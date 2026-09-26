from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from sqube_agent_guard.core.hashing import sha256_hex, stable_json_dumps
from sqube_agent_guard.ledger.events import EventType, ExecutionEvent
from sqube_agent_guard.models import ActionRecord, ActionStatus


class ExecutionStore(Protocol):
    def append_event(
        self,
        execution_id: str,
        event_type: EventType,
        actor: str,
        payload: dict[str, Any],
        timestamp: str,
    ) -> ExecutionEvent: ...

    def get_execution(self, execution_id: str) -> dict[str, Any] | None: ...

    def get_events(self, execution_id: str) -> list[ExecutionEvent]: ...

    def list_executions(self, limit: int = 50) -> list[dict[str, Any]]: ...

    def verify_chain(self, execution_id: str | None = None) -> bool: ...

    def upsert_execution_record(self, record: ActionRecord) -> None: ...

    def update_execution_record(self, execution_id: str, **fields: Any) -> None: ...

    def get_latest_record(self) -> dict[str, Any] | None: ...

    def register_idempotency(
        self, idempotency_key: str, execution_id: str, created_at: str
    ) -> bool: ...

    def get_execution_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_records (
  execution_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  action TEXT NOT NULL,
  resource TEXT,
  parameters_hash TEXT NOT NULL,
  parameters_summary TEXT,
  decision TEXT NOT NULL,
  policy_id TEXT NOT NULL,
  policy_version TEXT,
  status TEXT NOT NULL,
  approved_by TEXT,
  approval_reason TEXT,
  result_status TEXT,
  error_message TEXT,
  duration_ms INTEGER,
  completed_at TEXT,
  correlation_id TEXT,
  parent_execution_id TEXT,
  root_execution_id TEXT
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
  idempotency_key TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_events (
  event_id TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload TEXT NOT NULL,
  previous_event_hash TEXT,
  event_hash TEXT NOT NULL
);
"""


class SQLiteExecutionStore:
    def __init__(self, path: str = "sqube_ledger.sqlite3") -> None:
        self._path = path
        parent = Path(path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(execution_records)")}
        if "policy_version" not in cols:
            self._conn.execute("ALTER TABLE execution_records ADD COLUMN policy_version TEXT")
        if "correlation_id" not in cols:
            self._conn.execute("ALTER TABLE execution_records ADD COLUMN correlation_id TEXT")
        if "parent_execution_id" not in cols:
            self._conn.execute("ALTER TABLE execution_records ADD COLUMN parent_execution_id TEXT")
        if "root_execution_id" not in cols:
            self._conn.execute("ALTER TABLE execution_records ADD COLUMN root_execution_id TEXT")

    def append_event(
        self,
        execution_id: str,
        event_type: EventType,
        actor: str,
        payload: dict[str, Any],
        timestamp: str,
    ) -> ExecutionEvent:
        prev = self._conn.execute(
            "SELECT event_hash FROM execution_events WHERE execution_id = ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (execution_id,),
        ).fetchone()
        previous_hash = prev[0] if prev else None
        event_id = f"sq_evt_{uuid.uuid4().hex[:16]}"
        body = stable_json_dumps(
            {
                "event_id": event_id,
                "execution_id": execution_id,
                "event_type": event_type.value,
                "timestamp": timestamp,
                "actor": actor,
                "payload": payload,
                "previous_event_hash": previous_hash,
            }
        )
        event_hash = sha256_hex(body)
        self._conn.execute(
            "INSERT INTO execution_events "
            "(event_id, execution_id, event_type, timestamp, actor, payload, "
            "previous_event_hash, event_hash) VALUES (?,?,?,?,?,?,?,?)",
            (
                event_id,
                execution_id,
                event_type.value,
                timestamp,
                actor,
                stable_json_dumps(payload),
                previous_hash,
                event_hash,
            ),
        )
        self._conn.commit()
        return ExecutionEvent(
            event_id=event_id,
            execution_id=execution_id,
            event_type=event_type,
            timestamp=timestamp,
            actor=actor,
            payload=payload,
            previous_event_hash=previous_hash,
            event_hash=event_hash,
        )

    def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM execution_records WHERE execution_id = ?",
            (execution_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_events(self, execution_id: str) -> list[ExecutionEvent]:
        rows = self._conn.execute(
            "SELECT * FROM execution_events WHERE execution_id = ? ORDER BY timestamp ASC",
            (execution_id,),
        ).fetchall()
        events: list[ExecutionEvent] = []
        for row in rows:
            events.append(
                ExecutionEvent(
                    event_id=row["event_id"],
                    execution_id=row["execution_id"],
                    event_type=EventType(row["event_type"]),
                    timestamp=row["timestamp"],
                    actor=row["actor"],
                    payload=json.loads(row["payload"]),
                    previous_event_hash=row["previous_event_hash"],
                    event_hash=row["event_hash"],
                )
            )
        return events

    def list_executions(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM execution_records ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def verify_chain(self, execution_id: str | None = None) -> bool:
        if execution_id:
            events = self.get_events(execution_id)
        else:
            rows = self._conn.execute(
                "SELECT execution_id FROM execution_events ORDER BY timestamp ASC"
            ).fetchall()
            execution_ids = {r[0] for r in rows}
            return all(self.verify_chain(eid) for eid in execution_ids) if execution_ids else True
        for event in events:
            body = stable_json_dumps(
                {
                    "event_id": event.event_id,
                    "execution_id": event.execution_id,
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp,
                    "actor": event.actor,
                    "payload": event.payload,
                    "previous_event_hash": event.previous_event_hash,
                }
            )
            if sha256_hex(body) != event.event_hash:
                return False
        return True

    def upsert_execution_record(self, record: ActionRecord) -> None:
        row = record.to_row()
        if "policy_version" not in row:
            row["policy_version"] = None
        columns = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        self._conn.execute(
            f"INSERT INTO execution_records ({columns}) VALUES ({placeholders})",
            tuple(row.values()),
        )
        self._conn.commit()

    def update_execution_record(self, execution_id: str, **fields: Any) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [execution_id]
        self._conn.execute(
            f"UPDATE execution_records SET {assignments} WHERE execution_id = ?",
            values,
        )
        self._conn.commit()

    def get_latest_record(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM execution_records ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def register_idempotency(
        self, idempotency_key: str, execution_id: str, created_at: str
    ) -> bool:
        try:
            self._conn.execute(
                "INSERT INTO idempotency_keys (idempotency_key, execution_id, created_at) "
                "VALUES (?, ?, ?)",
                (idempotency_key, execution_id, created_at),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_execution_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT r.* FROM execution_records r "
            "INNER JOIN idempotency_keys k ON k.execution_id = r.execution_id "
            "WHERE k.idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        self._conn.close()
