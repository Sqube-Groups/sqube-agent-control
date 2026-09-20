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
| Python | `sqube-agent-guard` (PyPI) | `src/sqube_agent_guard/` |
| Node.js | `sqube-agent-guard` (npm) | `nodejs/` |
| Rust | `sqube-agent-guard` (build from `rust/`) | `rust/` |

All three implement the same v0.1 contract documented on **[GitHub Pages](https://sqube-groups.github.io/sqube-agent-control/docs/v0.1-spec)** (source: [`website/docs/v0.1-spec.md`](website/docs/v0.1-spec.md)).

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
| **v0.1 specification** | [https://sqube-groups.github.io/sqube-agent-control/docs/v0.1-spec](https://sqube-groups.github.io/sqube-agent-control/docs/v0.1-spec) |
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
