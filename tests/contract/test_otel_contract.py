from __future__ import annotations

import json
from pathlib import Path

from sqube_agent_guard.ledger.events import EventType


def test_otel_span_events_cover_ledger_event_types() -> None:
    path = Path(__file__).resolve().parent / "otel_semantics.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mapped = set(data["span_events"].keys())
    for event_type in EventType:
        assert event_type.value in mapped
