from __future__ import annotations

import json
from pathlib import Path

from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.policy.engine import CallablePolicy
from sqube_agent_guard.policy import default_policy
from sqube_agent_guard.telemetry.sink import JsonlEventSink


def test_jsonl_sink_receives_events(tmp_path: Path) -> None:
    ledger = str(tmp_path / "ledger.sqlite3")
    jsonl = str(tmp_path / "events.jsonl")
    engine = ExecutionEngine(
        policy=CallablePolicy(default_policy),
        ledger_path=ledger,
        event_sinks=[JsonlEventSink(jsonl)],
    )
    ctx = ExecutionContext(
        execution_id="sq_exec_sink",
        agent=AgentIdentity(agent_id="default"),
        action="file.read",
        resource="file:/tmp/x",
        parameters={},
    )
    assert engine.run_controlled(ctx, lambda: 1) == 1
    lines = Path(jsonl).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    first = json.loads(lines[0])
    assert first["execution_id"] == "sq_exec_sink"
    assert first["event_type"]
