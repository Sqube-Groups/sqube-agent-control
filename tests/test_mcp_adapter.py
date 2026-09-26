from __future__ import annotations

from pathlib import Path

from sqube_agent_guard.adapters.mcp import McpToolAdapter, McpToolCall
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.policy.engine import CallablePolicy
from sqube_agent_guard.policy import default_policy


def test_mcp_tool_invoke_runs_through_engine(tmp_path: Path) -> None:
    engine = ExecutionEngine(
        policy=CallablePolicy(default_policy),
        ledger_path=str(tmp_path / "ledger.sqlite3"),
    )
    adapter = McpToolAdapter(engine)
    result = adapter.invoke(
        McpToolCall(tool_name="search", arguments={"q": "x"}, agent_id="mcp-bot"),
        lambda: {"hits": 1},
        execution_id="sq_exec_mcp",
    )
    assert result == {"hits": 1}
    row = engine.store.get_execution("sq_exec_mcp")
    assert row is not None
    assert row["action"] == "mcp.tool.search"
    assert engine.store.verify_chain("sq_exec_mcp")
