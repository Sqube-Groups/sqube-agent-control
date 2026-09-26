# sqube-agent-guard (Rust)

**Sqube Agent Control (Rust)** — v1 synchronous `ExecutionEngine` and `ExecutionGuard` aligned with shared contract tests in `tests/contract/`.

Python-only features (CLI, control plane, idempotency helpers) are not in this crate. SDK wrapping is bypassable; this is not a kernel security boundary.

## Install

Not on crates.io yet. From this repository:

```bash
cd rust
cargo build
cargo test
```

Path dependency:

```toml
sqube-agent-guard = { path = "../rust" }
```

## Quick start

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

## Documentation

- Docs: https://sqube-groups.github.io/sqube-agent-control/docs/intro
- Repository: https://github.com/Sqube-Groups/sqube-agent-control

## License

Apache-2.0 — Copyright © 2026 Sqube Groups
