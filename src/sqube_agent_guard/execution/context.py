from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqube_agent_guard.authority.delegation import Delegation
from sqube_agent_guard.identity.models import AgentIdentity, Principal


@dataclass
class ExecutionContext:
    execution_id: str
    agent: AgentIdentity
    action: str
    resource: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    principal: Principal | None = None
    environment: str | None = None
    timestamp: str | None = None
    correlation_id: str | None = None
    session_id: str | None = None
    parent_execution_id: str | None = None
    root_execution_id: str | None = None
    delegation_chain: tuple[Delegation, ...] = ()
    purpose: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    idempotency_key: str | None = None
