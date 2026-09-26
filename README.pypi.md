# sqube-agent-guard

**Sqube Agent Control** — open-source execution authorization for AI agents.

Wrap consequential actions, evaluate deterministic policy (`ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`), optional human approval, and record tamper-evident execution events. v1.0 adds composable policies, `simulate` / `explain`, and an execution store with hash-chained events.

SDK-level control is bypassable if application code skips the guard. This is not a replacement for IAM, gateways, or production security controls.

## Install

```bash
pip install sqube-agent-guard
```

Requires Python 3.10+.

## Quick start

```python
from sqube_agent_guard import Decision, ExecutionGuard

def policy(action, resource, agent_id, **ctx):
    if action == "email.send":
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW

guard = ExecutionGuard(policy=policy)

@guard.wrap_action(action="email.send", resource="user@example.com")
def send_email():
    ...

send_email()
```

## Docs

https://sqube-groups.github.io/sqube-agent-control/docs/intro
