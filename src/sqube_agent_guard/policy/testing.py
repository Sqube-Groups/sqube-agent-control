"""Policy test helpers (v1)."""

from __future__ import annotations

from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.identity.models import AgentIdentity, Principal
from sqube_agent_guard.models import Decision
from sqube_agent_guard.policy.engine import Policy


def context_for(
    *,
    agent: str = "default",
    action: str,
    resource: str | None = None,
    environment: str | None = None,
    principal_type: str | None = None,
    principal_id: str | None = None,
    execution_id: str = "sq_exec_test",
) -> ExecutionContext:
    principal = None
    if principal_type and principal_id:
        principal = Principal(type=principal_type, id=principal_id)
    return ExecutionContext(
        execution_id=execution_id,
        agent=AgentIdentity(agent_id=agent, environment=environment),
        action=action,
        resource=resource,
        environment=environment,
        principal=principal,
    )


def assert_decision(policy: Policy, ctx: ExecutionContext, expected: Decision) -> None:
    actual = policy.evaluate(ctx).decision
    assert actual == expected, f"expected {expected}, got {actual}"
