# Sqube Agent Control

> Open-source infrastructure for controlling AI agent actions.

**v0.1 is an experiment.** SDK wrapping is bypassable. This is **not** a replacement for IAM, gateways, or security controls. It exists to learn whether execution-decision tooling has pull in real teams.

Sqube Execution Guard (v0.1) wraps a consequential action, deterministically decides `ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`, optionally pauses for a human via CLI, and writes an append-only SQLite execution record.

Do not use messaging like “secure your agents,” “enterprise control plane,” or “prevent all unauthorized actions.”

## Status

**Experimental — API may change.**

## SDKs

| Language | Package | Path |
|----------|---------|------|
| Python | `sqube-guard` (PyPI) | `src/sqube_guard/` |
| Node.js | `@sqube/guard` (npm) | `nodejs/` |
| Rust | `sqube-guard` (crates.io) | `rust/` |

All three implement the same v0.1 contract from [`docs/project md files/sqube_execution_guard_v0_1_spec.md`](docs/project%20md%20files/sqube_execution_guard_v0_1_spec.md).

## Quick start (Python)

```python
from sqube_guard import ExecutionGuard, Decision


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
import { Decision, ExecutionGuard } from "@sqube/guard";

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
use sqube_guard::{Decision, ExecutionGuard, WrapOptions};

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

## Decisions

```text
ALLOW
BLOCK
REQUIRE_APPROVAL
```

Policies are application-defined callables. No LLM in the decision path for v0.1.

## Installation

```bash
pip install sqube-guard
npm install @sqube/guard
cargo add sqube-guard
```

Packaging and releases are wired via GitHub Actions on version tags (`v*.*.*`). Configure repository secrets: `PYPI_API_TOKEN`, `NPM_TOKEN`, `CARGO_REGISTRY_TOKEN`.

## Development

```bash
# Python
pip install -e ".[dev]"
pytest

# Node
cd nodejs && npm ci && npm test

# Rust
cd rust && cargo test
```

## Project structure

```text
src/sqube_guard/     # Python SDK
nodejs/              # TypeScript / npm SDK
rust/                # Rust crate
tests/               # Python tests
examples/            # Python examples
docs/                # v0.1 spec
```

## Contributing

Contributions and feedback are welcome. For larger changes, open an issue first.

## License

Copyright © 2026 Sqube Groups — [Apache-2.0](LICENSE)

[Sqube](https://sqube.in)
