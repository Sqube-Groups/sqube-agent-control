# Getting started

## Python

```bash
pip install sqube-agent-guard
```

```python
from sqube_agent_guard import Decision, ExecutionGuard

def policy(action, resource, agent_id, **ctx):
    if action.startswith("admin_"):
        return Decision.BLOCK
    return Decision.ALLOW

guard = ExecutionGuard()

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

Clone this repository and build from `rust/` (crates.io publish is optional for v1.0).

## Next steps

- [Concepts](./concepts.md)
- [Policies](./policies.md)
- [CLI](./cli.md)
