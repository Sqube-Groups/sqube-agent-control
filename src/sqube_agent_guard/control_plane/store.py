from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqube_agent_guard.control_plane.event_bus import EventBus
from sqube_agent_guard.control_plane.models import AgentRegistration, PolicyRegistration
from sqube_agent_guard.control_plane.webhooks import WebhookStore
from sqube_agent_guard.ledger.store import SQLiteExecutionStore
from sqube_agent_guard.platform_events import sse_type_for_platform_event


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  agent_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  runtime TEXT,
  version TEXT,
  environment TEXT,
  status TEXT NOT NULL,
  capabilities TEXT,
  policy_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policies (
  policy_id TEXT NOT NULL,
  version TEXT NOT NULL,
  name TEXT,
  bundle_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (policy_id, version)
);

CREATE TABLE IF NOT EXISTS ingested_events (
  event_id TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  stream_seq INTEGER NOT NULL,
  received_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cp_executions (
  execution_id TEXT PRIMARY KEY,
  agent_id TEXT,
  action TEXT,
  resource TEXT,
  decision TEXT,
  status TEXT,
  policy_id TEXT,
  correlation_id TEXT,
  root_execution_id TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS event_stream_counter (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  seq INTEGER NOT NULL
);
INSERT OR IGNORE INTO event_stream_counter (id, seq) VALUES (1, 0);
"""


class ControlPlaneStore:
    """Control-plane metadata (agents/policies) + read access to execution ledger."""

    def __init__(self, plane_db_path: str, ledger_path: str) -> None:
        parent = Path(plane_db_path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(plane_db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._ledger = SQLiteExecutionStore(ledger_path)
        self.bus = EventBus()
        self.webhooks = WebhookStore(self._conn)

    @property
    def ledger(self) -> SQLiteExecutionStore:
        return self._ledger

    def _next_stream_seq(self) -> int:
        self._conn.execute(
            "UPDATE event_stream_counter SET seq = seq + 1 WHERE id = 1"
        )
        row = self._conn.execute(
            "SELECT seq FROM event_stream_counter WHERE id = 1"
        ).fetchone()
        self._conn.commit()
        return int(row[0])

    def ingest_events_batch(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        accepted: list[str] = []
        duplicates: list[str] = []
        rejected: list[dict[str, str]] = []
        for raw in events:
            event_id = raw.get("event_id")
            if (
                not event_id
                or not raw.get("execution_id")
                or not raw.get("agent_id")
                or not raw.get("event_type")
                or not raw.get("timestamp")
            ):
                rejected.append({"event_id": str(event_id), "reason": "missing required fields"})
                continue
            existing = self._conn.execute(
                "SELECT 1 FROM ingested_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing:
                duplicates.append(event_id)
                continue
            seq = self._next_stream_seq()
            now = _utc_now()
            safe = {
                k: raw.get(k)
                for k in (
                    "event_id",
                    "execution_id",
                    "agent_id",
                    "event_type",
                    "timestamp",
                    "action",
                    "resource",
                    "decision",
                    "status",
                    "correlation_id",
                    "root_execution_id",
                    "policy_id",
                )
            }
            self._conn.execute(
                "INSERT INTO ingested_events "
                "(event_id, execution_id, agent_id, event_type, timestamp, payload_json, stream_seq, received_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    safe["event_id"],
                    safe["execution_id"],
                    safe["agent_id"],
                    safe.get("event_type") or "UNKNOWN",
                    safe.get("timestamp") or now,
                    json.dumps(safe, sort_keys=True),
                    seq,
                    now,
                ),
            )
            self._apply_execution_projection(safe, now)
            accepted.append(event_id)
            sse_type = sse_type_for_platform_event(safe)
            self.bus.publish_sync(sse_type, safe)
            try:
                self.webhooks.deliver(sse_type, safe)
            except Exception:
                pass
        self._conn.commit()
        return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}

    def _apply_execution_projection(self, ev: dict[str, Any], now: str) -> None:
        ex_id = ev["execution_id"]
        row_raw = self._conn.execute(
            "SELECT * FROM cp_executions WHERE execution_id = ?", (ex_id,)
        ).fetchone()
        row = dict(row_raw) if row_raw else None
        created = row["created_at"] if row else (ev.get("timestamp") or now)
        fields = {
            "agent_id": ev.get("agent_id"),
            "action": ev.get("action") or (row["action"] if row else None),
            "resource": ev.get("resource") or (row["resource"] if row else None),
            "decision": ev.get("decision") or (row["decision"] if row else None),
            "status": ev.get("status") or (row["status"] if row else None),
            "policy_id": ev.get("policy_id") or (row["policy_id"] if row else None),
            "correlation_id": ev.get("correlation_id")
            or (row["correlation_id"] if row else None),
            "root_execution_id": ev.get("root_execution_id")
            or (row["root_execution_id"] if row else None),
            "created_at": created,
            "updated_at": now,
        }
        et = ev.get("event_type")
        if et == "POLICY_EVALUATED" and ev.get("decision"):
            fields["decision"] = ev["decision"]
        if et in ("ACTION_SUCCEEDED",):
            fields["status"] = "SUCCEEDED"
        elif et == "ACTION_FAILED":
            fields["status"] = "FAILED"
        elif et == "ACTION_BLOCKED":
            fields["status"] = "BLOCKED"
        elif et == "ACTION_CANCELLED":
            fields["status"] = "CANCELLED"
        elif et in ("APPROVAL_DENIED",):
            fields["status"] = "DENIED"
        elif et == "APPROVAL_EXPIRED":
            fields["status"] = "EXPIRED"
        elif et == "APPROVAL_REQUESTED":
            fields["status"] = "WAITING_APPROVAL"
        if row:
            self._conn.execute(
                "UPDATE cp_executions SET agent_id=?, action=?, resource=?, decision=?, status=?, "
                "policy_id=?, correlation_id=?, root_execution_id=?, updated_at=? WHERE execution_id=?",
                (
                    fields["agent_id"],
                    fields["action"],
                    fields["resource"],
                    fields["decision"],
                    fields["status"],
                    fields["policy_id"],
                    fields["correlation_id"],
                    fields["root_execution_id"],
                    fields["updated_at"],
                    ex_id,
                ),
            )
        else:
            self._conn.execute(
                "INSERT INTO cp_executions (execution_id, agent_id, action, resource, decision, status, "
                "policy_id, correlation_id, root_execution_id, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ex_id,
                    fields["agent_id"],
                    fields["action"],
                    fields["resource"],
                    fields["decision"],
                    fields["status"],
                    fields["policy_id"],
                    fields["correlation_id"],
                    fields["root_execution_id"],
                    fields["created_at"],
                    fields["updated_at"],
                ),
            )

    def _list_cp_executions(self, limit: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM cp_executions ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def _merge_executions(self, limit: int, status: str | None = None) -> list[dict[str, Any]]:
        local = self._ledger.list_executions(limit=limit, status=status)
        remote = self._list_cp_executions(limit)
        by_id: dict[str, dict[str, Any]] = {}
        for row in local + remote:
            ex_id = row["execution_id"]
            prev = by_id.get(ex_id)
            if not prev or (row.get("updated_at") or row.get("created_at", "")) >= (
                prev.get("updated_at") or prev.get("created_at", "")
            ):
                by_id[ex_id] = row
        merged = list(by_id.values())
        merged.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return merged[:limit]

    def register_agent(self, reg: AgentRegistration) -> dict[str, Any]:
        now = _utc_now()
        caps = json.dumps(reg.capabilities or [])
        existing = self.get_agent(reg.agent_id)
        if existing:
            self._conn.execute(
                "UPDATE agents SET name=?, runtime=?, version=?, environment=?, status=?, "
                "capabilities=?, policy_id=?, updated_at=? WHERE agent_id=?",
                (
                    reg.name,
                    reg.runtime,
                    reg.version,
                    reg.environment,
                    reg.status,
                    caps,
                    reg.policy_id,
                    now,
                    reg.agent_id,
                ),
            )
        else:
            self._conn.execute(
                "INSERT INTO agents (agent_id, name, runtime, version, environment, status, "
                "capabilities, policy_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    reg.agent_id,
                    reg.name,
                    reg.runtime,
                    reg.version,
                    reg.environment,
                    reg.status,
                    caps,
                    reg.policy_id,
                    now,
                    now,
                ),
            )
        self._conn.commit()
        agent = self.get_agent(reg.agent_id) or {}
        self.bus.publish_sync(
            "agent.registered",
            {"agent_id": reg.agent_id, "name": reg.name, "environment": reg.environment},
        )
        try:
            self.webhooks.deliver(
                "agent.registered",
                {"agent_id": reg.agent_id, "name": reg.name},
            )
        except Exception:
            pass
        return agent

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["capabilities"] = json.loads(data["capabilities"] or "[]")
        return data

    def list_agents(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM agents ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["capabilities"] = json.loads(data["capabilities"] or "[]")
            out.append(data)
        return out

    def register_policy(self, reg: PolicyRegistration) -> dict[str, Any]:
        now = _utc_now()
        bundle_json = json.dumps(reg.bundle, sort_keys=True)
        self._conn.execute(
            "INSERT OR REPLACE INTO policies (policy_id, version, name, bundle_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (reg.policy_id, reg.version, reg.name, bundle_json, now),
        )
        self._conn.commit()
        policy = self.get_policy(reg.policy_id, reg.version) or {}
        self.bus.publish_sync(
            "policy.changed",
            {"policy_id": reg.policy_id, "version": reg.version, "name": reg.name},
        )
        try:
            self.webhooks.deliver(
                "policy.changed",
                {"policy_id": reg.policy_id, "version": reg.version},
            )
        except Exception:
            pass
        return policy

    def get_policy(self, policy_id: str, version: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM policies WHERE policy_id = ? AND version = ?",
            (policy_id, version),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["bundle"] = json.loads(data.pop("bundle_json"))
        return data

    def list_policies(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM policies ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["bundle"] = json.loads(data.pop("bundle_json"))
            out.append(data)
        return out

    def overview(self) -> dict[str, Any]:
        agents = self.list_agents(limit=10_000)
        executions = self._merge_executions(limit=500)
        pending = self._ledger.list_approval_requests(status="PENDING", limit=500)
        allowed = blocked = approval_req = succeeded = failed = cancelled = 0
        for row in executions:
            decision = row.get("decision", "")
            status = row.get("status", "")
            if decision == "ALLOW":
                allowed += 1
            elif decision == "BLOCK":
                blocked += 1
            elif decision == "REQUIRE_APPROVAL":
                approval_req += 1
            if status == "SUCCEEDED":
                succeeded += 1
            elif status == "FAILED":
                failed += 1
            elif status == "CANCELLED":
                cancelled += 1
        return {
            "total_agents": len(agents),
            "total_executions_sampled": len(executions),
            "counts": {
                "allowed_decisions": allowed,
                "blocked_decisions": blocked,
                "approval_required_decisions": approval_req,
                "succeeded": succeeded,
                "failed": failed,
                "cancelled": cancelled,
                "pending_approvals": len(pending),
            },
            "recent_executions": executions[:20],
            "pending_approvals": [
                {
                    "approval_id": p.approval_id,
                    "execution_id": p.execution_id,
                    "requested_at": p.requested_at,
                    "expires_at": p.expires_at,
                }
                for p in pending
            ],
        }

    def list_executions(
        self,
        *,
        agent_id: str | None = None,
        status: str | None = None,
        action: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = self._merge_executions(limit=limit, status=status)
        if agent_id:
            rows = [r for r in rows if r.get("agent_id") == agent_id]
        if action:
            rows = [r for r in rows if r.get("action") == action]
        return rows

    def get_execution_detail(self, execution_id: str) -> dict[str, Any] | None:
        row = self._ledger.get_execution(execution_id)
        if not row:
            cp = self._conn.execute(
                "SELECT * FROM cp_executions WHERE execution_id = ?", (execution_id,)
            ).fetchone()
            if not cp:
                return None
            row = dict(cp)
        events = [
            {
                "timestamp": e.timestamp,
                "event_type": e.event_type.value,
                "actor": e.actor,
                "payload": e.payload,
                "event_hash": e.event_hash,
            }
            for e in self._ledger.get_events(execution_id)
        ]
        ingested = self._conn.execute(
            "SELECT payload_json, timestamp, event_type FROM ingested_events "
            "WHERE execution_id = ? ORDER BY stream_seq ASC",
            (execution_id,),
        ).fetchall()
        for r in ingested:
            events.append(
                {
                    "timestamp": r[1],
                    "event_type": r[2],
                    "actor": "ingestion",
                    "payload": json.loads(r[0]),
                    "event_hash": None,
                }
            )
        events.sort(key=lambda e: e["timestamp"])
        return {"execution": row, "events": events}

    def ingested_events_after(self, stream_seq: int, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT stream_seq, payload_json FROM ingested_events "
            "WHERE stream_seq > ? ORDER BY stream_seq ASC LIMIT ?",
            (stream_seq, limit),
        ).fetchall()
        out = []
        for seq, payload in rows:
            data = json.loads(payload)
            data["stream_seq"] = seq
            out.append(data)
        return out
