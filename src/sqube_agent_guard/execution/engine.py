from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqube_agent_guard.approval.provider import ApprovalProvider, CliApprovalProvider
from sqube_agent_guard.authority.delegation import Delegation
from sqube_agent_guard.exceptions import (
    SqubeBlockedError,
    SqubeDeniedError,
    SqubeGuardError,
    SqubeApprovalPendingError,
    SqubeIdempotencyConflictError,
    SqubeIdempotencyReplayError,
    SqubeInvalidStateTransitionError,
)
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.interceptor import ExecutionInterceptor
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.ledger.events import EventType, ExecutionEvent
from sqube_agent_guard.telemetry.sink import EventSink
from sqube_agent_guard.ledger.store import ExecutionStore, SQLiteExecutionStore
from sqube_agent_guard.models import ActionRecord, ActionStatus, Decision
from sqube_agent_guard.policy.engine import CallablePolicy, Policy, PolicyEvaluation
from sqube_agent_guard.policy import default_policy
from sqube_agent_guard.redaction import redact_value
from sqube_agent_guard.core.hashing import hash_payload

OnErrorMode = Literal["fail_open", "fail_closed"]
ApprovalMode = Literal["sync", "deferred"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_execution_id() -> str:
    return f"sq_exec_{uuid.uuid4().hex[:16]}"


class ExecutionEngine:
    def __init__(
        self,
        *,
        policy: Policy | None = None,
        store: ExecutionStore | None = None,
        ledger_path: str = "sqube_ledger.sqlite3",
        approval_provider: ApprovalProvider | None = None,
        approval_timeout_seconds: int = 300,
        on_error: OnErrorMode = "fail_closed",
        event_sinks: Sequence[EventSink] | None = None,
        interceptors: Sequence[ExecutionInterceptor] | None = None,
        approval_mode: ApprovalMode = "sync",
    ) -> None:
        if policy is None:
            policy = CallablePolicy(default_policy)
        self._policy = policy
        self._store = store or SQLiteExecutionStore(ledger_path)
        self._approval = approval_provider or CliApprovalProvider()
        self._approval_timeout = approval_timeout_seconds
        self._on_error = on_error
        self._event_sinks = tuple(event_sinks or ())
        self._interceptors = tuple(interceptors or ())
        self._approval_mode = approval_mode

    @property
    def store(self) -> ExecutionStore:
        return self._store

    def _transition(
        self, execution_id: str, from_status: str, to_status: str, **fields: Any
    ) -> None:
        self._store.transition_execution(
            execution_id, from_status, to_status, **fields
        )

    def _record_event(
        self,
        execution_id: str,
        event_type: EventType,
        actor: str,
        payload: dict[str, Any],
        timestamp: str,
    ) -> ExecutionEvent:
        event = self._store.append_event(
            execution_id, event_type, actor, payload, timestamp
        )
        for sink in self._event_sinks:
            sink.emit(event)
        return event

    def simulate(self, ctx: ExecutionContext) -> PolicyEvaluation:
        return self._policy.evaluate(ctx)

    def explain(self, ctx: ExecutionContext) -> PolicyEvaluation:
        return self._policy.explain(ctx)

    def _check_delegation(self, ctx: ExecutionContext) -> None:
        for delegation in ctx.delegation_chain:
            if not delegation.allows_action(ctx.action):
                raise SqubeGuardError(
                    f"delegation {delegation.delegation_id} does not authorize action {ctx.action}"
                )

    def run_controlled(
        self,
        ctx: ExecutionContext,
        fn: Callable[[], Any],
    ) -> Any:
        if not ctx.timestamp:
            ctx.timestamp = _utc_now_iso()
        if not ctx.root_execution_id:
            ctx.root_execution_id = ctx.execution_id
        if not ctx.correlation_id:
            ctx.correlation_id = ctx.root_execution_id

        if ctx.idempotency_key:
            if not self._store.register_idempotency(
                ctx.idempotency_key, ctx.execution_id, ctx.timestamp
            ):
                dup = self._store.get_execution_by_idempotency(ctx.idempotency_key)
                if not dup:
                    raise SqubeIdempotencyConflictError(
                        ctx.idempotency_key, ctx.execution_id
                    )
                prior_id = dup["execution_id"]
                status = dup.get("status")
                if status == ActionStatus.SUCCEEDED.value:
                    raise SqubeIdempotencyReplayError(prior_id)
                if status == ActionStatus.BLOCKED.value:
                    raise SqubeBlockedError(prior_id, dup.get("action", ctx.action))
                raise SqubeIdempotencyConflictError(ctx.idempotency_key, prior_id)

        params_hash = hash_payload(ctx.parameters)
        summary = redact_value(ctx.parameters)

        record = ActionRecord(
            execution_id=ctx.execution_id,
            created_at=ctx.timestamp,
            agent_id=ctx.agent.agent_id,
            action=ctx.action,
            resource=ctx.resource,
            parameters_hash=params_hash,
            parameters_summary=summary,
            decision=Decision.ALLOW.value,
            policy_id=self._policy.metadata.policy_id,
            status=ActionStatus.REQUESTED.value,
            correlation_id=ctx.correlation_id,
            parent_execution_id=ctx.parent_execution_id,
            root_execution_id=ctx.root_execution_id,
            session_id=ctx.session_id,
        )
        self._store.upsert_execution_record(record)
        self._record_event(
            ctx.execution_id,
            EventType.ACTION_REQUESTED,
            ctx.agent.agent_id,
            {"action": ctx.action, "resource": ctx.resource},
            ctx.timestamp,
        )

        try:
            self._check_delegation(ctx)
        except SqubeGuardError:
            self._finalize_blocked(
                ctx, "delegation denied", from_status=ActionStatus.REQUESTED.value
            )
            raise

        self._record_event(
            ctx.execution_id,
            EventType.CONTEXT_RESOLVED,
            ctx.agent.agent_id,
            {
                "principal": ctx.principal.id if ctx.principal else None,
                "correlation_id": ctx.correlation_id,
                "root_execution_id": ctx.root_execution_id,
            },
            _utc_now_iso(),
        )
        self._transition(
            ctx.execution_id,
            ActionStatus.REQUESTED.value,
            ActionStatus.EVALUATED.value,
        )

        try:
            evaluation = self._policy.evaluate(ctx)
        except Exception as exc:
            return self._handle_policy_error(ctx, fn, exc)

        self._store.update_execution_record(
            ctx.execution_id,
            decision=evaluation.decision.value,
            policy_id=evaluation.policy_id,
            policy_version=evaluation.policy_version,
        )
        self._record_event(
            ctx.execution_id,
            EventType.POLICY_EVALUATED,
            "policy",
            {
                "decision": evaluation.decision.value,
                "policy_id": evaluation.policy_id,
                "policy_version": evaluation.policy_version,
                "reason": evaluation.reason,
            },
            _utc_now_iso(),
        )

        if evaluation.decision == Decision.BLOCK:
            self._finalize_blocked(ctx, evaluation.reason)
            raise SqubeBlockedError(ctx.execution_id, ctx.action)

        if evaluation.decision == Decision.REQUIRE_APPROVAL:
            if self._approval_mode == "deferred":
                return self._deferred_approval_path(
                    ctx, evaluation, summary, params_hash
                )
            return self._approval_path(ctx, fn, evaluation, summary, params_hash)

        return self._begin_execute(ctx, fn, from_status=ActionStatus.EVALUATED.value)

    def resume_after_approval(
        self,
        ctx: ExecutionContext,
        fn: Callable[[], Any],
        *,
        approval_id: str,
    ) -> Any:
        row = self._store.get_execution(ctx.execution_id)
        if not row:
            raise SqubeGuardError(f"unknown execution {ctx.execution_id}")
        if row["status"] == ActionStatus.WAITING_APPROVAL.value:
            raise SqubeApprovalPendingError(ctx.execution_id, approval_id)
        if row["status"] in (
            ActionStatus.DENIED.value,
            ActionStatus.EXPIRED.value,
            ActionStatus.BLOCKED.value,
            ActionStatus.CANCELLED.value,
        ):
            raise SqubeDeniedError(ctx.execution_id, row["status"])
        if hash_payload(ctx.parameters) != row["parameters_hash"]:
            raise SqubeGuardError("parameters changed after authorization")
        approval = self._store.get_approval(approval_id)
        if not approval or approval.execution_id != ctx.execution_id:
            raise SqubeGuardError(f"unknown approval {approval_id}")
        now = _utc_now_iso()
        if approval.expires_at and approval.expires_at < now:
            raise SqubeDeniedError(ctx.execution_id, "approval_expired")
        self._store.consume_approval_for_execution(
            approval_id, ctx.execution_id, now
        )
        self._record_event(
            ctx.execution_id,
            EventType.ACTION_STARTED,
            ctx.agent.agent_id,
            {"approval_id": approval_id},
            now,
        )
        return self._run_fn_body(ctx, fn)

    def cancel_execution(self, execution_id: str, *, reason: str = "cancelled") -> None:
        row = self._store.get_execution(execution_id)
        if not row:
            raise SqubeGuardError(f"unknown execution {execution_id}")
        status = row["status"]
        now = _utc_now_iso()
        if status == ActionStatus.WAITING_APPROVAL.value:
            self._transition(
                execution_id,
                ActionStatus.WAITING_APPROVAL.value,
                ActionStatus.CANCELLED.value,
                completed_at=now,
                approval_reason=reason,
            )
            self._record_event(
                execution_id,
                EventType.ACTION_CANCELLED,
                "operator",
                {"reason": reason},
                now,
            )
            return
        if status == ActionStatus.APPROVED.value:
            self._transition(
                execution_id,
                ActionStatus.APPROVED.value,
                ActionStatus.CANCELLED.value,
                completed_at=now,
                approval_reason=reason,
            )
            self._record_event(
                execution_id,
                EventType.ACTION_CANCELLED,
                "operator",
                {"reason": reason},
                now,
            )
            return
        raise SqubeInvalidStateTransitionError(status, ActionStatus.CANCELLED.value)

    def _deferred_approval_path(
        self,
        ctx: ExecutionContext,
        evaluation: PolicyEvaluation,
        summary: str,
        params_hash: str,
    ) -> Any:
        approval_id = f"sq_apr_{uuid.uuid4().hex[:12]}"
        now = _utc_now_iso()
        expires = (
            datetime.now(timezone.utc) + timedelta(seconds=self._approval_timeout)
        ).replace(microsecond=0).isoformat()
        self._transition(
            ctx.execution_id,
            ActionStatus.EVALUATED.value,
            ActionStatus.WAITING_APPROVAL.value,
        )
        self._store.create_approval_request(
            approval_id,
            ctx.execution_id,
            params_hash,
            now,
            expires,
        )
        self._record_event(
            ctx.execution_id,
            EventType.APPROVAL_REQUESTED,
            ctx.agent.agent_id,
            {"approval_id": approval_id, "expires_at": expires, "summary": summary},
            now,
        )
        raise SqubeApprovalPendingError(ctx.execution_id, approval_id)

    def _approval_path(
        self,
        ctx: ExecutionContext,
        fn: Callable[[], Any],
        evaluation: PolicyEvaluation,
        summary: str,
        params_hash: str,
    ) -> Any:
        from sqube_agent_guard.approval.provider import ApprovalRequest

        self._transition(
            ctx.execution_id,
            ActionStatus.EVALUATED.value,
            ActionStatus.WAITING_APPROVAL.value,
        )
        self._record_event(
            ctx.execution_id,
            EventType.APPROVAL_REQUESTED,
            ctx.agent.agent_id,
            {},
            _utc_now_iso(),
        )
        approval_id = f"sq_apr_{uuid.uuid4().hex[:12]}"
        approved, approved_by, reason = self._approval.request(
            ApprovalRequest(
                approval_id=approval_id,
                execution_id=ctx.execution_id,
                requested_at=_utc_now_iso(),
                expires_at=None,
                action=ctx.action,
                resource=ctx.resource,
                parameters_hash=params_hash,
                policy_version=evaluation.policy_version,
                summary=summary,
                metadata={"agent_id": ctx.agent.agent_id},
            ),
            self._approval_timeout,
        )
        if not approved:
            denied_at = _utc_now_iso()
            if reason == "timeout":
                self._transition(
                    ctx.execution_id,
                    ActionStatus.WAITING_APPROVAL.value,
                    ActionStatus.EXPIRED.value,
                    approval_reason=reason,
                    completed_at=denied_at,
                )
                event = EventType.APPROVAL_EXPIRED
            else:
                self._transition(
                    ctx.execution_id,
                    ActionStatus.WAITING_APPROVAL.value,
                    ActionStatus.DENIED.value,
                    approval_reason=reason,
                    completed_at=denied_at,
                )
                event = EventType.APPROVAL_DENIED
            self._record_event(
                ctx.execution_id, event, "human", {"reason": reason}, denied_at
            )
            raise SqubeDeniedError(ctx.execution_id, reason or "denied")

        self._transition(
            ctx.execution_id,
            ActionStatus.WAITING_APPROVAL.value,
            ActionStatus.APPROVED.value,
            approved_by=approved_by,
        )
        self._record_event(
            ctx.execution_id,
            EventType.APPROVAL_GRANTED,
            approved_by or "cli_user",
            {},
            _utc_now_iso(),
        )
        return self._begin_execute(ctx, fn, from_status=ActionStatus.APPROVED.value)

    def _finalize_blocked(
        self,
        ctx: ExecutionContext,
        reason: str,
        *,
        from_status: str = ActionStatus.EVALUATED.value,
    ) -> None:
        self._transition(
            ctx.execution_id,
            from_status,
            ActionStatus.BLOCKED.value,
            completed_at=_utc_now_iso(),
        )
        self._record_event(
            ctx.execution_id,
            EventType.ACTION_BLOCKED,
            "policy",
            {"reason": reason},
            _utc_now_iso(),
        )

    def _handle_policy_error(
        self, ctx: ExecutionContext, fn: Callable[[], Any], error: Exception
    ) -> Any:
        if self._on_error == "fail_open":
            return self._begin_execute(ctx, fn, from_status=ActionStatus.EVALUATED.value)
        self._transition(
            ctx.execution_id,
            ActionStatus.EVALUATED.value,
            ActionStatus.FAILED.value,
            error_message=f"policy_error: {error}",
            completed_at=_utc_now_iso(),
        )
        raise SqubeGuardError(f"Policy evaluation failed: {error}") from error

    def _begin_execute(
        self, ctx: ExecutionContext, fn: Callable[[], Any], *, from_status: str
    ) -> Any:
        self._transition(
            ctx.execution_id,
            from_status,
            ActionStatus.EXECUTING.value,
        )
        self._record_event(
            ctx.execution_id,
            EventType.ACTION_STARTED,
            ctx.agent.agent_id,
            {},
            _utc_now_iso(),
        )
        return self._run_fn_body(ctx, fn)

    def _run_fn_body(self, ctx: ExecutionContext, fn: Callable[[], Any]) -> Any:
        start = time.perf_counter()
        try:
            result = self._with_interceptors(ctx, fn)()
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            failed_at = _utc_now_iso()
            self._transition(
                ctx.execution_id,
                ActionStatus.EXECUTING.value,
                ActionStatus.FAILED.value,
                result_status="FAILED",
                error_message=str(exc),
                duration_ms=duration_ms,
                completed_at=failed_at,
            )
            self._record_event(
                ctx.execution_id,
                EventType.ACTION_FAILED,
                ctx.agent.agent_id,
                {"error": str(exc)},
                failed_at,
            )
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        done_at = _utc_now_iso()
        self._transition(
            ctx.execution_id,
            ActionStatus.EXECUTING.value,
            ActionStatus.SUCCEEDED.value,
            result_status="SUCCESS",
            duration_ms=duration_ms,
            completed_at=done_at,
        )
        self._record_event(
            ctx.execution_id,
            EventType.ACTION_SUCCEEDED,
            ctx.agent.agent_id,
            {},
            done_at,
        )
        return result

    def _with_interceptors(
        self, ctx: ExecutionContext, fn: Callable[[], Any]
    ) -> Callable[[], Any]:
        chain: Callable[[], Any] = fn
        for interceptor in reversed(self._interceptors):
            inner = chain

            def chain(
                i: ExecutionInterceptor = interceptor,
                inner: Callable[[], Any] = inner,
            ) -> Any:
                return i.intercept(ctx, inner)

        return chain


def context_from_wrap(
    *,
    execution_id: str,
    agent_id: str,
    action: str,
    resource: str | None,
    parameters: dict[str, Any],
    environment: str | None = None,
    delegation_chain: tuple[Delegation, ...] = (),
    idempotency_key: str | None = None,
    principal_type: str | None = None,
    principal_id: str | None = None,
) -> ExecutionContext:
    from sqube_agent_guard.identity.models import Principal

    principal = None
    if principal_type and principal_id:
        principal = Principal(type=principal_type, id=principal_id)
    return ExecutionContext(
        execution_id=execution_id,
        agent=AgentIdentity(agent_id=agent_id, environment=environment),
        action=action,
        resource=resource,
        parameters=parameters,
        environment=environment,
        delegation_chain=delegation_chain,
        idempotency_key=idempotency_key,
        principal=principal,
    )
