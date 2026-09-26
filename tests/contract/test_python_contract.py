from __future__ import annotations

import json
from pathlib import Path

import pytest

from sqube_agent_guard.execution.engine import ExecutionEngine, context_from_wrap
from sqube_agent_guard.policy import default_policy
from sqube_agent_guard.policy.engine import CallablePolicy

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")))
def test_fixture_decision(path: Path) -> None:
    data = json.loads(path.read_text())
    engine = ExecutionEngine(policy=CallablePolicy(default_policy))
    ctx = context_from_wrap(
        execution_id="sq_exec_contract",
        agent_id=data["context"]["agent_id"],
        action=data["context"]["action"],
        resource=data["context"].get("resource"),
        parameters={},
    )
    result = engine.simulate(ctx)
    assert result.decision.value == data["expected_decision"], data["name"]
