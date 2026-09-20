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
