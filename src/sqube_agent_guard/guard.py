from __future__ import annotations

import functools
import hashlib
import json
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal

from sqube_agent_guard.approval import prompt_cli_approval
from sqube_agent_guard.exceptions import SqubeBlockedError, SqubeDeniedError, SqubeGuardError
from sqube_agent_guard.ledger import Ledger
from sqube_agent_guard.models import ActionRecord, ActionStatus, Decision
from sqube_agent_guard.policy import default_policy
from sqube_agent_guard.redaction import redact_value

OnErrorMode = Literal["fail_open", "fail_closed"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_execution_id() -> str:
    return f"sq_exec_{uuid.uuid4().hex[:16]}"


def _hash_parameters(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    payload = {"args": args, "kwargs": kwargs}
    try:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    except TypeError:
        encoded = repr(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _policy_id(policy: Callable[..., Decision]) -> str:
    return getattr(policy, "__name__", "anonymous_policy")


class ExecutionGuard:
    def __init__(
        self,
        *,
        policy: Callable[..., Decision] | None = None,
        ledger_path: str = "sqube_ledger.sqlite3",
        approval_timeout_seconds: int = 300,
        on_error: OnErrorMode = "fail_closed",
        approval_fn: Callable[..., tuple[bool, str | None, str | None]] | None = None,
    ) -> None:
        self._policy = policy or default_policy
        self._ledger = Ledger(ledger_path)
        self._approval_timeout = approval_timeout_seconds
        self._on_error = on_error
        self._approval_fn = approval_fn or prompt_cli_approval

    def wrap_action(
        self,
        *,
        action: str,
        resource: str | Callable[..., str] | None = None,
        agent_id: str = "default",
    ) -> Callable:
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return self._execute_wrapped(
                    fn=fn,
                    action=action,
                    resource_resolver=resource,
                    agent_id=agent_id,
                    args=args,
                    kwargs=kwargs,
                )

            return wrapper

        return decorator

    def _execute_wrapped(
        self,
        *,
        fn: Callable,
        action: str,
        resource_resolver: str | Callable[..., str] | None,
        agent_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        execution_id = _new_execution_id()
        created_at = _utc_now_iso()
        params_hash = _hash_parameters(args, kwargs)
        params_summary = redact_value(kwargs if kwargs else args)
        resource = self._resolve_resource(resource_resolver, args, kwargs)
        policy_id = _policy_id(self._policy)

        record = ActionRecord(
            execution_id=execution_id,
            created_at=created_at,
            agent_id=agent_id,
            action=action,
            resource=resource,
            parameters_hash=params_hash,
            parameters_summary=params_summary,
            decision=Decision.ALLOW.value,
            policy_id=policy_id,
            status=ActionStatus.REQUESTED.value,
        )
        self._ledger.insert(record)

        try:
            decision = self._policy(action, resource, agent_id, args=args, kwargs=kwargs)
        except Exception as exc:
            return self._handle_policy_error(
                execution_id=execution_id,
                fn=fn,
                args=args,
                kwargs=kwargs,
                error=exc,
            )

        if not isinstance(decision, Decision):
            decision = Decision(str(decision))

        self._ledger.update_status(
            execution_id,
            decision=decision.value,
            status=ActionStatus.EVALUATED.value,
        )

        if decision == Decision.BLOCK:
            self._ledger.update_status(
                execution_id,
                status=ActionStatus.BLOCKED.value,
                completed_at=_utc_now_iso(),
            )
            raise SqubeBlockedError(execution_id, action)

        if decision == Decision.REQUIRE_APPROVAL:
            self._ledger.update_status(execution_id, status=ActionStatus.WAITING_APPROVAL.value)
            approved, approved_by, reason = self._approval_fn(
                execution_id=execution_id,
                agent_id=agent_id,
                action=action,
                resource=resource,
                summary=params_summary,
                timeout_seconds=self._approval_timeout,
            )
            if not approved:
                status = ActionStatus.EXPIRED if reason == "timeout" else ActionStatus.DENIED
                self._ledger.update_status(
                    execution_id,
                    status=status.value,
                    approval_reason=reason,
                    completed_at=_utc_now_iso(),
                )
                raise SqubeDeniedError(execution_id, reason or "denied")

            self._ledger.update_status(
                execution_id,
                status=ActionStatus.APPROVED.value,
                approved_by=approved_by,
            )

        return self._run_fn(execution_id, fn, args, kwargs)

    def _handle_policy_error(
        self,
        *,
        execution_id: str,
        fn: Callable,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        error: Exception,
    ) -> Any:
        self._ledger.update_status(
            execution_id,
            status=ActionStatus.FAILED.value,
            error_message=f"policy_error: {error}",
            completed_at=_utc_now_iso(),
        )
        if self._on_error == "fail_open":
            return self._run_fn(execution_id, fn, args, kwargs, guard_failed=True)
        raise SqubeGuardError(f"Policy evaluation failed: {error}") from error

    def _run_fn(
        self,
        execution_id: str,
        fn: Callable,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        guard_failed: bool = False,
    ) -> Any:
        self._ledger.update_status(execution_id, status=ActionStatus.EXECUTING.value)
        start = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self._ledger.update_status(
                execution_id,
                status=ActionStatus.FAILED.value,
                result_status="FAILED",
                error_message=str(exc),
                duration_ms=duration_ms,
                completed_at=_utc_now_iso(),
            )
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        self._ledger.update_status(
            execution_id,
            status=ActionStatus.SUCCEEDED.value,
            result_status="SUCCESS" if not guard_failed else "SUCCESS",
            duration_ms=duration_ms,
            completed_at=_utc_now_iso(),
        )
        return result

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
