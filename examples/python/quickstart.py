"""Non-destructive quickstart: simulate then wrap a safe action."""

from sqube_agent_guard import Decision, ExecutionContext, ExecutionGuard
from sqube_agent_guard.identity.models import AgentIdentity


def policy(action: str, resource: str | None, agent_id: str, **_: object) -> Decision:
    if action == "email.send":
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW


def main() -> None:
    guard = ExecutionGuard(policy=policy)
    ctx = ExecutionContext(
        execution_id="sq_exec_demo",
        agent=AgentIdentity(agent_id="demo-agent"),
        action="file.read",
        resource="file:/tmp/example.txt",
        parameters={},
    )
    print("simulate:", guard.simulate(ctx).decision.value)

    @guard.wrap_action(action="file.read", resource="file:/tmp/example.txt")
    def read_file() -> str:
        return "ok"

    print("run:", read_file())


if __name__ == "__main__":
    main()
