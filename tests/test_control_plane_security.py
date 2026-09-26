from __future__ import annotations

import os
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from sqube_agent_guard.control_plane.api import create_app
from sqube_agent_guard.control_plane.store import ControlPlaneStore


@pytest.fixture
def secured_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ControlPlaneStore:
    monkeypatch.setenv("SQUBE_ADMIN_PASSWORD", "admin-secret")
    monkeypatch.setenv("SQUBE_API_KEY", "ingest-key")
    return ControlPlaneStore(
        plane_db_path=str(tmp_path / "plane.sqlite3"),
        ledger_path=str(tmp_path / "ledger.sqlite3"),
    )


@pytest.fixture
def secured_client(secured_store: ControlPlaneStore) -> TestClient:
    return TestClient(create_app(secured_store))


def _login(client: TestClient, username: str = "admin", password: str = "admin-secret") -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert res.status_code == 200
    return res.json()["csrf_token"]


def test_unauthenticated_fleet_read_blocked(secured_client: TestClient) -> None:
    assert secured_client.get("/api/v1/agents").status_code == 401
    assert secured_client.get("/api/v1/overview").status_code == 401
    assert secured_client.get("/api/v1/executions").status_code == 401


def test_health_public(secured_client: TestClient) -> None:
    assert secured_client.get("/api/v1/health").status_code == 200


def test_ingest_requires_api_key_not_session(secured_client: TestClient) -> None:
    csrf = _login(secured_client)
    res = secured_client.post(
        "/api/v1/events/batch",
        json={"events": []},
        headers={"X-Sqube-CSRF-Token": csrf},
    )
    assert res.status_code == 401
    ok = secured_client.post(
        "/api/v1/events/batch",
        json={"events": []},
        headers={"X-Sqube-Api-Key": "ingest-key"},
    )
    assert ok.status_code == 200


def test_sse_rejects_query_token_bypass(secured_client: TestClient) -> None:
    res = secured_client.get("/api/v1/events/stream?access_token=ingest-key")
    assert res.status_code == 401


def test_role_matrix(secured_client: TestClient, secured_store: ControlPlaneStore) -> None:
    team_id = secured_store.identity.list_teams()[0]["team_id"]
    secured_store.identity.add_team_member(
        team_id, "viewer1", "viewer", "viewer-pass", {"username": "admin"}
    )
    secured_store.identity.add_team_member(
        team_id, "operator1", "operator", "operator-pass", {"username": "admin"}
    )

    vcsrf = _login(secured_client, "viewer1", "viewer-pass")
    assert secured_client.get("/api/v1/agents").status_code == 200

    denied = secured_client.post(
        "/api/v1/agents",
        json={"agent_id": "x", "name": "X"},
        headers={"X-Sqube-CSRF-Token": vcsrf},
    )
    assert denied.status_code == 403

    ocsrf = _login(secured_client, "operator1", "operator-pass")
    pending = secured_client.get("/api/v1/approvals/pending")
    assert pending.status_code == 200

    admin_csrf = _login(secured_client)
    created = secured_client.post(
        "/api/v1/agents",
        json={"agent_id": "fleet-a", "name": "Fleet A"},
        headers={"X-Sqube-CSRF-Token": admin_csrf},
    )
    assert created.status_code == 200

    wh = secured_client.post(
        "/api/v1/webhooks/destinations",
        json={"url": "http://127.0.0.1:9/h", "secret": "s", "event_types": ["execution.created"]},
        headers={"X-Sqube-CSRF-Token": admin_csrf},
    )
    assert wh.status_code == 200
    assert "secret" not in wh.json()

    _login(secured_client, "viewer1", "viewer-pass")
    assert secured_client.get("/api/v1/webhooks/destinations").status_code == 403


def test_csrf_required_for_mutations(secured_client: TestClient) -> None:
    _login(secured_client)
    res = secured_client.post(
        "/api/v1/agents",
        json={"agent_id": "no-csrf", "name": "N"},
    )
    assert res.status_code == 403


def test_logout_invalidates_session(secured_client: TestClient) -> None:
    csrf = _login(secured_client)
    assert secured_client.get("/api/v1/agents").status_code == 200
    cookie_before = secured_client.cookies.get("sqube_session")
    assert cookie_before

    out = secured_client.post("/api/v1/auth/logout")
    assert out.status_code == 200
    assert secured_client.get("/api/v1/agents").status_code == 401

    # Reuse old session id must not work (server-side row deleted).
    secured_client.cookies.set("sqube_session", cookie_before)
    assert secured_client.get("/api/v1/agents").status_code == 401

    secured_client.cookies.clear()
    csrf2 = _login(secured_client)
    assert csrf2
    assert secured_client.get("/api/v1/agents").status_code == 200


def test_audit_on_agent_register(secured_client: TestClient) -> None:
    csrf = _login(secured_client)
    secured_client.post(
        "/api/v1/agents",
        json={"agent_id": "audited", "name": "Audited"},
        headers={"X-Sqube-CSRF-Token": csrf},
    )
    audit = secured_client.get(
        "/api/v1/admin/audit", headers={"X-Sqube-CSRF-Token": csrf}
    ).json()
    assert any(a["action"] == "agent.registered" for a in audit)
