# Getting started

## Python SDK

```bash
pip install sqube-agent-guard
```

```python
from sqube_agent_guard import Decision, ExecutionGuard

def policy(action, resource, agent_id, **ctx):
    if action.startswith("admin_"):
        return Decision.BLOCK
    return Decision.ALLOW

guard = ExecutionGuard(policy=policy)

@guard.wrap_action(action="file.read", resource="file:/tmp/demo.txt")
def read_demo():
    return "ok"

read_demo()
```

Inspect the ledger:

```bash
sqube-agent-guard executions --limit 5
sqube-agent-guard ledger verify
```

## Control plane (optional)

Fleet dashboard and HTTP APIs for agents, policies, executions, and approvals:

```bash
pip install "sqube-agent-guard[control-plane]"
sqube-agent-guard serve --data-dir .sqube --port 8080
```

1. Open **http://127.0.0.1:8080/setup** and create the first admin (you choose the username).
2. Register agents/policies via API or examples under `examples/python/`.
3. Optional: `export SQUBE_CONTROL_PLANE_URL=http://127.0.0.1:8080` so the Python SDK exports events to the plane.

See [Control plane](./control-plane.md) and [Event ingestion](./event-ingestion.md).

## Node.js

```bash
npm install sqube-agent-guard
```

```typescript
import { ExecutionGuard } from "sqube-agent-guard";

const guard = new ExecutionGuard();
const run = guard.wrapAction({ action: "file.read" }, () => "ok");
await run();
```

## Rust

Clone the repository and build from `rust/`.

## Next steps

- [Concepts](./concepts.md)
- [Policies](./policies.md)
- [CLI](./cli.md)
- [Control plane authentication](./control-plane-auth.md)
