class SqubeBlockedError(Exception):
    """Raised when policy decision is BLOCK."""

    def __init__(self, execution_id: str, action: str) -> None:
        self.execution_id = execution_id
        self.action = action
        super().__init__(f"Action '{action}' blocked (execution_id={execution_id})")


class SqubeDeniedError(Exception):
    """Raised when approval was denied or expired."""

    def __init__(self, execution_id: str, reason: str) -> None:
        self.execution_id = execution_id
        self.reason = reason
        super().__init__(f"Action denied: {reason} (execution_id={execution_id})")


class SqubeGuardError(Exception):
    """Raised on guard failures in fail_closed mode."""


class SqubeInvalidStateTransitionError(SqubeGuardError):
    def __init__(
        self, from_status: str, to_status: str, *, execution_id: str | None = None
    ) -> None:
        self.from_status = from_status
        self.to_status = to_status
        self.execution_id = execution_id
        suffix = f" (execution_id={execution_id})" if execution_id else ""
        super().__init__(
            f"Invalid execution transition {from_status} -> {to_status}{suffix}"
        )


class SqubeApprovalPendingError(SqubeGuardError):
    """Execution is waiting for a deferred human approval."""

    def __init__(self, execution_id: str, approval_id: str) -> None:
        self.execution_id = execution_id
        self.approval_id = approval_id
        super().__init__(
            f"Approval pending (approval_id={approval_id}, execution_id={execution_id})"
        )


class SqubeApprovalError(SqubeGuardError):
    """Approval could not be applied (already decided, expired, or consumed)."""

    def __init__(self, approval_id: str, reason: str) -> None:
        self.approval_id = approval_id
        self.reason = reason
        super().__init__(f"Approval {approval_id}: {reason}")


class SqubeIdempotencyConflictError(Exception):
    """Raised when the same idempotency key is used while a prior run is still active."""

    def __init__(self, idempotency_key: str, execution_id: str) -> None:
        self.idempotency_key = idempotency_key
        self.execution_id = execution_id
        super().__init__(
            f"Idempotency key in use (key={idempotency_key}, execution_id={execution_id})"
        )


class SqubeIdempotencyReplayError(Exception):
    """Raised when a completed execution is replayed via idempotency key (result not stored)."""

    def __init__(self, execution_id: str) -> None:
        self.execution_id = execution_id
        super().__init__(
            f"Execution already completed (execution_id={execution_id}); "
            "fetch ledger record for outcome"
        )
