---
sidebar_position: 4
title: Control plane
---

# Control plane (local-first)

The **control plane** provides fleet visibility and administration. The **execution kernel** (SDK + local ledger) remains the runtime data plane and works without the control plane.

## Run locally

```bash
pip install "sqube-agent-guard[control-plane]"
sqube-agent-guard serve --data-dir .sqube --port 8080
```

### First-time setup (browser)

Open **http://127.0.0.1:8080/setup** and create the administrator account (username and password of your choice; minimum 8 characters).

After setup, sign in at **/login**. The dashboard uses a **session cookie** and CSRF protection — not API keys in the browser.

Optional automation (CI only): set `SQUBE_ADMIN_PASSWORD` (8+ characters) before the first start to auto-create user **`admin`**.

### Agent event export (machines)

```bash
export SQUBE_CONTROL_PLANE_URL=http://127.0.0.1:8080
export SQUBE_API_KEY=your-ingest-key   # required once human auth is enabled
```

SDKs POST batched events to `POST /api/v1/events/batch`. Export failures do not block local authorized execution.

See [Control plane authentication](./control-plane-auth) and [Event ingestion](./event-ingestion).

## API surface

| Area | Endpoints |
|------|-----------|
| Auth | `POST /api/v1/auth/setup`, `login`, `logout`, `GET /api/v1/auth/me` |
| Agents | `POST/GET /api/v1/agents`, `PATCH .../policy` |
| Policies | `POST/GET /api/v1/policies`, version history via store |
| Executions | `GET /api/v1/executions`, `GET /api/v1/executions/{id}` |
| Approvals | `GET /api/v1/approvals/pending`, grant/deny POST |
| Events | `POST /api/v1/events/batch`, `GET /api/v1/events/stream` (SSE) |
| Webhooks | `POST/GET /api/v1/webhooks/destinations` (admin) |
| Fleet | `GET /api/v1/overview` |

The **local ledger** remains runtime evidence. Ingested events merge for fleet views; the plane does not replace SDK policy evaluation.

## Architecture

```text
Agent SDK → Local ledger (authoritative)
              ├→ OTel (optional)
              └→ Export queue → HTTP ingest → Control plane
                        ├→ SSE → Dashboard
                        └→ Webhooks
```

Example: `examples/python/platform_control_plane_e2e.py`
