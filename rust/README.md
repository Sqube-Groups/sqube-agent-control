# sqube-agent-guard (Rust)

**Sqube Agent Control (Rust)** implements v1 **synchronous** execution semantics via [`ExecutionEngine`](src/execution_engine.rs). [`ExecutionGuard`](src/guard.rs) `wrap_action` delegates to the same engine path (shared contract tests in `tests/contract/`). Hash-chained events and Python-only features (idempotency, delegation, CLI) are out of scope for Rust v1.0 — see `tests/contract/V1_SYNC_SEMANTICS.md`. SDK wrapping is bypassable; this is **not** a kernel security boundary.

## Install

The crate is **not on crates.io yet**. Clone the repository and build from `rust/`:

```bash
git clone https://github.com/Sqube-Groups/sqube-agent-control.git
cd sqube-agent-control/rust
cargo build
cargo test
```

When published, `cargo add sqube-agent-guard` will work. Until then, use a path or git dependency in your `Cargo.toml` (adjust path/branch/tag to your layout):

```toml
sqube-agent-guard = { path = "../sqube-agent-control/rust" }
# sqube-agent-guard = { git = "https://github.com/Sqube-Groups/sqube-agent-control", branch = "main" }
```

## Quick start

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

## Documentation

- **Docs intro:** [https://sqube-groups.github.io/sqube-agent-control/docs/intro](https://sqube-groups.github.io/sqube-agent-control/docs/intro)
- **Source & README:** [https://github.com/Sqube-Groups/sqube-agent-control](https://github.com/Sqube-Groups/sqube-agent-control)

## License

Apache-2.0 — Copyright © 2026 Sqube Groups
