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
