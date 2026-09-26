# Cross-SDK contract (v1 semantics)

Python is the **reference implementation**. Other SDKs must match these artifacts:

| Artifact | Purpose |
|----------|---------|
| `fixtures/*.json` | Default policy decisions (ALLOW / BLOCK / REQUIRE_APPROVAL) |
| `v1_semantics.json` | Execution status machine + illegal transitions + deferred approval flow |
| `deferred_approval.json` | End-to-end deferred grant → resume scenario (all SDKs) |

## Running contract tests

```bash
PYTHONPATH=src pytest tests/contract/
cd nodejs && npm test   # includes contractSemantics.test.ts
cd rust && cargo test   # contract_fixtures + contract_semantics
```

## Parity expectations

| Capability | Python | Node | Rust |
|------------|--------|------|------|
| Policy fixtures | yes | yes | yes |
| State machine contract | yes | yes | yes |
| `ExecutionEngine` sync + deferred | yes | yes | yes |
| State machine contract | yes | yes | yes |
| Hash-chained events (ledger) | yes | yes | partial (records + approvals) |

All three SDKs run the same `deferred_approval.json` integration scenario in CI.
