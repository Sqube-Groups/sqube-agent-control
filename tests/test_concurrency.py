from __future__ import annotations

import pytest

from sqube_agent_guard.exceptions import SqubeApprovalError, SqubeApprovalPendingError
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.ledger.store import SQLiteExecutionStore
from sqube_agent_guard.models import Decision
from sqube_agent_guard.policy.engine import CallablePolicy


def _require(action: str, *_a, **_k) -> Decision:
    return Decision.REQUIRE_APPROVAL


def test_approval_consume_only_once(tmp_path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(
        policy=CallablePolicy(_require),
        ledger_path=ledger,
        approval_mode="deferred",
    )
    ctx = ExecutionContext(
        execution_id="sq_exec_conc",
        agent=AgentIdentity(agent_id="bot"),
        action="send_email",
        resource=None,
        parameters={},
    )
    with pytest.raises(SqubeApprovalPendingError) as pending:
        engine.run_controlled(ctx, lambda: "ok")
    approval_id = pending.value.approval_id
    store = SQLiteExecutionStore(ledger)
    store.grant_approval(approval_id, "human", "2026-01-02T00:00:00+00:00")

    assert (
        engine.resume_after_approval(ctx, lambda: "ok", approval_id=approval_id)
        == "ok"
    )
    with pytest.raises(SqubeApprovalError, match="consumed|GRANTED"):
        engine.resume_after_approval(ctx, lambda: "ok", approval_id=approval_id)
