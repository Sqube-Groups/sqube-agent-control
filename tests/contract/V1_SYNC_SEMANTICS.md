# v1.0 synchronous execution semantics (all SDKs)

v1.0 defines **one** execution lifecycle, shared via `v1_semantics.json` and `deferred_approval.json`.

## Contract

1. **Default approval mode is synchronous** — policy may return `REQUIRE_APPROVAL`; the runtime collects an approval decision before executing the guarded function (CLI prompt, callback, or operator grant in deferred mode).
2. **Deferred approval is a pause, not background execution** — `run_controlled` / `runControlled` stops in `WAITING_APPROVAL` until an operator grants (or denies). The guarded function runs only after a successful resume (or inline sync approval).
3. **State transitions are atomic** — illegal transitions and stale-status updates are rejected (see store `transition_execution` and contract illegal-transition tests).
4. **Node.js** — public APIs return Promises for I/O; semantics match Python/Rust. There is no parallel “async execution model.”

## SDK scope (v1.0 release)

| Capability | Python | Node | Rust |
|------------|--------|------|------|
| Shared policy + state-machine contract tests | yes | yes | yes |
| `ExecutionEngine` sync + deferred | yes | yes | yes |
| `ExecutionGuard` → delegates to engine | yes | yes | yes |
| Hash-chained execution events | yes | yes | no |
| Idempotency keys | yes | no | no |
| Delegation / principal models | yes | no | no |
| Operator CLI | yes | no | no |
| MCP adapter | yes | no | no |

Anything listed “no” for Node/Rust is **out of scope** for v1.0 parity; those SDKs must not document those features as supported.
