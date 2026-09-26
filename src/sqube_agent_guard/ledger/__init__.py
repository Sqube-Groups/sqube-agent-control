"""Execution ledger: events, store, and v0.1-compatible facade."""

from __future__ import annotations

from typing import Any

from sqube_agent_guard.ledger.store import SQLiteExecutionStore
from sqube_agent_guard.models import ActionRecord


class Ledger:
    def __init__(self, path: str = "sqube_ledger.sqlite3") -> None:
        self._store = SQLiteExecutionStore(path)

    def insert(self, record: ActionRecord) -> None:
        self._store.upsert_execution_record(record)

    def update_status(self, execution_id: str, **fields: Any) -> None:
        self._store.update_execution_record(execution_id, **fields)

    def get(self, execution_id: str) -> dict[str, Any] | None:
        return self._store.get_execution(execution_id)

    def get_latest(self) -> dict[str, Any] | None:
        return self._store.get_latest_record()

    def close(self) -> None:
        self._store.close()
