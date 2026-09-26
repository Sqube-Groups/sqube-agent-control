from __future__ import annotations

from fastapi.testclient import TestClient


def setup_and_login(
    client: TestClient,
    username: str = "admin",
    password: str = "test-pass-123",
) -> str:
    res = client.post(
        "/api/v1/auth/setup",
        json={"username": username, "password": password},
    )
    if res.status_code == 400 and "already configured" in res.text:
        res = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
    assert res.status_code == 200, res.text
    return res.json()["csrf_token"]
