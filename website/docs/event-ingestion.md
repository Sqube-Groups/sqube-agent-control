---
sidebar_position: 5
title: Event ingestion
---

# Remote event ingestion

Agents record execution evidence in the **local ledger** first. Optional export sends redacted platform events to the control plane.

```text
Agent SDK → Local ledger → Durable export queue → HTTP batch → Control plane
                                                              ↓
                                                    SSE / Webhooks / Dashboard
```

## Why HTTP batches (not polling)

Agents push **new** events incrementally from a local queue. The control plane does not poll agents every few seconds, and agents do not download the full ledger.

## Configure export (Python)

```bash
export SQUBE_CONTROL_PLANE_URL=http://127.0.0.1:8080
export SQUBE_API_KEY=your-key   # optional in local dev if unset on server
```

```python
from sqube_agent_guard import ExecutionGuard
from sqube_agent_guard.export.config import control_plane_export_from_env

sinks, exporter = control_plane_export_from_env("sqube_ledger.sqlite3")
guard = ExecutionGuard(ledger_path="sqube_ledger.sqlite3", event_sinks=sinks)
```

Export failures **do not** change authorization or execution outcomes. Events remain queued until the plane is reachable.

## Ingestion API

`POST /api/v1/events/batch` — idempotent on `event_id`.

## Realtime dashboard

`GET /api/v1/events/stream` (SSE) pushes execution/approval updates. The dashboard uses REST for initial load and SSE for live updates.

## Webhooks

`POST /api/v1/webhooks/destinations` registers signed outbound deliveries (`Sqube-Signature` HMAC). Webhooks are not part of the SDK execution path.

## OpenTelemetry

OTel remains a separate observability path from platform event ingestion. See [Observability](./observability).
