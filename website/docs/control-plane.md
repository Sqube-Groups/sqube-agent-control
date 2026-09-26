---
sidebar_position: 4
title: Control plane
---

# Control plane (local-first)

The **control plane** provides fleet visibility and administration. The **execution kernel** (SDK + ledger) remains the runtime data plane and works without the control plane.

## Run locally

```bash
pip install "sqube-agent-guard[control-plane]"
sqube-agent-guard serve --data-dir .sqube --port 8080
```

Open `http://127.0.0.1:8080/` for the operational dashboard.

Optional API authentication:

```bash
export SQUBE_API_KEY="your-secret"
# Clients send header: X-Sqube-Api-Key
```

If `SQUBE_API_KEY` is unset, the API accepts local requests without a key (development only).

## API surface

| Area | Endpoints |
|------|-----------|
| Agents | `POST/GET /api/v1/agents`, `GET /api/v1/agents/{id}` |
| Policies | `POST/GET /api/v1/policies`, `GET /api/v1/policies/{id}/{version}` |
| Executions | `GET /api/v1/executions`, `GET /api/v1/executions/{id}` |
| Approvals | `GET /api/v1/approvals/pending`, grant/deny POST |
| Fleet | `GET /api/v1/overview` |

Execution evidence is read from the shared SQLite ledger in `--data-dir`. The ledger remains the source of truth; the control plane does not replace SDK authorization.

## Architecture

```text
Agent SDK → ExecutionEngine → Ledger (authoritative)
                                ↑
Control plane API / Dashboard ──┘ (query + administer)
OTel sinks ─────────────────────── (observe ledger events)
```

See `examples/python/platform_control_plane_e2e.py` for a full loop when the server is running.
