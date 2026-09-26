from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class ActionStatus(str, Enum):
    REQUESTED = "REQUESTED"
    EVALUATED = "EVALUATED"
    BLOCKED = "BLOCKED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ActionRecord:
    execution_id: str
    created_at: str
    agent_id: str
    action: str
    resource: str | None
    parameters_hash: str
    parameters_summary: str | None
    decision: str
    policy_id: str
    status: str
    policy_version: str | None = None
    approved_by: str | None = None
    approval_reason: str | None = None
    result_status: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    completed_at: str | None = None
    correlation_id: str | None = None
    parent_execution_id: str | None = None
    root_execution_id: str | None = None
    session_id: str | None = None

    def to_row(self) -> dict[str, Any]:
        return asdict(self)
