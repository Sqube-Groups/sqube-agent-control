from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS export_queue (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  exported_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_export_pending ON export_queue(exported_at, seq);
"""


class ExportQueue:
    """Durable local queue for control-plane event export."""

    def __init__(self, db_path: str, max_pending: int = 10_000) -> None:
        parent = Path(db_path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._max_pending = max_pending

    def enqueue(self, event: dict[str, Any], created_at: str) -> bool:
        pending = self._conn.execute(
            "SELECT COUNT(*) FROM export_queue WHERE exported_at IS NULL"
        ).fetchone()[0]
        if pending >= self._max_pending:
            return False
        try:
            self._conn.execute(
                "INSERT INTO export_queue (event_id, payload_json, created_at) VALUES (?,?,?)",
                (event["event_id"], json.dumps(event, sort_keys=True), created_at),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return True

    def pending_batch(self, limit: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT event_id, payload_json FROM export_queue "
            "WHERE exported_at IS NULL ORDER BY seq ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [json.loads(r[1]) for r in rows]

    def mark_exported(self, event_ids: list[str], exported_at: str) -> None:
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        self._conn.execute(
            f"UPDATE export_queue SET exported_at = ? WHERE event_id IN ({placeholders})",
            [exported_at, *event_ids],
        )
        self._conn.commit()

    def pending_count(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM export_queue WHERE exported_at IS NULL"
        ).fetchone()[0]
