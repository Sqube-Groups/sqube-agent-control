from __future__ import annotations

from typing import TYPE_CHECKING

from sqube_agent_guard.ledger.events import EventType, ExecutionEvent
from sqube_agent_guard.platform_events import platform_event_from_ledger

if TYPE_CHECKING:
    from sqube_agent_guard.export.exporter import EventExporter
    from sqube_agent_guard.ledger.store import SQLiteExecutionStore


_STATUS_BY_EVENT: dict[EventType, str] = {
    EventType.ACTION_SUCCEEDED: "SUCCEEDED",
    EventType.ACTION_FAILED: "FAILED",
    EventType.ACTION_BLOCKED: "BLOCKED",
    EventType.ACTION_CANCELLED: "CANCELLED",
    EventType.APPROVAL_DENIED: "DENIED",
    EventType.APPROVAL_EXPIRED: "EXPIRED",
}


class ControlPlaneExportSink:
    """Queues ledger events for durable HTTP export (observability path only)."""

    def __init__(self, exporter: EventExporter, ledger: SQLiteExecutionStore) -> None:
        self._exporter = exporter
        self._ledger = ledger

    def emit(self, event: ExecutionEvent) -> None:
        try:
            row = self._ledger.get_execution(event.execution_id) or {}
            status = row.get("status") or _STATUS_BY_EVENT.get(event.event_type)
            platform = platform_event_from_ledger(
                event,
                agent_id=row.get("agent_id"),
                action=row.get("action"),
                resource=row.get("resource"),
                decision=row.get("decision"),
                status=status,
                correlation_id=row.get("correlation_id"),
                root_execution_id=row.get("root_execution_id"),
                policy_id=row.get("policy_id"),
            )
            self._exporter.enqueue(platform)
        except Exception:
            pass
