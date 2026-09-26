"""Optional OpenTelemetry bridge — observes ledger events only (never affects policy/execution)."""

from __future__ import annotations

import logging
from typing import Any

from sqube_agent_guard.ledger.events import EventType, ExecutionEvent
from sqube_agent_guard.redaction import redact_value

_logger = logging.getLogger(__name__)

_TERMINAL_EVENTS = frozenset(
    {
        EventType.ACTION_SUCCEEDED,
        EventType.ACTION_FAILED,
        EventType.ACTION_CANCELLED,
        EventType.ACTION_BLOCKED,
        EventType.APPROVAL_DENIED,
        EventType.APPROVAL_EXPIRED,
    }
)

_PAYLOAD_ALLOWLIST: dict[EventType, frozenset[str]] = {
    EventType.ACTION_REQUESTED: frozenset({"action", "resource"}),
    EventType.CONTEXT_RESOLVED: frozenset(
        {"correlation_id", "root_execution_id", "principal"}
    ),
    EventType.POLICY_EVALUATED: frozenset(
        {"decision", "policy_id", "policy_version", "reason"}
    ),
    EventType.ACTION_BLOCKED: frozenset({"reason"}),
    EventType.APPROVAL_REQUESTED: frozenset({"approval_id", "expires_at"}),
    EventType.APPROVAL_GRANTED: frozenset({}),
    EventType.APPROVAL_DENIED: frozenset({"reason"}),
    EventType.APPROVAL_EXPIRED: frozenset({"reason"}),
    EventType.ACTION_STARTED: frozenset({"approval_id"}),
    EventType.ACTION_FAILED: frozenset({"error", "duration_ms"}),
    EventType.ACTION_SUCCEEDED: frozenset({"duration_ms"}),
    EventType.ACTION_CANCELLED: frozenset({"reason"}),
}


def _safe_attribute_value(key: str, value: Any) -> str | int | float | bool | None:
    lowered = key.lower()
    if any(bad in lowered for bad in ("secret", "token", "password", "authorization")):
        return None
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_value(value) if len(value) > 64 else value
    return redact_value(value)


def _payload_to_attributes(
    event_type: EventType, payload: dict[str, Any]
) -> dict[str, str | int | float | bool]:
    allowed = _PAYLOAD_ALLOWLIST.get(event_type, frozenset())
    out: dict[str, str | int | float | bool] = {}
    for key in allowed:
        if key not in payload:
            continue
        val = _safe_attribute_value(key, payload[key])
        if val is not None:
            out[f"sqube.{key}"] = val
    if "approval_id" in payload and "sqube.approval_id" not in out:
        val = _safe_attribute_value("approval_id", payload["approval_id"])
        if val is not None:
            out["sqube.approval_id"] = val
    if event_type == EventType.POLICY_EVALUATED and "decision" in payload:
        out["sqube.decision"] = str(payload["decision"])
    if event_type == EventType.POLICY_EVALUATED and "policy_id" in payload:
        out["sqube.policy_id"] = str(payload["policy_id"])
    return out


class OtelEventSink:
    """Emit traces and metrics from tamper-evident ledger events (optional OTel install)."""

    def __init__(self, tracer_name: str = "sqube.agent.control") -> None:
        self._tracer = None
        self._meter = None
        self._spans: dict[str, Any] = {}
        self._counters: dict[str, Any] = {}
        self._duration_hist = None
        try:
            from opentelemetry import metrics, trace

            self._tracer = trace.get_tracer(tracer_name)
            self._meter = metrics.get_meter(tracer_name)
            self._init_metrics()
        except ImportError:
            pass

    def _init_metrics(self) -> None:
        if self._meter is None:
            return
        names = [
            "sqube.executions.total",
            "sqube.executions.allowed",
            "sqube.executions.blocked",
            "sqube.executions.approval_required",
            "sqube.executions.succeeded",
            "sqube.executions.failed",
            "sqube.executions.cancelled",
            "sqube.approvals.granted",
            "sqube.approvals.denied",
            "sqube.approvals.expired",
        ]
        for name in names:
            self._counters[name] = self._meter.create_counter(name)
        self._duration_hist = self._meter.create_histogram("sqube.execution.duration")

    def emit(self, event: ExecutionEvent) -> None:
        try:
            self._emit_inner(event)
        except Exception:  # noqa: BLE001 — telemetry must never affect execution
            _logger.debug("OpenTelemetry emit failed", exc_info=True)

    def _emit_inner(self, event: ExecutionEvent) -> None:
        if self._tracer is None:
            return

        span = self._spans.get(event.execution_id)
        if event.event_type == EventType.ACTION_REQUESTED:
            attrs = _payload_to_attributes(event.event_type, event.payload)
            attrs["sqube.execution_id"] = event.execution_id
            if event.actor:
                attrs["sqube.agent_id"] = event.actor
            span = self._tracer.start_span("sqube.execution", attributes=attrs)
            self._spans[event.execution_id] = span
            self._inc("sqube.executions.total")
            span.add_event("execution requested", attributes=attrs)
            return

        if span is None:
            span = self._tracer.start_span(
                "sqube.execution",
                attributes={"sqube.execution_id": event.execution_id},
            )
            self._spans[event.execution_id] = span

        event_name = event.event_type.value.replace("_", " ").lower()
        attrs = _payload_to_attributes(event.event_type, event.payload)
        attrs["sqube.execution_id"] = event.execution_id
        span.add_event(event_name, attributes=attrs)
        self._record_metrics(event, attrs)

        if event.event_type in _TERMINAL_EVENTS:
            status = attrs.get("sqube.decision") or event.event_type.value
            span.set_attribute("sqube.status", str(status))
            span.end()
            self._spans.pop(event.execution_id, None)

    def _inc(self, name: str, value: int = 1) -> None:
        counter = self._counters.get(name)
        if counter is not None:
            counter.add(value)

    def _record_metrics(
        self, event: ExecutionEvent, attrs: dict[str, str | int | float | bool]
    ) -> None:
        et = event.event_type
        if et == EventType.POLICY_EVALUATED:
            decision = str(attrs.get("sqube.decision", ""))
            if decision == "ALLOW":
                self._inc("sqube.executions.allowed")
            elif decision == "BLOCK":
                self._inc("sqube.executions.blocked")
            elif decision == "REQUIRE_APPROVAL":
                self._inc("sqube.executions.approval_required")
        elif et == EventType.ACTION_BLOCKED:
            self._inc("sqube.executions.blocked")
        elif et == EventType.ACTION_SUCCEEDED:
            self._inc("sqube.executions.succeeded")
            if self._duration_hist is not None:
                ms = event.payload.get("duration_ms")
                if isinstance(ms, int):
                    self._duration_hist.record(ms)
        elif et == EventType.ACTION_FAILED:
            self._inc("sqube.executions.failed")
            if self._duration_hist is not None:
                ms = event.payload.get("duration_ms")
                if isinstance(ms, int):
                    self._duration_hist.record(ms)
        elif et == EventType.ACTION_CANCELLED:
            self._inc("sqube.executions.cancelled")
        elif et == EventType.APPROVAL_GRANTED:
            self._inc("sqube.approvals.granted")
        elif et == EventType.APPROVAL_DENIED:
            self._inc("sqube.approvals.denied")
        elif et == EventType.APPROVAL_EXPIRED:
            self._inc("sqube.approvals.expired")
