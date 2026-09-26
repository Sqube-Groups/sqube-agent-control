from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from sqube_agent_guard.control_plane.api import create_app
from sqube_agent_guard.control_plane.store import ControlPlaneStore
from tests.control_plane_helpers import setup_and_login
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.models import Decision
from sqube_agent_guard.policy.engine import CallablePolicy


def _allow(_a: str, *_k, **_kw) -> Decision:
    return Decision.ALLOW


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    store = ControlPlaneStore(
        plane_db_path=str(tmp_path / "plane.sqlite3"),
        ledger_path=str(tmp_path / "ledger.sqlite3"),
    )
    return TestClient(create_app(store))


def test_register_agent_and_overview(client: TestClient) -> None:
    csrf = setup_and_login(client)
    res = client.post(
        "/api/v1/agents",
        json={"agent_id": "bot-a", "name": "Agent A", "environment": "dev"},
        headers={"X-Sqube-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    agents = client.get("/api/v1/agents").json()
    assert len(agents) == 1
    overview = client.get("/api/v1/overview").json()
    assert overview["total_agents"] == 1


def test_execution_visible_via_control_plane(client: TestClient, tmp_path: Path) -> None:
    store = ControlPlaneStore(
        plane_db_path=str(tmp_path / "p2.sqlite3"),
        ledger_path=str(tmp_path / "l2.sqlite3"),
    )
    engine = ExecutionEngine(
        policy=CallablePolicy(_allow),
        store=store.ledger,
    )
    ctx = ExecutionContext(
        execution_id="sq_exec_cp",
        agent=AgentIdentity(agent_id="bot-a"),
        action="file.read",
        resource="file:/x",
        parameters={},
    )
    engine.run_controlled(ctx, lambda: "ok")
    api = TestClient(create_app(store))
    setup_and_login(api)
    rows = api.get("/api/v1/executions").json()
    assert any(r["execution_id"] == "sq_exec_cp" for r in rows)
    detail = api.get("/api/v1/executions/sq_exec_cp").json()
    assert detail["execution"]["status"] == "SUCCEEDED"
    assert len(detail["events"]) >= 2
