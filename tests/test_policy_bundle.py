from __future__ import annotations

from pathlib import Path

from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.identity.models import AgentIdentity
from sqube_agent_guard.models import Decision
from sqube_agent_guard.policy.bundle import load_policy_bundle, policy_from_dict, validate_policy_bundle

FIXTURE = Path(__file__).parent / "fixtures" / "policies" / "org_default.json"


def _ctx(action: str, resource: str | None = None) -> ExecutionContext:
    return ExecutionContext(
        execution_id="sq_exec_bundle",
        agent=AgentIdentity(agent_id="bot"),
        action=action,
        resource=resource,
    )


def test_load_org_default_fixture() -> None:
    policy = load_policy_bundle(FIXTURE)
    assert policy.metadata.policy_id == "org-default"
    assert policy.evaluate(_ctx("admin_delete")).decision == Decision.BLOCK
    assert policy.evaluate(_ctx("send_email")).decision == Decision.REQUIRE_APPROVAL
    assert policy.evaluate(_ctx("file.read", "file:/tmp/x")).decision == Decision.ALLOW


def test_validate_ok() -> None:
    assert validate_policy_bundle(FIXTURE) == []


def test_nested_all_any() -> None:
    policy = policy_from_dict(
        {
            "policy_id": "nested",
            "name": "nested",
            "rules": [
                {
                    "name": "prod deploy block",
                    "when": {
                        "all": [
                            {"agent_id": "coding-agent"},
                            {"environment": "production"},
                            {"action": "deployment.create"},
                        ]
                    },
                    "decision": "BLOCK",
                }
            ],
        }
    )
    ctx = ExecutionContext(
        execution_id="x",
        agent=AgentIdentity(agent_id="coding-agent", environment="production"),
        action="deployment.create",
        environment="production",
    )
    assert policy.evaluate(ctx).decision == Decision.BLOCK
