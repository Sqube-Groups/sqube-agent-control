from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from sqube_agent_guard.control_plane.api import create_app
from sqube_agent_guard.control_plane.store import ControlPlaneStore
from sqube_agent_guard.control_plane.webhooks import sign_webhook_payload
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.export.exporter import EventExporter
from sqube_agent_guard.export.queue import ExportQueue
from sqube_agent_guard.export.sink import ControlPlaneExportSink
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.models import Decision
from sqube_agent_guard.policy.engine import CallablePolicy


def _allow(action: str, *_a, **_kw) -> Decision:
    return Decision.ALLOW


@pytest.fixture
def store(tmp_path: Path) -> ControlPlaneStore:
    return ControlPlaneStore(
        plane_db_path=str(tmp_path / "plane.sqlite3"),
        ledger_path=str(tmp_path / "ledger.sqlite3"),
    )


@pytest.fixture
def client(store: ControlPlaneStore) -> TestClient:
    return TestClient(create_app(store))


def _event(event_id: str, execution_id: str = "sq_exec_1") -> dict:
    return {
        "event_id": event_id,
        "execution_id": execution_id,
        "agent_id": "bot-1",
        "event_type": "ACTION_REQUESTED",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "action": "file.read",
        "resource": "file:/x",
    }


def test_batch_ingest_and_duplicate(client: TestClient) -> None:
    body = {"events": [_event("evt-1"), _event("evt-2")]}
    first = client.post("/api/v1/events/batch", json=body).json()
    assert first["accepted"] == ["evt-1", "evt-2"]
    second = client.post("/api/v1/events/batch", json=body).json()
    assert second["duplicates"] == ["evt-1", "evt-2"]
    rows = client.get("/api/v1/executions").json()
    assert any(r["execution_id"] == "sq_exec_1" for r in rows)


def test_batch_auth_required(store: ControlPlaneStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SQUBE_API_KEY", "secret")
    authed = TestClient(create_app(store))
    res = authed.post("/api/v1/events/batch", json={"events": [_event("evt-x")]})
    assert res.status_code == 401
    res = authed.post(
        "/api/v1/events/batch",
        json={"events": [_event("evt-x")]},
        headers={"X-Sqube-Api-Key": "secret"},
    )
    assert res.status_code == 200


def test_malformed_event_rejected(client: TestClient) -> None:
    res = client.post(
        "/api/v1/events/batch",
        json={"events": [{"event_id": "bad", "execution_id": "x"}]},
    ).json()
    assert res["rejected"]


def test_sse_replay_and_last_event_id(client: TestClient, store: ControlPlaneStore) -> None:
    client.post("/api/v1/events/batch", json={"events": [_event("evt-sse")]})
    msgs = store.bus.replay_after(0)
    assert len(msgs) == 1
    assert msgs[0]["type"] == "execution.created"
    assert msgs[0]["data"]["event_id"] == "evt-sse"
    assert store.bus.replay_after(msgs[0]["id"]) == []


def test_partial_batch_and_ordering(client: TestClient) -> None:
    body = {
        "events": [
            _event("evt-ok"),
            {"event_id": "evt-bad", "execution_id": "x"},
            _event("evt-ok2", "sq_exec_2"),
        ]
    }
    res = client.post("/api/v1/events/batch", json=body).json()
    assert res["accepted"] == ["evt-ok", "evt-ok2"]
    assert res["rejected"]
    assert client.post("/api/v1/events/batch", json=body).json()["duplicates"] == [
        "evt-ok",
        "evt-ok2",
    ]


def test_events_stream_route_registered(store: ControlPlaneStore) -> None:
    app = create_app(store)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/v1/events/stream" in paths


def test_exporter_does_not_break_execution(tmp_path: Path, store: ControlPlaneStore) -> None:
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            received.append(json.loads(body.decode()))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                json.dumps({"accepted": [e["event_id"] for e in received[-1]["events"]]}).encode()
            )

        def log_message(self, *_args) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    queue = ExportQueue(str(tmp_path / "q.sqlite3"))
    exporter = EventExporter(queue, f"http://127.0.0.1:{port}", batch_size=10)
    sink = ControlPlaneExportSink(exporter, store.ledger)
    engine = ExecutionEngine(
        policy=CallablePolicy(_allow),
        store=store.ledger,
        event_sinks=[sink],
    )
    ctx = ExecutionContext(
        execution_id="sq_exec_export",
        agent=AgentIdentity(agent_id="bot-1"),
        action="read",
        resource=None,
        parameters={},
    )
    assert engine.run_controlled(ctx, lambda: 1) == 1
    assert exporter.flush_once() is True
    assert received
    server.shutdown()


def test_webhook_signing_and_delivery(store: ControlPlaneStore) -> None:
    captured: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            captured["signature"] = self.headers.get("Sqube-Signature")
            captured["body"] = body
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/hook"
    store.webhooks.add_destination(url, "whsec_test", ["execution.created"])
    store.ingest_events_batch([_event("evt-wh")])
    import time

    deadline = time.time() + 3
    while not captured and time.time() < deadline:
        time.sleep(0.05)
    server.shutdown()
    assert captured.get("signature", "").startswith("t=")
    sig_header = captured["signature"]
    ts = sig_header.split(",")[0].split("=", 1)[1]
    v1 = sig_header.split("v1=")[1]
    assert v1 == sign_webhook_payload("whsec_test", ts, captured["body"])


def test_webhook_duplicate_delivery_skipped(store: ControlPlaneStore) -> None:
    calls = {"n": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            calls["n"] += 1
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/hook"
    store.webhooks.add_destination(url, "whsec_test", ["execution.created"])
    store.ingest_events_batch([_event("evt-dup-wh")])
    store.ingest_events_batch([_event("evt-dup-wh")])
    import time

    time.sleep(0.2)
    server.shutdown()
    assert calls["n"] == 1
