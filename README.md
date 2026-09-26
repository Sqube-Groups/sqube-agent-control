# Sqube Agent Control

> **Open-source execution authorization infrastructure for AI agents.**

Wrap consequential actions, evaluate deterministic policy (`ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`), optional human approval, and record tamper-evident execution events. **v1.0** adds composable policies, simulation/explain, declarative policy bundles, hash-chained events (Python + Node), and operator CLI commands.

SDK wrapping is bypassable if application code skips the guard. This is **not** a replacement for IAM, gateways, or production security controls.

## Status

**v1.0.0 (release candidate on `feat/v1.0-core`)** — synchronous execution semantics and shared contract tests across Python, Node, and Rust. **Python** is the reference implementation (full operator surface). **Node** and **Rust** implement `ExecutionEngine` + deferred approval + contract tests; they do **not** ship every Python-only capability. See [tests/contract/V1_SYNC_SEMANTICS.md](tests/contract/V1_SYNC_SEMANTICS.md) and [CHANGELOG.md](CHANGELOG.md).

## SDKs

| Language | Package | Path | v1.0 role |
|----------|---------|------|-----------|
| Python | `sqube-agent-guard` (PyPI) | `src/sqube_agent_guard/` | Reference: engine, CLI, idempotency, delegation, MCP adapter, hash-chained events |
| Node.js | `sqube-agent-guard` (npm) | `nodejs/` | Contract + engine/guard; hash-chained events; Promises for I/O only |
| Rust | `sqube-agent-guard` (build from `rust/`) | `rust/` | Contract + engine/guard; `wrap_action` uses the same engine path |

Shared policy and state-machine contract tests: `tests/contract/`. Public docs: **[GitHub Pages](https://sqube-groups.github.io/sqube-agent-control/docs/intro)**.

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
use sqube_agent_guard::{Decision, ExecutionGuard, WrapOptions};

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

**Python and Node.js** (published registries):

```bash
pip install sqube-agent-guard
npm install sqube-agent-guard
```

**Rust** — crates.io is not published yet. Clone this repository and build from `rust/` (see [`rust/README.md`](rust/README.md)).

## Optional LLM probes

v0.1 guard decisions are **deterministic** — no LLM in the policy path. For manual experiments only (not CI, not `ExecutionGuard`), see [`examples/nvidia_kimi_vision_probe.py`](examples/nvidia_kimi_vision_probe.py).

```bash
pip install requests   # or: pip install -e ".[probes]"
export NVIDIA_API_KEY="your-key"
python examples/nvidia_kimi_vision_probe.py
```

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

## Documentation

| Use | URL |
|-----|-----|
| **Docs home (intro)** | [https://sqube-groups.github.io/sqube-agent-control/docs/intro](https://sqube-groups.github.io/sqube-agent-control/docs/intro) |
| **Repo About / Website field** | [https://sqube-groups.github.io/sqube-agent-control/](https://sqube-groups.github.io/sqube-agent-control/) |

Local docs preview: `cd website && npm ci && npm start`

## Project structure

```text
src/sqube_agent_guard/     # Python SDK
nodejs/              # TypeScript / npm SDK
rust/                # Rust crate
tests/               # Python tests
examples/            # Python examples
website/             # Docusaurus docs site (GitHub Pages)
```

## Contributing

Contributions and feedback are welcome. For larger changes, open an issue first.

## License

Copyright © 2026 Sqube Groups — [Apache-2.0](LICENSE)

[Sqube](https://sqube.in)
