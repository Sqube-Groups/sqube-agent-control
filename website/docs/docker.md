---
sidebar_position: 5
title: Docker
---

# Run with Docker

The control plane (API + dashboard) ships as a container image. The SDKs stay libraries inside your agents; the image is the one server component.

## Single container

```bash
docker run -d --name sqube \
  -p 127.0.0.1:8080:8080 \
  -v sqube-data:/data \
  -e SQUBE_API_KEY=your-ingest-key \
  ghcr.io/sqube-groups/sqube-agent-control:latest
```

Open **http://127.0.0.1:8080/setup** to create the administrator account. Data (`control_plane.sqlite3`, `sqube_ledger.sqlite3`) lives in the `/data` volume.

## Docker Compose

From a clone of the repository:

```bash
docker compose up -d                      # control plane only
docker compose --profile demo up --build  # plus a demo agent that exports events
```

The demo agent runs three guarded actions (allowed, approval required, blocked) and posts them to the control plane, so the dashboard shows data right away.

## Environment

| Variable | Purpose |
|----------|---------|
| `SQUBE_API_KEY` | Ingest key agents send in `X-Sqube-Api-Key` |
| `SQUBE_ADMIN_PASSWORD` | Optional: auto-create user `admin` on first start (8+ characters) |
| `SQUBE_ADMIN_EMAIL` | Email for the auto-created admin (default `admin@local`) |
| `SQUBE_COOKIE_SECURE` | Set to `1` when serving over HTTPS behind a reverse proxy |

Agents running elsewhere point at the container with `SQUBE_CONTROL_PLANE_URL` and the same `SQUBE_API_KEY`. See [Event ingestion](./event-ingestion).

## Notes

- The container runs as a non-root user (`uid 10001`) and has a health check on `/api/v1/health`.
- Compose binds to `127.0.0.1` only. Put a TLS-terminating reverse proxy in front before exposing it.
- Images are published for `linux/amd64` and `linux/arm64` on each release tag.
