"""Optional OpenTelemetry bridge (v1)."""

from __future__ import annotations

from typing import Any

from sqube_agent_guard.ledger.events import ExecutionEvent


class OtelEventSink:
    """Emit Sqube events as OTel span events when opentelemetry-api is installed."""

    def __init__(self, tracer_name: str = "sqube.agent.control") -> None:
        self._tracer = None
        try:
            from opentelemetry import trace

            self._tracer = trace.get_tracer(tracer_name)
        except ImportError:
            self._tracer = None

    def emit(self, event: ExecutionEvent) -> None:
        if self._tracer is None:
            return
        span = self._tracer.start_span(
            name=f"sqube.{event.event_type.value}",
            attributes={
                "sqube.execution_id": event.execution_id,
                "sqube.event_id": event.event_id,
                "sqube.actor": event.actor,
            },
        )
        payload: dict[str, Any] = event.payload
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)):
                span.set_attribute(f"sqube.payload.{key}", value)
        span.end()
