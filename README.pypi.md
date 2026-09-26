# sqube-agent-guard

**Sqube Agent Control** — open-source execution authorization for AI agents.

Evaluate deterministic policy (`ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`), optional human approval, and a tamper-evident execution ledger. The SDK is application-level; bypassing the guard is out of scope for v1.

## Install

```bash
pip install sqube-agent-guard
```

Optional extras:

```bash
pip install "sqube-agent-guard[control-plane]"   # local API + dashboard
pip install "sqube-agent-guard[otel]"            # OpenTelemetry bridge
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

## Control plane (optional)

```bash
sqube-agent-guard serve --data-dir .sqube
```

Open `http://127.0.0.1:8080/setup` on first run to create an administrator account.

## Documentation

https://sqube-groups.github.io/sqube-agent-control/docs/intro

## License

Apache-2.0 — Copyright © 2026 Sqube Groups
