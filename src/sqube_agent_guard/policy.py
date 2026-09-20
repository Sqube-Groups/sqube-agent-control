from __future__ import annotations

from sqube_agent_guard.models import Decision

HIGH_RISK_ACTIONS = frozenset({"db_mutation", "send_email", "file_delete"})


def default_policy(action: str, resource: str | None, agent_id: str, **_: object) -> Decision:
    if action in HIGH_RISK_ACTIONS:
        return Decision.REQUIRE_APPROVAL
    if action.startswith("admin_"):
        return Decision.BLOCK
    return Decision.ALLOW
