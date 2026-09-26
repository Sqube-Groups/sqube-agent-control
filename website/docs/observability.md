---
sidebar_position: 6
title: Observability (OpenTelemetry)
---

# OpenTelemetry (optional)

Sqube records tamper-evident events in the **ledger first**. OpenTelemetry is **observability only** — it never participates in policy or authorization decisions. If OTel is missing or fails, execution continues according to your configured failure semantics (`fail_closed` / `fail_open`).

## Enable (Python)

```bash
pip install "sqube-agent-guard[otel]"
```

```python
from sqube_agent_guard import ExecutionGuard
from sqube_agent_guard.telemetry.otel import OtelEventSink

guard = ExecutionGuard(event_sinks=[OtelEventSink()])
```

Configure your OpenTelemetry SDK (collector/exporter) as usual in the host application.

## Enable (Node.js)

```bash
npm install @opentelemetry/api   # optional peer
```

```typescript
import { ExecutionGuard, OtelEventSink } from "sqube-agent-guard";

const guard = new ExecutionGuard({ eventSinks: [new OtelEventSink()] });
```

## Semantics contract

Span names, attributes, and metric instruments are defined in the repository:

`tests/contract/otel_semantics.json`

Shared attribute keys include `sqube.execution_id`, `sqube.agent_id`, `sqube.action`, `sqube.decision`, and `sqube.status`. **Raw parameters, secrets, and tokens are never exported** — only redacted or allowlisted fields from ledger events.

## Rust

Rust v1.0 does not ship an OTel SDK integration. The same `otel_semantics.json` contract applies when Rust gains telemetry in a future release.
