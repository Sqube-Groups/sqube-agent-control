"""
End-to-end: control plane + execution kernel (local-first).

Prerequisites:
  pip install -e ".[control-plane,otel]"

Run control plane (separate terminal):
  sqube-agent-guard serve --data-dir /tmp/sqube-platform

Then:
  PYTHONPATH=src python examples/python/platform_control_plane_e2e.py
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from sqube_agent_guard import ExecutionContext, ExecutionEngine, ExecutionGuard
from sqube_agent_guard.exceptions import SqubeApprovalPendingError, SqubeBlockedError
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.policy import default_policy
from sqube_agent_guard.telemetry.otel import OtelEventSink

BASE = "http://127.0.0.1:8080"
DATA_LEDGER = Path("/tmp/sqube-platform/sqube_ledger.sqlite3")


def api(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    api(
        "POST",
        "/api/v1/agents",
        {
            "agent_id": "customer-agent",
            "name": "Customer Agent",
            "runtime": "python",
            "environment": "local",
            "policy_id": "org_default",
        },
    )
    api(
        "POST",
        "/api/v1/policies",
        {
            "policy_id": "org_default",
            "version": "1",
            "name": "default",
            "bundle": {
                "policy_id": "org_default",
                "rules": [
                    {"when": {"action": "admin_delete"}, "decision": "BLOCK"},
                    {"when": {"action": "send_email"}, "decision": "REQUIRE_APPROVAL"},
                ],
            },
        },
    )

    ledger = str(DATA_LEDGER)
    guard = ExecutionGuard(
        policy=default_policy,
        ledger_path=ledger,
        approval_mode="deferred",
        event_sinks=[OtelEventSink()],
    )
    engine = ExecutionEngine(
        policy=guard._engine._policy,
        ledger_path=ledger,
        approval_mode="deferred",
        event_sinks=[OtelEventSink()],
    )
    agent = AgentIdentity(agent_id="customer-agent")

    @guard.wrap_action(action="file.read", resource="db:customers")
    def read_db() -> str:
        return "row"

    print("read_db:", read_db())

    ctx_email = ExecutionContext(
        execution_id="sq_exec_platform_email",
        agent=agent,
        action="send_email",
        resource="user@example.com",
        parameters={"to": "user@example.com"},
    )
    try:
        engine.run_controlled(ctx_email, lambda: "sent")
    except SqubeApprovalPendingError as pending:
        api("POST", f"/api/v1/approvals/{pending.approval_id}/grant", {"decided_by": "cto"})
        print(
            "email:",
            guard.resume_after_approval(
                ctx_email, lambda: "sent", approval_id=pending.approval_id
            ),
        )

    ctx_del = ExecutionContext(
        execution_id="sq_exec_platform_del",
        agent=agent,
        action="admin_delete",
        resource="customers",
        parameters={},
    )
    try:
        engine.run_controlled(ctx_del, lambda: "x")
    except SqubeBlockedError:
        print("admin_delete blocked (expected)")

    overview = api("GET", "/api/v1/overview")
    print("dashboard overview:", json.dumps(overview["counts"], indent=2))


if __name__ == "__main__":
    main()
