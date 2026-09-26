from __future__ import annotations

import json
from pathlib import Path

import pytest

from sqube_agent_guard.exceptions import SqubeApprovalPendingError
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.ledger.store import SQLiteExecutionStore
from sqube_agent_guard.models import ActionStatus, Decision
from sqube_agent_guard.policy.engine import CallablePolicy

FIXTURE = Path(__file__).parent / "deferred_approval.json"


def _require_email(action: str, *_a, **_k) -> Decision:
    if action == "send_email":
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW


def test_deferred_approval_contract_scenario(tmp_path: Path) -> None:
    data = json.loads(FIXTURE.read_text())
    ctx_data = data["context"]
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(
        policy=CallablePolicy(_require_email),
        ledger_path=ledger,
        approval_mode="deferred",
    )
    ctx = ExecutionContext(
        execution_id="sq_exec_contract_def",
        agent=AgentIdentity(agent_id=ctx_data["agent_id"]),
        action=ctx_data["action"],
        resource=ctx_data.get("resource"),
        parameters=ctx_data.get("parameters") or {},
    )
    with pytest.raises(SqubeApprovalPendingError) as pending:
        engine.run_controlled(ctx, lambda: data["resume_result"])
    store = SQLiteExecutionStore(ledger)
    assert (
        store.get_execution(ctx.execution_id)["status"]
        == data["expected_after_pending_status"]
    )
    store.grant_approval(pending.value.approval_id, "human", data["grant_at"])
    assert (
        store.get_execution(ctx.execution_id)["status"]
        == data["expected_after_grant_status"]
    )
    result = engine.resume_after_approval(
        ctx, lambda: data["resume_result"], approval_id=pending.value.approval_id
    )
    assert result == data["resume_result"]
    assert store.get_execution(ctx.execution_id)["status"] == data["expected_final_status"]
