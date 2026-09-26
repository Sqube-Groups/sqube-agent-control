from __future__ import annotations

from pathlib import Path
from typing import Any

import json

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sqube_agent_guard.control_plane.auth import api_key_dependency
from sqube_agent_guard.control_plane.models import AgentRegistration, PolicyRegistration
from sqube_agent_guard.control_plane.store import ControlPlaneStore
class AgentBody(BaseModel):
    agent_id: str
    name: str
    runtime: str | None = None
    version: str | None = None
    environment: str | None = None
    status: str = "active"
    capabilities: list[str] = Field(default_factory=list)
    policy_id: str | None = None


class PolicyBody(BaseModel):
    policy_id: str
    version: str = "1"
    name: str | None = None
    bundle: dict[str, Any]


class ApprovalDecisionBody(BaseModel):
    decided_by: str = "operator"
    reason: str | None = None


class IngestEventBody(BaseModel):
    event_id: str
    execution_id: str
    agent_id: str
    event_type: str
    timestamp: str
    action: str | None = None
    resource: str | None = None
    decision: str | None = None
    status: str | None = None
    correlation_id: str | None = None
    root_execution_id: str | None = None
    policy_id: str | None = None


class EventBatchBody(BaseModel):
    """Lenient batch body — per-event validation happens in the store for partial success."""

    events: list[dict[str, Any]]


class WebhookDestinationBody(BaseModel):
    url: str
    secret: str
    event_types: list[str]


def create_app(store: ControlPlaneStore) -> FastAPI:
    app = FastAPI(title="Sqube Control Plane", version="1.0.0")
    auth = api_key_dependency()

    @app.get("/api/v1/health")
    def health(_: None = Depends(auth)) -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/overview")
    def overview(_: None = Depends(auth)) -> dict[str, Any]:
        return store.overview()

    @app.post("/api/v1/agents")
    def register_agent(body: AgentBody, _: None = Depends(auth)) -> dict[str, Any]:
        return store.register_agent(
            AgentRegistration(
                agent_id=body.agent_id,
                name=body.name,
                runtime=body.runtime,
                version=body.version,
                environment=body.environment,
                status=body.status,
                capabilities=body.capabilities,
                policy_id=body.policy_id,
            )
        )

    @app.get("/api/v1/agents")
    def list_agents(limit: int = 100, _: None = Depends(auth)) -> list[dict[str, Any]]:
        return store.list_agents(limit=limit)

    @app.get("/api/v1/agents/{agent_id}")
    def get_agent(agent_id: str, _: None = Depends(auth)) -> dict[str, Any]:
        row = store.get_agent(agent_id)
        if not row:
            raise HTTPException(status_code=404, detail="agent not found")
        return row

    @app.post("/api/v1/policies")
    def register_policy(body: PolicyBody, _: None = Depends(auth)) -> dict[str, Any]:
        return store.register_policy(
            PolicyRegistration(
                policy_id=body.policy_id,
                version=body.version,
                name=body.name,
                bundle=body.bundle,
            )
        )

    @app.get("/api/v1/policies")
    def list_policies(limit: int = 100, _: None = Depends(auth)) -> list[dict[str, Any]]:
        return store.list_policies(limit=limit)

    @app.get("/api/v1/policies/{policy_id}/{version}")
    def get_policy(
        policy_id: str, version: str, _: None = Depends(auth)
    ) -> dict[str, Any]:
        row = store.get_policy(policy_id, version)
        if not row:
            raise HTTPException(status_code=404, detail="policy not found")
        return row

    @app.get("/api/v1/executions")
    def list_executions(
        agent_id: str | None = None,
        status: str | None = None,
        action: str | None = None,
        limit: int = 50,
        _: None = Depends(auth),
    ) -> list[dict[str, Any]]:
        return store.list_executions(
            agent_id=agent_id, status=status, action=action, limit=limit
        )

    @app.get("/api/v1/executions/{execution_id}")
    def get_execution(execution_id: str, _: None = Depends(auth)) -> dict[str, Any]:
        detail = store.get_execution_detail(execution_id)
        if not detail:
            raise HTTPException(status_code=404, detail="execution not found")
        return detail

    @app.get("/api/v1/approvals/pending")
    def pending_approvals(limit: int = 50, _: None = Depends(auth)) -> list[dict[str, Any]]:
        items = store.ledger.list_approval_requests(status="PENDING", limit=limit)
        out: list[dict[str, Any]] = []
        for item in items:
            ex = store.ledger.get_execution(item.execution_id) or {}
            out.append(
                {
                    "approval_id": item.approval_id,
                    "execution_id": item.execution_id,
                    "requested_at": item.requested_at,
                    "expires_at": item.expires_at,
                    "agent_id": ex.get("agent_id"),
                    "action": ex.get("action"),
                    "resource": ex.get("resource"),
                }
            )
        return out

    @app.post("/api/v1/approvals/{approval_id}/grant")
    def grant_approval(
        approval_id: str, body: ApprovalDecisionBody, _: None = Depends(auth)
    ) -> dict[str, str]:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        execution_id = store.ledger.grant_approval(approval_id, body.decided_by, now)
        return {"status": "granted", "execution_id": execution_id}

    @app.post("/api/v1/approvals/{approval_id}/deny")
    def deny_approval(
        approval_id: str, body: ApprovalDecisionBody, _: None = Depends(auth)
    ) -> dict[str, str]:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        reason = body.reason or "denied"
        execution_id = store.ledger.deny_approval(
            approval_id, body.decided_by, reason, now
        )
        return {"status": "denied", "execution_id": execution_id}

    @app.post("/api/v1/events/batch")
    def ingest_events(body: EventBatchBody, _: None = Depends(auth)) -> dict[str, object]:
        return store.ingest_events_batch(body.events)

    @app.get("/api/v1/events/stream")
    def events_stream(request: Request, _: None = Depends(auth)) -> StreamingResponse:
        last_event_id = request.headers.get("Last-Event-ID")
        replay_from = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

        def _format(msg: dict[str, object]) -> str:
            return (
                f"id: {msg['id']}\n"
                f"event: {msg['type']}\n"
                f"data: {json.dumps(msg['data'])}\n\n"
            )

        def event_generator():
            last_id = replay_from
            for msg in store.bus.replay_after(replay_from):
                last_id = msg["id"]
                yield _format(msg)
            while True:
                for msg in store.bus.replay_after(last_id):
                    last_id = msg["id"]
                    yield _format(msg)
                yield ": keepalive\n\n"
                store.bus.wait_for_updates(last_id, timeout=15.0)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.post("/api/v1/webhooks/destinations")
    def add_webhook(body: WebhookDestinationBody, _: None = Depends(auth)) -> dict[str, object]:
        dest = store.webhooks.add_destination(body.url, body.secret, body.event_types)
        return {k: v for k, v in dest.items() if k != "secret"}

    @app.get("/api/v1/webhooks/destinations")
    def list_webhooks(_: None = Depends(auth)) -> list[dict[str, object]]:
        return store.webhooks.list_destinations()

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

        @app.get("/")
        def dashboard() -> FileResponse:
            return FileResponse(static_dir / "index.html")

    return app


def default_store(data_dir: str) -> ControlPlaneStore:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    return ControlPlaneStore(
        plane_db_path=str(base / "control_plane.sqlite3"),
        ledger_path=str(base / "sqube_ledger.sqlite3"),
    )
