# Sqube Agent Control

> Open-source execution authorization infrastructure for AI agents.

Wrap consequential actions, evaluate deterministic policy (`ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`), optional human approval, and record tamper-evident execution events. **v1.0** adds policy bundles, simulation/explain, hash-chained events (Python + Node), optional OpenTelemetry, a local **control plane** (API + dashboard), and remote event ingestion.

SDK wrapping is bypassable if application code skips the guard. This is **not** a replacement for IAM, API gateways, or host-level security.

## Status

**v1.0.4** on [`main`](https://github.com/Sqube-Groups/sqube-agent-control/tree/main) — Python is the reference SDK; Node and Rust implement the shared execution contract ([`tests/contract/`](tests/contract/)). See [CHANGELOG.md](CHANGELOG.md) and [V1_SYNC_SEMANTICS.md](tests/contract/V1_SYNC_SEMANTICS.md).

## SDKs

| Language | Package | Path |
|----------|---------|------|
| Python | [`sqube-agent-guard`](https://pypi.org/project/sqube-agent-guard/) **1.0.4** (PyPI) | `src/sqube_agent_guard/` |
| Node.js | [`sqube-agent-guard`](https://www.npmjs.com/package/sqube-agent-guard) **1.0.4** (npm) | [`nodejs/`](nodejs/) |
| Rust | build from repo (not on crates.io yet) | [`rust/`](rust/) |

**Docs:** [sqube-groups.github.io/sqube-agent-control/docs/intro](https://sqube-groups.github.io/sqube-agent-control/docs/intro)

**Control plane:** `pip install "sqube-agent-guard[control-plane]"` then `sqube-agent-guard serve` — first visit `/setup` to create an admin account. See [control plane](website/docs/control-plane.md) and [event ingestion](website/docs/event-ingestion.md).

## Quick start (Python)

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

## Quick start (Node.js)

```typescript
import { Decision, ExecutionGuard } from "sqube-agent-guard";

const guard = new ExecutionGuard({
  policy: (action) =>
    action === "delete_file" ? Decision.REQUIRE_APPROVAL : Decision.ALLOW,
});

const deleteFile = guard.wrapAction(
  { action: "delete_file", resource: (path: string) => `file:${path}` },
  (path: string) => { /* ... */ }
);

await deleteFile("/tmp/example.txt");
```

## Quick start (Rust)

```rust
use sqube_agent_guard::{ExecutionGuard, WrapOptions};

let guard = ExecutionGuard::with_default_policy().with_ledger_path("sqube_ledger.sqlite3");

guard.wrap_action(
    WrapOptions {
        action: "delete_file".into(),
        resource: Some("file:/tmp/x".into()),
        agent_id: "default".into(),
    },
    || Ok(()),
    "path=/tmp/x",
    r#"{"path":"/tmp/x"}"#,
)?;
```

## Installation

```bash
pip install sqube-agent-guard
npm install sqube-agent-guard
```

Rust: clone and build from `rust/` ([rust/README.md](rust/README.md)).

## Development

```bash
pip install -e ".[dev]"
pytest

cd nodejs && npm ci && npm test

cd rust && cargo test
```

## Project layout

```text
src/sqube_agent_guard/   Python SDK + control plane
nodejs/                  TypeScript SDK
rust/                    Rust crate
tests/contract/          Cross-language semantics
website/                 Public documentation (GitHub Pages)
examples/                Python examples
```

## Contributing

Open an issue before large changes. Pull requests welcome.

## License

Apache-2.0 — Copyright © 2026 Sqube Groups · [Sqube](https://sqube.in)
