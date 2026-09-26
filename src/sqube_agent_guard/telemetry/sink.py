from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from sqube_agent_guard.ledger.events import ExecutionEvent


class EventSink(Protocol):
    def emit(self, event: ExecutionEvent) -> None: ...


class JsonlEventSink:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: ExecutionEvent) -> None:
        record: dict[str, Any] = {
            "event_id": event.event_id,
            "execution_id": event.execution_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp,
            "actor": event.actor,
            "payload": event.payload,
            "event_hash": event.event_hash,
        }
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
