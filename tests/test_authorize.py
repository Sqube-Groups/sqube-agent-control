from __future__ import annotations

import json
from pathlib import Path

from sqube_agent_guard.guard import _as_policy
from sqube_agent_guard.http.authorize import authorize_request
from sqube_agent_guard.policy.bundle import load_policy_bundle


def test_authorize_default_policy() -> None:
    policy = _as_policy(None)
    out = authorize_request(
        policy,
        {"agent_id": "bot", "action": "send_email", "resource": "a@b.com"},
    )
    assert out["decision"] == "REQUIRE_APPROVAL"
    assert out["execution_id"].startswith("sq_exec_")


def test_authorize_with_bundle() -> None:
    bundle = (
        Path(__file__).parent / "fixtures" / "policies" / "org_default.json"
    )
    policy = load_policy_bundle(bundle)
    out = authorize_request(policy, {"agent_id": "bot", "action": "admin_delete"})
    assert out["decision"] == "BLOCK"


def test_authorize_cli_json_roundtrip() -> None:
    policy = _as_policy(None)
    body = {"agent_id": "x", "action": "file.read", "resource": "file:/tmp/a"}
    out = authorize_request(policy, body)
    parsed = json.loads(json.dumps(out))
    assert parsed["decision"] == "ALLOW"
