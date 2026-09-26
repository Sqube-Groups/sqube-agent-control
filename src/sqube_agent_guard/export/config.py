from __future__ import annotations

import os
from typing import TYPE_CHECKING

from sqube_agent_guard.export.exporter import EventExporter
from sqube_agent_guard.export.queue import ExportQueue
from sqube_agent_guard.export.sink import ControlPlaneExportSink
from sqube_agent_guard.ledger.store import SQLiteExecutionStore

if TYPE_CHECKING:
    from sqube_agent_guard.telemetry.sink import EventSink


def control_plane_export_from_env(
    ledger_path: str, queue_db_path: str | None = None
) -> tuple[list[EventSink], EventExporter | None]:
    """Build optional export sink when SQUBE_CONTROL_PLANE_URL is set."""
    url = os.environ.get("SQUBE_CONTROL_PLANE_URL")
    if not url:
        return [], None
    api_key = os.environ.get("SQUBE_API_KEY")
    qpath = queue_db_path or str(
        __import__("pathlib").Path(ledger_path).parent / "export_queue.sqlite3"
    )
    queue = ExportQueue(qpath)
    exporter = EventExporter(queue, url, api_key)
    exporter.start_background()
    ledger = SQLiteExecutionStore(ledger_path)
    return [ControlPlaneExportSink(exporter, ledger)], exporter
