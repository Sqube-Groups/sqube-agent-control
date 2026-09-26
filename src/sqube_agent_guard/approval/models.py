from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ApprovalRequestStatus(str, Enum):
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    execution_id: str
    status: ApprovalRequestStatus
    parameters_hash: str
    requested_at: str
    expires_at: str | None
    decided_at: str | None = None
    decided_by: str | None = None
    decision_reason: str | None = None
