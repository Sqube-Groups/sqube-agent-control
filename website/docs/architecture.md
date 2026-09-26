---
sidebar_position: 3
title: Architecture
---

# Sqube architecture (v1.0)

Sqube separates **control plane**, **runtime data plane**, and **observability**.

## Product loop

```text
Agent SDK → Policy → Execution → Local ledger (authoritative evidence)
  ├→ OTel exporter → observability backend (optional)
  └→ Durable export queue → HTTP batch ingest → Control plane
        ├→ SSE → Dashboard (live)
        └→ Webhooks → external systems
```

See [Event ingestion](./event-ingestion.md) for export, SSE, and webhook behavior.

**Invariant:** no successful controlled side effect without a preceding `ALLOW` or approved decision recorded for that execution.

## Control plane

- Agent registration and policy catalog (SQLite metadata)
- Execution and approval querying
- Operator dashboard (static UI served by the control plane)
- Optional API key (`SQUBE_API_KEY`)

Local-first: no Sqube cloud account required.

## Runtime data plane

- Python (reference), Node, and Rust SDKs
- Shared semantic contract (`tests/contract/`)
- Tamper-evident ledger (Python + Node hash chains)
- MCP adapter, interceptors, CLI

## Observability

- Optional OpenTelemetry (`pip install sqube-agent-guard[otel]`)
- Observes ledger events only; telemetry failure does not change authorization

## Security boundary

SDK enforcement is **application-level**. Hostile code that bypasses the guard is out of scope for v1.0. See [Security model](./security-model).
