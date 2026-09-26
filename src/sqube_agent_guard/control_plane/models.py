from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentRegistration:
    agent_id: str
    name: str
    runtime: str | None = None
    version: str | None = None
    environment: str | None = None
    status: str = "active"
    capabilities: list[str] | None = None
    policy_id: str | None = None


@dataclass
class PolicyRegistration:
    policy_id: str
    version: str
    name: str | None
    bundle: dict[str, Any]
