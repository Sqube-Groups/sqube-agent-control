from __future__ import annotations

import pytest

from sqube_agent_guard.exceptions import (
    SqubeBlockedError,
    SqubeIdempotencyConflictError,
    SqubeIdempotencyReplayError,
)
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.models import ActionRecord, ActionStatus


def _ctx(execution_id: str, key: str) -> ExecutionContext:
    return ExecutionContext(
        execution_id=execution_id,
        agent=AgentIdentity(agent_id="default"),
        action="read",
        resource="file:/tmp/x",
        parameters={},
        idempotency_key=key,
    )


def test_idempotency_replay_after_success(tmp_path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(ledger_path=ledger)
    key = "idem-1"
    c1 = _ctx("sq_exec_a", key)
    assert engine.run_controlled(c1, lambda: 42) == 42

    c2 = _ctx("sq_exec_b", key)
    with pytest.raises(SqubeIdempotencyReplayError) as exc:
        engine.run_controlled(c2, lambda: 99)
    assert exc.value.execution_id == "sq_exec_a"


def test_idempotency_conflict_while_in_flight(tmp_path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(ledger_path=ledger)
    key = "idem-2"
    c1 = _ctx("sq_exec_c", key)
    engine._store.register_idempotency(key, c1.execution_id, "2020-01-01T00:00:00+00:00")
    engine._store.upsert_execution_record(
        ActionRecord(
            execution_id=c1.execution_id,
            created_at="2020-01-01T00:00:00+00:00",
            agent_id="default",
            action="read",
            resource=None,
            parameters_hash="x",
            parameters_summary=None,
            decision="ALLOW",
            policy_id="default",
            status=ActionStatus.EXECUTING.value,
        )
    )
    c2 = _ctx("sq_exec_d", key)
    with pytest.raises(SqubeIdempotencyConflictError):
        engine.run_controlled(c2, lambda: 1)


def test_idempotency_blocked_replay(tmp_path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    engine = ExecutionEngine(ledger_path=ledger)
    key = "idem-3"
    c_admin = ExecutionContext(
        execution_id="sq_exec_f",
        agent=AgentIdentity(agent_id="default"),
        action="admin_delete",
        resource="system",
        parameters={},
        idempotency_key=key,
    )
    with pytest.raises(SqubeBlockedError):
        engine.run_controlled(c_admin, lambda: 1)

    c2 = ExecutionContext(
        execution_id="sq_exec_g",
        agent=AgentIdentity(agent_id="default"),
        action="admin_delete",
        resource="system",
        parameters={},
        idempotency_key=key,
    )
    with pytest.raises(SqubeBlockedError) as exc:
        engine.run_controlled(c2, lambda: 1)
    assert exc.value.execution_id == "sq_exec_f"
