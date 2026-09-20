# sqube-agent-guard

**Sqube Execution Guard** is a developer-side helper for v0.1 experiments: it wraps consequential actions, evaluates a deterministic policy (`ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`), can pause for human approval via CLI, and appends decisions to a SQLite ledger. SDK wrapping is bypassable—this is **not** a security boundary and does not replace IAM, gateways, or other controls.

## Install

```bash
pip install sqube-agent-guard
```

Requires Python 3.10+.

## Quick start

```python
from sqube_agent_guard import ExecutionGuard, Decision


def policy(action, resource, agent_id, **ctx):
    if action == "delete_file":
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW


guard = ExecutionGuard(policy=policy)


@guard.wrap_action(action="delete_file", resource=lambda path: f"file:{path}")
def delete_file(path):
    ...


delete_file("/tmp/example.txt")
```

## Documentation

- **v0.1 spec:** [https://sqube-groups.github.io/sqube-agent-control/docs/v0.1-spec](https://sqube-groups.github.io/sqube-agent-control/docs/v0.1-spec)
- **Docs intro:** [https://sqube-groups.github.io/sqube-agent-control/docs/intro](https://sqube-groups.github.io/sqube-agent-control/docs/intro)
- **Source & examples:** [https://github.com/Sqube-Groups/sqube-agent-control](https://github.com/Sqube-Groups/sqube-agent-control)

## License

Apache-2.0 — Copyright © 2026 Sqube Groups
