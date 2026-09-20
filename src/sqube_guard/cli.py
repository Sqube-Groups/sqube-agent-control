"""CLI entry point for inspecting ledger (v0.1 minimal)."""

from __future__ import annotations

import argparse
import sqlite3
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="sqube-guard", description="Sqube Execution Guard CLI")
    parser.add_argument(
        "ledger",
        nargs="?",
        default="sqube_ledger.sqlite3",
        help="Path to SQLite ledger",
    )
    parser.add_argument("--last", type=int, default=10, help="Show last N records")
    args = parser.parse_args()

    try:
        conn = sqlite3.connect(args.ledger)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT execution_id, action, decision, status, created_at FROM execution_records "
            "ORDER BY created_at DESC LIMIT ?",
            (args.last,),
        ).fetchall()
    except sqlite3.Error as exc:
        print(f"Error reading ledger: {exc}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print("No records.")
        return

    for row in rows:
        print(
            f"{row['created_at']}  {row['execution_id']}  "
            f"{row['action']}  {row['decision']}  {row['status']}"
        )


if __name__ == "__main__":
    main()
