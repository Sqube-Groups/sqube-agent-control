"""Sqube Agent Control CLI (v1)."""

from __future__ import annotations

import argparse
import json
import sys

from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.execution.engine import ExecutionEngine, _new_execution_id, context_from_wrap
from sqube_agent_guard.guard import ExecutionGuard, _as_policy
from sqube_agent_guard.ledger.store import SQLiteExecutionStore
from sqube_agent_guard.models import ActionStatus
from sqube_agent_guard.policy.bundle import load_policy_bundle, validate_policy_bundle


def main() -> None:
    parser = argparse.ArgumentParser(prog="sqube-agent-guard", description="Sqube Agent Control CLI")
    parser.add_argument(
        "--ledger",
        default="sqube_ledger.sqlite3",
        help="SQLite execution store path",
    )
    sub = parser.add_subparsers(dest="command")

    execs = sub.add_parser("executions", help="List recent executions")
    execs.add_argument("--limit", type=int, default=10)

    show = sub.add_parser("execution", help="Show one execution")
    show.add_argument("execution_id")

    verify = sub.add_parser("ledger", help="Ledger operations")
    verify_sub = verify.add_subparsers(dest="ledger_cmd")
    verify_sub.add_parser("verify", help="Verify event hash chains")

    sim = sub.add_parser("simulate", help="Dry-run policy evaluation")
    sim.add_argument("--agent", default="default")
    sim.add_argument("--action", required=True)
    sim.add_argument("--resource", default=None)
    sim.add_argument("--environment", default=None)

    expl = sub.add_parser("explain", help="Explain policy decision")
    expl.add_argument("--agent", default="default")
    expl.add_argument("--action", required=True)
    expl.add_argument("--resource", default=None)
    expl.add_argument("--environment", default=None)

    pol = sub.add_parser("policy", help="Declarative policy bundles")
    pol_sub = pol.add_subparsers(dest="policy_cmd")
    pol_validate = pol_sub.add_parser("validate", help="Validate a JSON/YAML bundle")
    pol_validate.add_argument("path")
    pol_sim = pol_sub.add_parser("simulate", help="Evaluate a bundle against a context")
    pol_sim.add_argument("path")
    pol_sim.add_argument("--agent", default="default")
    pol_sim.add_argument("--action", required=True)
    pol_sim.add_argument("--resource", default=None)
    pol_sim.add_argument("--environment", default=None)

    appr = sub.add_parser("approvals", help="Approval queue inspection")
    appr_sub = appr.add_subparsers(dest="approvals_cmd")
    appr_pending = appr_sub.add_parser("pending", help="List executions waiting for approval")
    appr_pending.add_argument("--limit", type=int, default=20)

    parser.add_argument("--last", type=int, default=10, help="Limit for default list view")

    args = parser.parse_args()

    if args.command is None:
        _legacy_list(args)
        return

    store = SQLiteExecutionStore(args.ledger)

    if args.command == "executions":
        rows = store.list_executions(args.limit)
        for row in rows:
            print(
                f"{row['created_at']}  {row['execution_id']}  {row['action']}  "
                f"{row['decision']}  {row['status']}"
            )
        return

    if args.command == "execution":
        row = store.get_execution(args.execution_id)
        if not row:
            print("Not found.", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(row, indent=2, default=str))
        events = store.get_events(args.execution_id)
        print("\nEvents:")
        for event in events:
            print(f"  {event.timestamp}  {event.event_type.value}  {event.actor}")
        return

    if args.command == "ledger" and args.ledger_cmd == "verify":
        ok = store.verify_chain()
        print("OK" if ok else "INTEGRITY_FAILURE")
        sys.exit(0 if ok else 2)

    if args.command == "approvals" and args.approvals_cmd == "pending":
        rows = store.list_executions(
            args.limit, status=ActionStatus.WAITING_APPROVAL.value
        )
        if not rows:
            print("No pending approvals.")
            return
        for row in rows:
            print(
                f"{row['created_at']}  {row['execution_id']}  {row['agent_id']}  "
                f"{row['action']}  {row.get('resource') or '-'}"
            )
        return

    if args.command == "policy" and args.policy_cmd == "validate":
        errors = validate_policy_bundle(args.path)
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            sys.exit(1)
        print("OK")
        return

    if args.command == "policy" and args.policy_cmd == "simulate":
        policy = load_policy_bundle(args.path)
        ctx = context_from_wrap(
            execution_id=_new_execution_id(),
            agent_id=args.agent,
            action=args.action,
            resource=args.resource,
            parameters={},
            environment=args.environment,
        )
        result = policy.evaluate(ctx)
        print(f"Decision: {result.decision.value}")
        print(f"Policy: {result.policy_id} (v{result.policy_version})")
        print(f"Reason: {result.reason}")
        return

    if args.command in ("simulate", "explain"):
        guard = ExecutionGuard(ledger_path=args.ledger)
        ctx = context_from_wrap(
            execution_id=_new_execution_id(),
            agent_id=args.agent,
            action=args.action,
            resource=args.resource,
            parameters={},
            environment=args.environment,
        )
        result = guard.explain(ctx) if args.command == "explain" else guard.simulate(ctx)
        print(f"Decision: {result.decision.value}")
        print(f"Policy: {result.policy_id} (v{result.policy_version})")
        print(f"Reason: {result.reason}")
        if result.matched_rules:
            print("Matched:", ", ".join(result.matched_rules))
        if result.failed_rules:
            print("Failed:", ", ".join(result.failed_rules))
        return

    parser.print_help()


def _legacy_list(args) -> None:
    store = SQLiteExecutionStore(args.ledger)
    rows = store.list_executions(args.last)
    if not rows:
        print("No records.")
        return
    for row in rows:
        print(
            f"{row['created_at']}  {row['execution_id']}  {row['action']}  "
            f"{row['decision']}  {row['status']}"
        )


if __name__ == "__main__":
    main()
