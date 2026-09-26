"""Stateless authorize API (v1): evaluate policy from a JSON request body."""

from __future__ import annotations

from typing import Any

from sqube_agent_guard.execution.engine import _new_execution_id, context_from_wrap
from sqube_agent_guard.policy.engine import Policy


def authorize_request(policy: Policy, body: dict[str, Any]) -> dict[str, Any]:
    """Evaluate policy without writing to the ledger."""
    agent_id = str(body.get("agent_id") or "default")
    action = body.get("action")
    if not action:
        raise ValueError("action is required")
    resource = body.get("resource")
    environment = body.get("environment")
    parameters = body.get("parameters") or {}
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")

    principal_type = body.get("principal_type")
    principal_id = body.get("principal_id")
    ctx = context_from_wrap(
        execution_id=str(body.get("execution_id") or _new_execution_id()),
        agent_id=agent_id,
        action=str(action),
        resource=str(resource) if resource is not None else None,
        parameters=parameters,
        environment=str(environment) if environment is not None else None,
        principal_type=str(principal_type) if principal_type else None,
        principal_id=str(principal_id) if principal_id else None,
    )
    if body.get("idempotency_key"):
        ctx.idempotency_key = str(body["idempotency_key"])

    result = policy.evaluate(ctx)
    return {
        "decision": result.decision.value,
        "policy_id": result.policy_id,
        "policy_version": result.policy_version,
        "policy_hash": result.policy_hash,
        "reason": result.reason,
        "matched_rules": result.matched_rules,
        "failed_rules": result.failed_rules,
        "execution_id": ctx.execution_id,
    }
