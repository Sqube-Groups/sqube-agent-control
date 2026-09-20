"""Example A — DB mutation (staged; no real DB)."""

from sqube_guard import Decision, ExecutionGuard


def policy(action, resource, agent_id, **_) -> Decision:
    if action == "db_mutation":
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW


def execute_sql(query: str) -> str:
    return f"executed: {query}"


def without_sqube(query: str) -> str:
    return execute_sql(query)


def with_sqube(query: str) -> str:
    guard = ExecutionGuard(policy=policy, ledger_path="examples_ledger.sqlite3")

    @guard.wrap_action(action="db_mutation", resource=lambda q: f"sql:{q[:40]}")
    def guarded_execute_sql(q: str) -> str:
        return execute_sql(q)

    return guarded_execute_sql(query)


if __name__ == "__main__":
    q = "UPDATE users SET status='active' WHERE id=1"
    print("Without:", without_sqube(q))
    print("With (auto-approve in demo — use real CLI in production):")
    guard = ExecutionGuard(
        policy=policy,
        ledger_path="examples_ledger.sqlite3",
        approval_fn=lambda **_: (True, "demo", None),
    )

    @guard.wrap_action(action="db_mutation", resource=lambda query: f"sql:{query[:40]}")
    def guarded(q: str) -> str:
        return execute_sql(q)

    print("With:", guarded(q))
