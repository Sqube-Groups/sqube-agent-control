"""
Demo agent for the Docker Compose stack.

Runs a few guarded actions against a local ledger and exports events to the
control plane (SQUBE_CONTROL_PLANE_URL + SQUBE_API_KEY), so the dashboard has
something to show:

  docker compose --profile demo up --build
"""

from __future__ import annotations

import os

from sqube_agent_guard import Decision, ExecutionGuard
from sqube_agent_guard.exceptions import SqubeApprovalPendingError, SqubeBlockedError
from sqube_agent_guard.export.config import control_plane_export_from_env

LEDGER = os.environ.get("SQUBE_LEDGER_PATH", "/data/sqube_ledger.sqlite3")


def policy(action, resource, agent_id, **ctx):
    if action == "admin_delete":
        return Decision.BLOCK
    if action == "send_email":
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW


def main() -> None:
    sinks, exporter = control_plane_export_from_env(LEDGER)
    guard = ExecutionGuard(
        policy=policy,
        ledger_path=LEDGER,
        approval_mode="deferred",
        event_sinks=sinks,
    )

    @guard.wrap_action(action="file.read", resource="db:customers", agent_id="demo-agent")
    def read_customers() -> str:
        return "3 rows"

    @guard.wrap_action(action="send_email", resource=lambda to: f"email:{to}", agent_id="demo-agent")
    def send_email(to: str) -> str:
        return f"sent to {to}"

    @guard.wrap_action(action="admin_delete", resource="db:customers", agent_id="demo-agent")
    def drop_customers() -> str:
        return "dropped"

    print("file.read:", read_customers())
    try:
        send_email("user@example.com")
    except SqubeApprovalPendingError as pending:
        print("send_email: waiting for approval", pending.approval_id)
    try:
        drop_customers()
    except SqubeBlockedError:
        print("admin_delete: blocked by policy")

    if exporter is not None:
        exporter.shutdown(flush=True)
        print("events exported to", os.environ["SQUBE_CONTROL_PLANE_URL"])
    else:
        print("SQUBE_CONTROL_PLANE_URL not set; events stayed in the local ledger")


if __name__ == "__main__":
    main()
