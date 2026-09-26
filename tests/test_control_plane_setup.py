from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sqube_agent_guard.control_plane.api import create_app
from sqube_agent_guard.control_plane.store import ControlPlaneStore


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    store = ControlPlaneStore(
        plane_db_path=str(tmp_path / "plane.sqlite3"),
        ledger_path=str(tmp_path / "ledger.sqlite3"),
    )
    return TestClient(create_app(store))


def test_setup_ui_flow(client: TestClient) -> None:
    cfg = client.get("/api/v1/auth/config").json()
    assert cfg["setup_required"] is True
    assert client.get("/api/v1/overview").status_code == 401

    res = client.post(
        "/api/v1/auth/setup",
        json={"username": "myadmin", "password": "long-pass-1"},
    )
    assert res.status_code == 200
    assert res.json()["username"] == "myadmin"

    cfg2 = client.get("/api/v1/auth/config").json()
    assert cfg2["setup_required"] is False

    dup = client.post(
        "/api/v1/auth/setup",
        json={"username": "other", "password": "long-pass-2"},
    )
    assert dup.status_code == 400

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "myadmin", "password": "long-pass-1"},
    )
    assert login.status_code == 200
