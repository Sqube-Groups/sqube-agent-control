from __future__ import annotations

from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.execution.interceptor import ExecutionInterceptor
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.policy.engine import CallablePolicy
from sqube_agent_guard.policy import default_policy


class _AppendMarker(ExecutionInterceptor):
    def __init__(self) -> None:
        self.seen: list[str] = []

    def intercept(self, ctx: ExecutionContext, next_fn):
        self.seen.append("before")
        result = next_fn()
        self.seen.append("after")
        return result


def test_interceptor_wraps_execution(tmp_path) -> None:
    marker = _AppendMarker()
    engine = ExecutionEngine(
        policy=CallablePolicy(default_policy),
        ledger_path=str(tmp_path / "ledger.sqlite3"),
        interceptors=[marker],
    )
    ctx = ExecutionContext(
        execution_id="sq_exec_int",
        agent=AgentIdentity(agent_id="default"),
        action="file.read",
        resource="file:/tmp/x",
        parameters={},
    )
    assert engine.run_controlled(ctx, lambda: 99) == 99
    assert marker.seen == ["before", "after"]
