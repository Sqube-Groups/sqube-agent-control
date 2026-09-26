from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqube_agent_guard.export.queue import ExportQueue

_logger = logging.getLogger(__name__)


class EventExporter:
    """Batch HTTP exporter with retry/backoff. Never raises into execution path."""

    def __init__(
        self,
        queue: ExportQueue,
        base_url: str,
        api_key: str | None = None,
        *,
        batch_size: int = 50,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._queue = queue
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._batch_size = batch_size
        self._timeout = timeout_seconds
        self._failures = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def enqueue(self, event: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self._queue.enqueue(event, now)

    def flush_once(self) -> bool:
        batch = self._queue.pending_batch(self._batch_size)
        if not batch:
            return True
        body = json.dumps({"events": batch}).encode()
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-Sqube-Api-Key"] = self._api_key
        req = urllib.request.Request(
            f"{self._base_url}/api/v1/events/batch",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status not in (200, 201):
                    self._failures += 1
                    return False
                payload = json.loads(resp.read().decode())
                accepted = payload.get("accepted", [])
                self._queue.mark_exported(
                    accepted,
                    datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                )
                self._failures = 0
                return True
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            _logger.debug("export batch failed: %s", exc)
            self._failures += 1
            return False

    def _loop(self) -> None:
        while not self._stop.is_set():
            ok = self.flush_once()
            if not ok:
                delay = min(60.0, 2 ** min(self._failures, 6))
                self._stop.wait(delay)
            else:
                self._stop.wait(1.0)

    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="sqube-export")
        self._thread.start()

    def shutdown(self, flush: bool = True) -> None:
        self._stop.set()
        if flush:
            for _ in range(5):
                if self.flush_once() and self._queue.pending_count() == 0:
                    break
                time.sleep(0.2)
        if self._thread:
            self._thread.join(timeout=2.0)
