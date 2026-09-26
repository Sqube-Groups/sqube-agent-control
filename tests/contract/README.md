# Cross-SDK contract (v1 semantics)

Python is the **reference implementation**. Other SDKs must match these artifacts:

| Artifact | Purpose |
|----------|---------|
| `fixtures/*.json` | Default policy decisions (ALLOW / BLOCK / REQUIRE_APPROVAL) |
| `v1_semantics.json` | Execution status machine + illegal transitions + deferred approval flow |
| `deferred_approval.json` | End-to-end deferred grant → resume scenario (all SDKs) |
| `otel_semantics.json` | OpenTelemetry span events, attributes, and metrics (Python + Node) |

## Running contract tests

```bash
PYTHONPATH=src pytest tests/contract/
cd nodejs && npm test   # includes contractSemantics.test.ts
cd rust && cargo test   # contract_fixtures + contract_semantics
```

## v1.0 synchronous semantics

See **[V1_SYNC_SEMANTICS.md](./V1_SYNC_SEMANTICS.md)** — one lifecycle for all SDKs; Node Promises are transport only; deferred approval is a pause, not background execution.

## Parity expectations (contract vs optional features)

| Capability | Python | Node | Rust |
|------------|--------|------|------|
| Policy fixtures | yes | yes | yes |
| State machine contract | yes | yes | yes |
| `ExecutionEngine` sync + deferred | yes | yes | yes |
| `ExecutionGuard` → engine | yes | yes | yes |
| Hash-chained events (ledger) | yes | yes | no |

All three SDKs run the same `deferred_approval.json` integration scenario in CI.
