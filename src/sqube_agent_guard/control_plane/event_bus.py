from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any


class EventBus:
    """In-process fan-out for SSE (and internal hooks). Replay buffer is authoritative for delivery."""

    def __init__(self, replay_limit: int = 500) -> None:
        self._replay: deque[dict[str, Any]] = deque(maxlen=replay_limit)
        self._seq = 0
        self._wake = threading.Event()

    def publish_sync(self, event_type: str, data: dict[str, Any]) -> int:
        self._seq += 1
        message = {"id": self._seq, "type": event_type, "data": data}
        self._replay.append(message)
        self._wake.set()
        return self._seq

    def replay_after(self, last_id: int) -> list[dict[str, Any]]:
        return [m for m in self._replay if m["id"] > last_id]

    def latest_id(self) -> int:
        return self._seq

    def wait_for_updates(self, after_id: int, timeout: float) -> None:
        if self.latest_id() > after_id:
            return
        self._wake.wait(timeout)
        self._wake.clear()
