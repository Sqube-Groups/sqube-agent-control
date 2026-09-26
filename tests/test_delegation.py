from __future__ import annotations

import pytest

from sqube_agent_guard.authority.delegation import Delegation
from sqube_agent_guard.exceptions import SqubeGuardError
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.policy.engine import CallablePolicy
from sqube_agent_guard.policy import default_policy


def test_delegation_scope_enforced(tmp_path) -> None:
    engine = ExecutionEngine(
        policy=CallablePolicy(default_policy),
        ledger_path=str(tmp_path / "ledger.sqlite3"),
    )
    delegation = Delegation(
        delegation_id="d1",
        delegator="human",
        delegate="bot",
        scope=frozenset({"file.read"}),
        created_at="2020-01-01T00:00:00+00:00",
    )
    ctx = ExecutionContext(
        execution_id="sq_exec_del",
        agent=AgentIdentity(agent_id="bot"),
        action="file.delete",
        resource="file:/tmp/x",
        parameters={},
        delegation_chain=(delegation,),
    )
    with pytest.raises(SqubeGuardError, match="delegation"):
        engine.run_controlled(ctx, lambda: 1)
