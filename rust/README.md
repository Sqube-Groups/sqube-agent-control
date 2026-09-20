# sqube-guard (Rust)

Rust SDK for Sqube Execution Guard v0.1. See the repository root README for product context and honesty requirements.

```rust
use sqube_guard::{Decision, ExecutionGuard, PolicyFn};

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
