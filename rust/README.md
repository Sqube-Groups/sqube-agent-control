# sqube-agent-guard (Rust)

Rust SDK for Sqube Execution Guard v0.1. See the repository root README for product context and honesty requirements.

```rust
use sqube_agent_guard::{Decision, ExecutionGuard, PolicyFn};

let policy: PolicyFn = |action, _resource, _agent| {
    if action == "delete_file" {
        Decision::RequireApproval
    } else {
        Decision::Allow
    }
};

let guard = ExecutionGuard::new(policy).with_ledger_path("sqube_ledger.sqlite3");
// Use guard.wrap_action(...) — see examples in tests.
```

## Installation

The Rust crate is **not on crates.io yet**. Build and test from this directory in a clone of the repository:

```bash
git clone https://github.com/Sqube-Groups/sqube-agent-control.git
cd sqube-agent-control/rust
cargo build
cargo test
```

When the crate is published to crates.io, `cargo add sqube-agent-guard` will work; until then, add a dependency from your `Cargo.toml`:

```toml
# Path (local checkout)
sqube-agent-guard = { path = "../sqube-agent-control/rust" }

# Or git
sqube-agent-guard = { git = "https://github.com/Sqube-Groups/sqube-agent-control", branch = "main" }
```

Adjust the path, branch, or tag to match your layout.
