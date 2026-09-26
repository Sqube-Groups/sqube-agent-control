"""
End-to-end v1 demo: ALLOW, REQUIRE_APPROVAL (deferred), BLOCK.

Run:
  PYTHONPATH=src python examples/python/agent_workflow_demo.py

Then inspect:
  sqube-agent-guard --ledger /tmp/sqube_demo.sqlite3 executions
  sqube-agent-guard --ledger /tmp/sqube_demo.sqlite3 ledger verify
"""

from __future__ import annotations

from pathlib import Path

from sqube_agent_guard import ExecutionContext, ExecutionGuard
from sqube_agent_guard.execution.engine import ExecutionEngine
from sqube_agent_guard.exceptions import SqubeApprovalPendingError, SqubeBlockedError
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.ledger.store import SQLiteExecutionStore
from sqube_agent_guard.policy import default_policy

LEDGER = Path("/tmp/sqube_demo.sqlite3")


def main() -> None:
    if LEDGER.exists():
        LEDGER.unlink()
    guard = ExecutionGuard(
        policy=default_policy,
        ledger_path=str(LEDGER),
        approval_mode="deferred",
    )
    engine = ExecutionEngine(
        policy=guard._engine._policy,
        ledger_path=str(LEDGER),
        approval_mode="deferred",
    )
    agent = AgentIdentity(agent_id="customer-agent")

    @guard.wrap_action(action="file.read", resource="file:/customers/1")
    def read_customer() -> str:
        return "customer_record"

    print("read:", read_customer())

    ctx_email = ExecutionContext(
        execution_id="sq_exec_demo_email",
        agent=agent,
        action="send_email",
        resource="user@example.com",
        parameters={"to": "user@example.com"},
    )
    try:
        engine.run_controlled(ctx_email, lambda: "email_sent")
    except SqubeApprovalPendingError as pending:
        print("email waiting approval:", pending.approval_id)
        store = SQLiteExecutionStore(str(LEDGER))
        store.grant_approval(pending.approval_id, "cto", "2026-01-02T12:00:00+00:00")
        print(
            "email resumed:",
            guard.resume_after_approval(
                ctx_email, lambda: "email_sent", approval_id=pending.approval_id
            ),
        )

    ctx_admin = ExecutionContext(
        execution_id="sq_exec_demo_admin",
        agent=agent,
        action="admin_delete",
        resource="customers",
        parameters={},
    )
    try:
        engine.run_controlled(ctx_admin, lambda: "deleted")
    except SqubeBlockedError:
        print("admin_delete blocked (expected)")

    store = SQLiteExecutionStore(str(LEDGER))
    print("ledger verify:", store.verify_chain())
    for row in store.list_executions(10):
        print(row["execution_id"], row["action"], row["decision"], row["status"])


if __name__ == "__main__":
    main()
