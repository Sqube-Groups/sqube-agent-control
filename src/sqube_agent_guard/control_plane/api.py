from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
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
