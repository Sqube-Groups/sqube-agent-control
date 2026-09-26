from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqube_agent_guard.control_plane.models import AgentRegistration, PolicyRegistration
from sqube_agent_guard.ledger.store import SQLiteExecutionStore


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

    @property
    def ledger(self) -> SQLiteExecutionStore:
        return self._ledger

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
        return self.get_agent(reg.agent_id) or {}

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
        return self.get_policy(reg.policy_id, reg.version) or {}

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
        executions = self._ledger.list_executions(limit=500)
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
        rows = self._ledger.list_executions(limit=limit, status=status)
        if agent_id:
            rows = [r for r in rows if r.get("agent_id") == agent_id]
        if action:
            rows = [r for r in rows if r.get("action") == action]
        return rows

    def get_execution_detail(self, execution_id: str) -> dict[str, Any] | None:
        row = self._ledger.get_execution(execution_id)
        if not row:
            return None
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
        return {"execution": row, "events": events}
