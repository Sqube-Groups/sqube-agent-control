from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqube_agent_guard.approval import prompt_cli_approval  # noqa: F401


@dataclass
class ApprovalRequest:
    approval_id: str
    execution_id: str
    requested_at: str
    expires_at: str | None
    action: str
    resource: str | None
    parameters_hash: str
    policy_version: str
    summary: str
    metadata: dict[str, Any]


class ApprovalProvider(Protocol):
    def request(self, request: ApprovalRequest, timeout_seconds: int) -> tuple[bool, str | None, str | None]: ...


class CliApprovalProvider:
    def request(
        self, request: ApprovalRequest, timeout_seconds: int
    ) -> tuple[bool, str | None, str | None]:
        return prompt_cli_approval(
            execution_id=request.execution_id,
            agent_id=request.metadata.get("agent_id", "default"),
            action=request.action,
            resource=request.resource,
            summary=request.summary,
            timeout_seconds=timeout_seconds,
        )
