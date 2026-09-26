"""P0 correctness tests: expiry, cancel, tamper, CAS transitions, approval races."""

from __future__ import annotations

import multiprocessing as mp
import sqlite3
from pathlib import Path

import pytest

from sqube_agent_guard.exceptions import (
    SqubeApprovalError,
    SqubeApprovalPendingError,
    SqubeDeniedError,
    SqubeInvalidStateTransitionError,
)
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.ledger.events import EventType
from sqube_agent_guard.ledger.store import SQLiteExecutionStore
from sqube_agent_guard.models import ActionRecord, ActionStatus, Decision
from sqube_agent_guard.policy.engine import CallablePolicy


def _require_email(action: str, *_a, **_k) -> Decision:
    if action == "send_email":
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW


def _ctx(execution_id: str = "sq_exec_p0") -> ExecutionContext:
    return ExecutionContext(
        execution_id=execution_id,
        agent=AgentIdentity(agent_id="agent"),
        action="send_email",
        resource="a@b.com",
        parameters={"to": "a@b.com"},
    )


def test_resume_rejects_expired_approval_without_executing(tmp_path: Path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(
        policy=CallablePolicy(_require_email),
        ledger_path=ledger,
        approval_mode="deferred",
    )
    ctx = _ctx("sq_exec_expired_resume")
    with pytest.raises(SqubeApprovalPendingError) as pending:
        engine.run_controlled(ctx, lambda: (_ for _ in ()).throw(RuntimeError("must not run")))
    approval_id = pending.value.approval_id
    store = SQLiteExecutionStore(ledger)
    store.grant_approval(approval_id, "human", "2026-01-02T00:00:00+00:00")

    conn = sqlite3.connect(ledger)
    conn.execute(
        "UPDATE approval_requests SET expires_at = ? WHERE approval_id = ?",
        ("2020-01-01T00:00:00+00:00", approval_id),
    )
    conn.commit()
    conn.close()

    ran = {"value": False}

    def body() -> str:
        ran["value"] = True
        return "sent"

    with pytest.raises(SqubeDeniedError, match="approval_expired"):
        engine.resume_after_approval(ctx, body, approval_id=approval_id)
    assert ran["value"] is False
    assert store.get_execution(ctx.execution_id)["status"] == ActionStatus.APPROVED.value


def test_cancel_waiting_execution_blocks_resume(tmp_path: Path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(
        policy=CallablePolicy(_require_email),
        ledger_path=ledger,
        approval_mode="deferred",
    )
    ctx = _ctx("sq_exec_cancel")
    with pytest.raises(SqubeApprovalPendingError) as pending:
        engine.run_controlled(ctx, lambda: "x")
    approval_id = pending.value.approval_id
    store = SQLiteExecutionStore(ledger)
    engine.cancel_execution(ctx.execution_id, reason="operator_stop")
    assert store.get_execution(ctx.execution_id)["status"] == ActionStatus.CANCELLED.value
    ran = {"value": False}

    def body() -> str:
        ran["value"] = True
        return "x"

    with pytest.raises(SqubeDeniedError, match="CANCELLED"):
        engine.resume_after_approval(ctx, body, approval_id=approval_id)
    assert ran["value"] is False


def test_ledger_tamper_fails_verify_chain(tmp_path: Path) -> None:
    db = str(tmp_path / "tamper.sqlite3")
    store = SQLiteExecutionStore(db)
    store.append_event("e-tamper", EventType.ACTION_REQUESTED, "agent", {"a": 1}, "t1")
    store.append_event("e-tamper", EventType.POLICY_EVALUATED, "policy", {"d": "ALLOW"}, "t2")
    assert store.verify_chain("e-tamper") is True

    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE execution_events SET event_hash = ? WHERE execution_id = ?",
        ("0" * 64, "e-tamper"),
    )
    conn.commit()
    conn.close()
    assert store.verify_chain("e-tamper") is False


def test_store_transition_cas_rejects_stale_from_status(tmp_path: Path) -> None:
    store = SQLiteExecutionStore(str(tmp_path / "cas.sqlite3"))
    store.upsert_execution_record(
        ActionRecord(
            execution_id="sq_exec_cas",
            created_at="t",
            agent_id="bot",
            action="read",
            resource=None,
            parameters_hash="h",
            parameters_summary=None,
            decision=Decision.ALLOW.value,
            policy_id="default",
            status=ActionStatus.APPROVED.value,
        )
    )
    with pytest.raises(SqubeInvalidStateTransitionError) as err:
        store.transition_execution(
            "sq_exec_cas",
            ActionStatus.EVALUATED.value,
            ActionStatus.EXECUTING.value,
        )
    assert "APPROVED" in str(err.value) or err.value.from_status == ActionStatus.APPROVED.value


def test_double_deny_race(tmp_path: Path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(
        policy=CallablePolicy(_require_email),
        ledger_path=ledger,
        approval_mode="deferred",
    )
    ctx = _ctx("sq_exec_deny_race")
    with pytest.raises(SqubeApprovalPendingError) as pending:
        engine.run_controlled(ctx, lambda: 1)
    approval_id = pending.value.approval_id
    store = SQLiteExecutionStore(ledger)
    store.deny_approval(approval_id, "a", "no", "2026-01-02T00:00:00+00:00")
    with pytest.raises(SqubeApprovalError, match="status is DENIED"):
        store.deny_approval(approval_id, "b", "no again", "2026-01-02T00:00:01+00:00")


def _grant_worker(ledger_path: str, approval_id: str, operator: str) -> str:
    store = SQLiteExecutionStore(ledger_path)
    try:
        store.grant_approval(approval_id, operator, "2026-01-02T00:00:00+00:00")
        return "granted"
    except SqubeApprovalError as exc:
        return f"error:{exc}"


def test_multiprocess_grant_race_single_winner(tmp_path: Path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(
        policy=CallablePolicy(_require_email),
        ledger_path=ledger,
        approval_mode="deferred",
    )
    ctx = _ctx("sq_exec_mp_grant")
    with pytest.raises(SqubeApprovalPendingError) as pending:
        engine.run_controlled(ctx, lambda: 1)
    approval_id = pending.value.approval_id

    with mp.Pool(2) as pool:
        results = pool.starmap(
            _grant_worker,
            [
                (ledger, approval_id, "op_a"),
                (ledger, approval_id, "op_b"),
            ],
        )
    assert results.count("granted") == 1
    assert sum(1 for r in results if r.startswith("error:")) == 1
