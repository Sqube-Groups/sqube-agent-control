from __future__ import annotations

import pytest

from sqube_agent_guard.exceptions import SqubeInvalidStateTransitionError
from sqube_agent_guard.execution.state_machine import assert_transition
from sqube_agent_guard.models import ActionStatus


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ActionStatus.BLOCKED, ActionStatus.EXECUTING),
        (ActionStatus.DENIED, ActionStatus.EXECUTING),
        (ActionStatus.EXPIRED, ActionStatus.EXECUTING),
        (ActionStatus.SUCCEEDED, ActionStatus.EXECUTING),
        (ActionStatus.SUCCEEDED, ActionStatus.SUCCEEDED),
        (ActionStatus.WAITING_APPROVAL, ActionStatus.SUCCEEDED),
    ],
)
def test_illegal_transitions(from_status: ActionStatus, to_status: ActionStatus) -> None:
    with pytest.raises(SqubeInvalidStateTransitionError):
        assert_transition(from_status, to_status)


def test_legal_allow_path() -> None:
    assert_transition(ActionStatus.EVALUATED, ActionStatus.EXECUTING)
    assert_transition(ActionStatus.EXECUTING, ActionStatus.SUCCEEDED)
