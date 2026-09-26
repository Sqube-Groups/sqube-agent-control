"""Environment-backed defaults (v1)."""

from __future__ import annotations

import os


def ledger_path_from_env(default: str = "sqube_ledger.sqlite3") -> str:
    return os.environ.get("SQUBE_LEDGER_PATH", default)
