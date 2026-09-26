from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Delegation:
    delegation_id: str
    delegator: str
    delegate: str
    scope: frozenset[str]
    created_at: str
    expires_at: str | None = None
    parent_delegation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def allows_action(self, action: str) -> bool:
        if action in self.scope:
            return True
        return any(
            entry.endswith(".*") and action.startswith(entry[:-1])
            for entry in self.scope
        )
