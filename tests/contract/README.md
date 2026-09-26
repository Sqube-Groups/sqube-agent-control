# Cross-SDK contract (v1 semantics)

Python is the **reference implementation**. Other SDKs must match these artifacts:

| Artifact | Purpose |
|----------|---------|
| `fixtures/*.json` | Default policy decisions (ALLOW / BLOCK / REQUIRE_APPROVAL) |
| `v1_semantics.json` | Execution status machine + illegal transitions + deferred approval flow |

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
| `ExecutionEngine` + deferred approvals | yes | yes | guard-level only |
| Full ledger + MCP | yes | partial | partial |

Node: use `ExecutionEngine` with `approvalMode: "deferred"` for v1 execution semantics.  
Rust: state machine + policy contract; full engine deferred path is not required for v1.0.
