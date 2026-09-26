from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    name: str | None = None
    version: str | None = None
    environment: str | None = None
    owner: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Principal:
    type: str
    id: str
    metadata: dict[str, Any] = field(default_factory=dict)
