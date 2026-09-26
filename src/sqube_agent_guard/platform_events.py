"""Canonical platform events (ingestion, SSE, webhooks). Ledger remains authoritative."""

from __future__ import annotations

from typing import Any

from sqube_agent_guard.ledger.events import EventType, ExecutionEvent


def platform_event_from_ledger(
    event: ExecutionEvent,
    *,
    agent_id: str | None = None,
    action: str | None = None,
    resource: str | None = None,
    decision: str | None = None,
    status: str | None = None,
    correlation_id: str | None = None,
    root_execution_id: str | None = None,
    policy_id: str | None = None,
) -> dict[str, Any]:
    """Build a redacted platform event dict safe for HTTP export."""
    payload = event.payload or {}
    if decision is None and event.event_type == EventType.POLICY_EVALUATED:
        decision = str(payload.get("decision", "")) or None
    if policy_id is None and event.event_type == EventType.POLICY_EVALUATED:
        policy_id = str(payload.get("policy_id", "")) or None
    if action is None:
        action = payload.get("action") if isinstance(payload.get("action"), str) else None
    if resource is None:
        resource = payload.get("resource") if isinstance(payload.get("resource"), str) else None
    if correlation_id is None:
        correlation_id = payload.get("correlation_id")
    if root_execution_id is None:
        root_execution_id = payload.get("root_execution_id")
    resolved_agent = agent_id or event.actor
    return {
        "event_id": event.event_id,
        "execution_id": event.execution_id,
        "agent_id": resolved_agent,
        "event_type": event.event_type.value,
        "timestamp": event.timestamp,
        "action": action,
        "resource": resource,
        "decision": decision,
        "status": status,
        "correlation_id": correlation_id,
        "root_execution_id": root_execution_id,
        "policy_id": policy_id,
    }


def sse_type_for_platform_event(event: dict[str, Any]) -> str:
    et = event.get("event_type", "")
    mapping = {
        "ACTION_REQUESTED": "execution.created",
        "POLICY_EVALUATED": "execution.updated",
        "ACTION_SUCCEEDED": "execution.succeeded",
        "ACTION_FAILED": "execution.failed",
        "ACTION_BLOCKED": "execution.blocked",
        "APPROVAL_REQUESTED": "approval.required",
        "APPROVAL_GRANTED": "approval.granted",
        "APPROVAL_DENIED": "approval.denied",
        "APPROVAL_EXPIRED": "approval.denied",
        "ACTION_CANCELLED": "execution.updated",
        "ACTION_STARTED": "execution.updated",
        "CONTEXT_RESOLVED": "execution.updated",
    }
    return mapping.get(et, "execution.updated")
