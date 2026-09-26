"""MCP adapter (v1): translate tool calls into Sqube execution contexts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.identity.models import AgentIdentity


@dataclass
class McpToolCall:
    tool_name: str
    arguments: dict[str, Any]
    agent_id: str
    resource: str | None = None


class McpToolAdapter:
    """Route MCP tool invocations through the execution engine."""

    def __init__(self, engine: ExecutionEngine) -> None:
        self._engine = engine

    def invoke(
        self,
        call: McpToolCall,
        handler: Callable[[], Any],
        *,
        execution_id: str,
        action: str | None = None,
    ) -> Any:
        ctx = ExecutionContext(
            execution_id=execution_id,
            agent=AgentIdentity(agent_id=call.agent_id),
            action=action or f"mcp.tool.{call.tool_name}",
            resource=call.resource or f"mcp:tool/{call.tool_name}",
            parameters=call.arguments,
        )
        return self._engine.run_controlled(ctx, handler)
