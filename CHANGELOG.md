# Changelog

## 1.0.0 (unreleased)

### Release hardening (in progress on `feat/v1.0-core`)

- Explicit execution state machine with illegal-transition tests
- Deferred approvals (`approval_mode="deferred"`) with durable `approval_requests`
- CLI `approvals grant|deny|pending`; `resume_after_approval` with one-time approval consume
- Correlation/root/session IDs persisted on execution records
- E2E demo: `examples/python/agent_workflow_demo.py`
- Maintainer security checklist: `docs_internal_never_commit/SECURITY_REVIEW_v1.md.template`

### Python (reference SDK)

- `ExecutionEngine` with policy evaluation, approvals, delegation checks, idempotency keys, interceptors, and optional event sinks
- Tamper-evident hash-chained execution events in SQLite
- Composable `RulePolicy` and declarative JSON/YAML policy bundles
- `ExecutionGuard` preserving v0.1 `wrap_action` API
- `simulate` / `explain`, MCP tool adapter, stateless `authorize` JSON API
- CLI: executions, ledger verify, policy validate/simulate, approvals pending, authorize
- Optional OpenTelemetry bridge (`telemetry/otel.py`) and JSONL export

### Node.js

- v0.1-compatible `ExecutionGuard` with hash-chained events, `simulate` / `explain`, policy bundle loader, shared contract fixtures

### Rust

- v0.1 execution guard + shared JSON contract tests for default policy

### Docs

- Docusaurus: intro, concepts, getting started, policies, CLI, security model, threat model
