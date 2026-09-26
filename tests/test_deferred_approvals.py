from __future__ import annotations

import pytest

from sqube_agent_guard.exceptions import (
    SqubeApprovalError,
    SqubeApprovalPendingError,
    SqubeDeniedError,
    SqubeGuardError,
)
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.ledger.store import SQLiteExecutionStore
from sqube_agent_guard.models import ActionStatus, Decision
from sqube_agent_guard.policy.engine import CallablePolicy


def _require_email(action: str, *_a, **_k) -> Decision:
    if action == "send_email":
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW


def _ctx(execution_id: str = "sq_exec_def") -> ExecutionContext:
    return ExecutionContext(
        execution_id=execution_id,
        agent=AgentIdentity(agent_id="agent"),
        action="send_email",
        resource="a@b.com",
        parameters={"to": "a@b.com"},
    )


def test_deferred_approval_grant_resume(tmp_path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(
        policy=CallablePolicy(_require_email),
        ledger_path=ledger,
        approval_mode="deferred",
    )
    ctx = _ctx()
    with pytest.raises(SqubeApprovalPendingError) as pending:
        engine.run_controlled(ctx, lambda: "sent")
    approval_id = pending.value.approval_id
    store = SQLiteExecutionStore(ledger)
    store.grant_approval(approval_id, "human", "2026-01-02T00:00:00+00:00")
    assert store.get_execution(ctx.execution_id)["status"] == ActionStatus.APPROVED.value
    result = engine.resume_after_approval(ctx, lambda: "sent", approval_id=approval_id)
    assert result == "sent"
    assert store.get_execution(ctx.execution_id)["status"] == ActionStatus.SUCCEEDED.value


def test_denied_cannot_resume(tmp_path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(
        policy=CallablePolicy(_require_email),
        ledger_path=ledger,
        approval_mode="deferred",
    )
    ctx = _ctx("sq_exec_denied")
    with pytest.raises(SqubeApprovalPendingError) as pending:
        engine.run_controlled(ctx, lambda: 1)
    approval_id = pending.value.approval_id
    store = SQLiteExecutionStore(ledger)
    store.deny_approval(approval_id, "human", "no", "2026-01-02T00:00:00+00:00")
    with pytest.raises(SqubeDeniedError):
        engine.resume_after_approval(ctx, lambda: 1, approval_id=approval_id)


def test_resume_rejects_parameter_tamper(tmp_path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(
        policy=CallablePolicy(_require_email),
        ledger_path=ledger,
        approval_mode="deferred",
    )
    ctx = _ctx("sq_exec_tamper")
    with pytest.raises(SqubeApprovalPendingError) as pending:
        engine.run_controlled(ctx, lambda: 1)
    approval_id = pending.value.approval_id
    store = SQLiteExecutionStore(ledger)
    store.grant_approval(approval_id, "human", "2026-01-02T00:00:00+00:00")
    ctx.parameters = {"to": "evil@example.com"}
    with pytest.raises(SqubeGuardError, match="parameters changed"):
        engine.resume_after_approval(ctx, lambda: 1, approval_id=approval_id)


def test_double_grant_race(tmp_path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(
        policy=CallablePolicy(_require_email),
        ledger_path=ledger,
        approval_mode="deferred",
    )
    ctx = _ctx("sq_exec_race")
    with pytest.raises(SqubeApprovalPendingError) as pending:
        engine.run_controlled(ctx, lambda: 1)
    approval_id = pending.value.approval_id
    store = SQLiteExecutionStore(ledger)
    store.grant_approval(approval_id, "a", "2026-01-02T00:00:00+00:00")
    with pytest.raises(SqubeApprovalError):
        store.grant_approval(approval_id, "b", "2026-01-02T00:00:01+00:00")
