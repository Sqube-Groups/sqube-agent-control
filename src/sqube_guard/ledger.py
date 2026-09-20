from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from sqube_guard.models import ActionRecord

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
  status TEXT NOT NULL,
  approved_by TEXT,
  approval_reason TEXT,
  result_status TEXT,
  error_message TEXT,
  duration_ms INTEGER,
  completed_at TEXT
);
"""


class Ledger:
    def __init__(self, path: str = "sqube_ledger.sqlite3") -> None:
        self._path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def insert(self, record: ActionRecord) -> None:
        row = record.to_row()
        columns = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        self._conn.execute(
            f"INSERT INTO execution_records ({columns}) VALUES ({placeholders})",
            tuple(row.values()),
        )
        self._conn.commit()

    def update_status(self, execution_id: str, **fields: Any) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [execution_id]
        self._conn.execute(
            f"UPDATE execution_records SET {assignments} WHERE execution_id = ?",
            values,
        )
        self._conn.commit()

    def get(self, execution_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM execution_records WHERE execution_id = ?",
            (execution_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_latest(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM execution_records ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        self._conn.close()
