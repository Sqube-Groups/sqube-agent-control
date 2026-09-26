from __future__ import annotations

import json
from pathlib import Path

import pytest

from sqube_agent_guard.exceptions import SqubeInvalidStateTransitionError
from sqube_agent_guard.execution.state_machine import ALLOWED_TRANSITIONS, TERMINAL_STATUSES, assert_transition
from sqube_agent_guard.models import ActionStatus

FIXTURE = Path(__file__).parent / "v1_semantics.json"


def test_python_state_machine_matches_contract() -> None:
    data = json.loads(FIXTURE.read_text())
    contract_allowed = {
        (a, b) for a, b in data["allowed_transitions"]
    }
    impl_allowed = {(a.value, b.value) for a, b in ALLOWED_TRANSITIONS}
    assert contract_allowed == impl_allowed
    contract_terminal = set(data["terminal_statuses"])
    impl_terminal = {s.value for s in TERMINAL_STATUSES}
    assert contract_terminal == impl_terminal


@pytest.mark.parametrize("from_status,to_status", json.loads(FIXTURE.read_text())["illegal_transitions"])
def test_contract_illegal_transitions(from_status: str, to_status: str) -> None:
    with pytest.raises(SqubeInvalidStateTransitionError):
        assert_transition(ActionStatus(from_status), ActionStatus(to_status))
