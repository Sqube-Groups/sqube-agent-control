from __future__ import annotations

import json
from pathlib import Path

import pytest

from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.models import Decision
from sqube_agent_guard.policy.engine import CallablePolicy
from sqube_agent_guard.telemetry.otel import OtelEventSink


def _allow(_a: str, *_k, **_kw) -> Decision:
    return Decision.ALLOW


@pytest.fixture
def otel_providers():
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    span_exporter = InMemorySpanExporter()
    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(
        SimpleSpanProcessor(span_exporter)
    )
    metric_reader = InMemoryMetricReader()
    metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
    yield span_exporter, metric_reader
    span_exporter.clear()


def test_otel_sink_without_sdk_is_noop(tmp_path: Path) -> None:
    sink = OtelEventSink()
    engine = ExecutionEngine(
        policy=CallablePolicy(_allow),
        ledger_path=str(tmp_path / "l.sqlite3"),
        event_sinks=[sink],
    )
    ctx = ExecutionContext(
        execution_id="sq_exec_otel_noop",
        agent=AgentIdentity(agent_id="bot"),
        action="read",
        resource=None,
        parameters={"secret_token": "super-secret-value"},
    )
    assert engine.run_controlled(ctx, lambda: 1) == 1


def test_otel_records_execution_span_and_metrics(tmp_path: Path, otel_providers) -> None:
    span_exporter, metric_reader = otel_providers
    sink = OtelEventSink()
    engine = ExecutionEngine(
        policy=CallablePolicy(_allow),
        ledger_path=str(tmp_path / "m.sqlite3"),
        event_sinks=[sink],
    )
    ctx = ExecutionContext(
        execution_id="sq_exec_otel_span",
        agent=AgentIdentity(agent_id="bot"),
        action="read",
        resource="file:x",
        parameters={"password": "nope"},
    )
    engine.run_controlled(ctx, lambda: 42)
    finished = span_exporter.get_finished_spans()
    assert finished
    assert finished[0].name == "sqube.execution"
    attrs = dict(finished[0].attributes or {})
    assert attrs.get("sqube.execution_id") == "sq_exec_otel_span"
    assert "super-secret" not in str(attrs)
    assert "password" not in str(attrs)
    metrics_data = metric_reader.get_metrics_data()
    assert metrics_data is not None
    names: set[str] = set()
    for resource in metrics_data.resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                names.add(metric.name)
    assert "sqube.executions.total" in names
    assert "sqube.executions.allowed" in names
    assert "sqube.executions.succeeded" in names


def test_telemetry_sink_failure_does_not_block_execution(tmp_path: Path) -> None:
    class FailingSink:
        def emit(self, _event) -> None:
            raise RuntimeError("telemetry unavailable")

    engine = ExecutionEngine(
        policy=CallablePolicy(_allow),
        ledger_path=str(tmp_path / "f.sqlite3"),
        event_sinks=[FailingSink()],
    )
    ctx = ExecutionContext(
        execution_id="sq_exec_sink_fail",
        agent=AgentIdentity(agent_id="bot"),
        action="read",
        resource=None,
        parameters={},
    )
    assert engine.run_controlled(ctx, lambda: 99) == 99


def test_otel_contract_json_loads() -> None:
    path = Path(__file__).resolve().parent / "contract" / "otel_semantics.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "sqube.execution" == data["root_span_name"]
    assert "sqube.executions.total" in data["metrics"]
