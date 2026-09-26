"""Load a declarative policy bundle and evaluate one action."""

from pathlib import Path

from sqube_agent_guard import ExecutionEngine, load_policy_bundle
from sqube_agent_guard.execution.engine import context_from_wrap

BUNDLE = Path(__file__).resolve().parents[2] / "tests/fixtures/policies/org_default.json"


def main() -> None:
    policy = load_policy_bundle(BUNDLE)
    engine = ExecutionEngine(policy=policy)
    ctx = context_from_wrap(
        execution_id="sq_exec_bundle_demo",
        agent_id="demo",
        action="send_email",
        resource="user@example.com",
        parameters={},
    )
    result = engine.simulate(ctx)
    print(result.decision.value, result.reason)


if __name__ == "__main__":
    main()
