from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from sqube_agent_guard.export.exporter import EventExporter
from sqube_agent_guard.export.queue import ExportQueue


def test_queue_enqueue_and_mark_exported(tmp_path: Path) -> None:
    q = ExportQueue(str(tmp_path / "q.sqlite3"))
    ev = {"event_id": "e1", "execution_id": "x", "agent_id": "a"}
    assert q.enqueue(ev, "2026-01-01T00:00:00+00:00")
    assert q.pending_count() == 1
    batch = q.pending_batch(10)
    assert batch[0]["event_id"] == "e1"
    q.mark_exported(["e1"], "2026-01-01T00:00:01+00:00")
    assert q.pending_count() == 0


def test_exporter_retries_after_outage(tmp_path: Path) -> None:
    q = ExportQueue(str(tmp_path / "q.sqlite3"))
    ev = {
        "event_id": "e-retry",
        "execution_id": "sq_exec",
        "agent_id": "bot",
        "event_type": "ACTION_SUCCEEDED",
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    q.enqueue(ev, "2026-01-01T00:00:00+00:00")
    exporter = EventExporter(q, "http://127.0.0.1:1", batch_size=5)
    assert exporter.flush_once() is False
    assert q.pending_count() == 1

    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode())
            received.append(body)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                json.dumps({"accepted": [e["event_id"] for e in body["events"]]}).encode()
            )

        def log_message(self, *_args) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    exporter2 = EventExporter(q, f"http://127.0.0.1:{port}", batch_size=5)
    assert exporter2.flush_once() is True
    assert q.pending_count() == 0
    assert received
    server.shutdown()
