from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.models import Decision
from sqube_agent_guard.policy.engine import (
    ALL,
    NOT,
    PolicyMetadata,
    RulePolicy,
    action_is,
    agent_is,
    environment_is,
)


def _ctx(**kwargs) -> ExecutionContext:
    agent = AgentIdentity(agent_id=kwargs.pop("agent_id", "deployment-agent"), environment="production")
    return ExecutionContext(
        execution_id="sq_exec_test",
        agent=agent,
        action=kwargs.pop("action", "deployment.create"),
        resource=kwargs.pop("resource", "service:payments"),
        environment=kwargs.pop("environment", "production"),
        **kwargs,
    )


def test_all_blocks_in_production() -> None:
    policy = RulePolicy(
        metadata=PolicyMetadata(policy_id="production-deploy", name="production-deploy"),
        rules=[
            (
                "block coding agent prod deploy",
                ALL(
                    agent_is("coding-agent"),
                    environment_is("production"),
                    action_is("deployment.create"),
                ),
                Decision.BLOCK,
            ),
        ],
    )
    result = policy.evaluate(_ctx(agent_id="coding-agent"))
    assert result.decision == Decision.BLOCK


def test_not_allows_non_matching() -> None:
    policy = RulePolicy(
        metadata=PolicyMetadata(policy_id="p", name="p"),
        rules=[("block admin", NOT(action_is("admin.delete")), Decision.ALLOW)],
    )
    result = policy.evaluate(_ctx(action="email.send"))
    assert result.decision == Decision.ALLOW
