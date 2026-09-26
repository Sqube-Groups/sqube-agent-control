from __future__ import annotations

import functools
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any, Literal

from sqube_agent_guard.approval.provider import CliApprovalProvider
from sqube_agent_guard.execution.engine import ExecutionEngine, context_from_wrap, _new_execution_id
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.ledger import Ledger
from sqube_agent_guard.models import Decision
from sqube_agent_guard.policy.engine import CallablePolicy, Policy, PolicyEvaluation
from sqube_agent_guard.telemetry.sink import EventSink

OnErrorMode = Literal["fail_open", "fail_closed"]


class _LegacyApprovalAdapter(CliApprovalProvider):
    def __init__(self, approval_fn: Callable[..., tuple[bool, str | None, str | None]]) -> None:
        self._approval_fn = approval_fn

    def request(self, request, timeout_seconds: int):
        return self._approval_fn(
            execution_id=request.execution_id,
            agent_id=request.metadata.get("agent_id", "default"),
            action=request.action,
            resource=request.resource,
            summary=request.summary,
            timeout_seconds=timeout_seconds,
        )


def _as_policy(policy: Callable[..., Decision] | Policy | None) -> Policy:
    if policy is None:
        from sqube_agent_guard.policy import default_policy

        return CallablePolicy(default_policy)
    if hasattr(policy, "evaluate") and hasattr(policy, "metadata"):
        return policy  # type: ignore[return-value]
    return CallablePolicy(policy)  # type: ignore[arg-type]


class ExecutionGuard:
    """v1 execution guard with v0.1-compatible `wrap_action` API."""

    def __init__(
        self,
        *,
        policy: Callable[..., Decision] | Policy | None = None,
        ledger_path: str = "sqube_ledger.sqlite3",
        approval_timeout_seconds: int = 300,
        on_error: OnErrorMode = "fail_closed",
        approval_fn: Callable[..., tuple[bool, str | None, str | None]] | None = None,
        event_sinks: Sequence[EventSink] | None = None,
    ) -> None:
        policy_obj = _as_policy(policy)
        approval_provider = (
            _LegacyApprovalAdapter(approval_fn) if approval_fn else CliApprovalProvider()
        )
        self._engine = ExecutionEngine(
            policy=policy_obj,
            ledger_path=ledger_path,
            approval_provider=approval_provider,
            approval_timeout_seconds=approval_timeout_seconds,
            on_error=on_error,
            event_sinks=event_sinks,
        )
        self._ledger = Ledger(ledger_path)

    def simulate(self, ctx: ExecutionContext) -> PolicyEvaluation:
        return self._engine.simulate(ctx)

    def explain(self, ctx: ExecutionContext) -> PolicyEvaluation:
        return self._engine.explain(ctx)

    def wrap_action(
        self,
        *,
        action: str,
        resource: str | Callable[..., str] | None = None,
        agent_id: str = "default",
        environment: str | None = None,
        idempotency_key: str | Callable[..., str] | None = None,
        principal_type: str | None = None,
        principal_id: str | None = None,
    ) -> Callable:
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                execution_id = _new_execution_id()
                resource_val = self._resolve_resource(resource, args, kwargs)
                idem_val = self._resolve_resource(idempotency_key, args, kwargs)
                ctx = context_from_wrap(
                    execution_id=execution_id,
                    agent_id=agent_id,
                    action=action,
                    resource=resource_val,
                    parameters=kwargs if kwargs else {"args": args},
                    environment=environment,
                    idempotency_key=idem_val,
                    principal_type=principal_type,
                    principal_id=principal_id,
                )
                ctx.timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                return self._engine.run_controlled(ctx, lambda: fn(*args, **kwargs))

            return wrapper

        return decorator

    @staticmethod
    def _resolve_resource(
        resource_resolver: str | Callable[..., str] | None,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str | None:
        if resource_resolver is None:
            return None
        if isinstance(resource_resolver, str):
            return resource_resolver
        return resource_resolver(*args, **kwargs)
