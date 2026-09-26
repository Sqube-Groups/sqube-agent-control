from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EventType(str, Enum):
    ACTION_REQUESTED = "ACTION_REQUESTED"
    CONTEXT_RESOLVED = "CONTEXT_RESOLVED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    ACTION_BLOCKED = "ACTION_BLOCKED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_DENIED = "APPROVAL_DENIED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    ACTION_STARTED = "ACTION_STARTED"
    ACTION_SUCCEEDED = "ACTION_SUCCEEDED"
    ACTION_FAILED = "ACTION_FAILED"
    ACTION_CANCELLED = "ACTION_CANCELLED"


@dataclass
class ExecutionEvent:
    event_id: str
    execution_id: str
    event_type: EventType
    timestamp: str
    actor: str
    payload: dict[str, Any]
    previous_event_hash: str | None
    event_hash: str
