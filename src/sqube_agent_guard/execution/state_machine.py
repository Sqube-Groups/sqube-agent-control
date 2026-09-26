"""Execution status transitions (v1 release hardening)."""

from __future__ import annotations

from sqube_agent_guard.exceptions import SqubeInvalidStateTransitionError
from sqube_agent_guard.models import ActionStatus

TERMINAL_STATUSES = frozenset(
    {
        ActionStatus.BLOCKED,
        ActionStatus.DENIED,
        ActionStatus.EXPIRED,
        ActionStatus.SUCCEEDED,
        ActionStatus.FAILED,
        ActionStatus.CANCELLED,
    }
)

ALLOWED_TRANSITIONS: frozenset[tuple[ActionStatus, ActionStatus]] = frozenset(
    {
        (ActionStatus.REQUESTED, ActionStatus.EVALUATED),
        (ActionStatus.REQUESTED, ActionStatus.BLOCKED),
        (ActionStatus.REQUESTED, ActionStatus.FAILED),
        (ActionStatus.EVALUATED, ActionStatus.BLOCKED),
        (ActionStatus.EVALUATED, ActionStatus.WAITING_APPROVAL),
        (ActionStatus.EVALUATED, ActionStatus.EXECUTING),
        (ActionStatus.EVALUATED, ActionStatus.FAILED),
        (ActionStatus.WAITING_APPROVAL, ActionStatus.APPROVED),
        (ActionStatus.WAITING_APPROVAL, ActionStatus.DENIED),
        (ActionStatus.WAITING_APPROVAL, ActionStatus.EXPIRED),
        (ActionStatus.WAITING_APPROVAL, ActionStatus.CANCELLED),
        (ActionStatus.APPROVED, ActionStatus.EXECUTING),
        (ActionStatus.APPROVED, ActionStatus.CANCELLED),
        (ActionStatus.EXECUTING, ActionStatus.SUCCEEDED),
        (ActionStatus.EXECUTING, ActionStatus.FAILED),
        (ActionStatus.EXECUTING, ActionStatus.CANCELLED),
    }
)


def assert_transition(
    from_status: ActionStatus | str,
    to_status: ActionStatus | str,
    *,
    execution_id: str | None = None,
) -> None:
    from_enum = (
        from_status
        if isinstance(from_status, ActionStatus)
        else ActionStatus(str(from_status))
    )
    to_enum = (
        to_status
        if isinstance(to_status, ActionStatus)
        else ActionStatus(str(to_status))
    )
    if from_enum == to_enum:
        raise SqubeInvalidStateTransitionError(
            from_enum.value, to_enum.value, execution_id=execution_id
        )
    if from_enum in TERMINAL_STATUSES:
        raise SqubeInvalidStateTransitionError(
            from_enum.value, to_enum.value, execution_id=execution_id
        )
    if (from_enum, to_enum) not in ALLOWED_TRANSITIONS:
        raise SqubeInvalidStateTransitionError(
            from_enum.value, to_enum.value, execution_id=execution_id
        )


def is_terminal(status: ActionStatus | str) -> bool:
    st = status if isinstance(status, ActionStatus) else ActionStatus(str(status))
    return st in TERMINAL_STATUSES
