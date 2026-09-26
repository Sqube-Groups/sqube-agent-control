from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sqube_agent_guard.control_plane.access import (
    CSRF_HEADER,
    RequireAdmin,
    RequireOperator,
    RequireViewer,
    get_identity,
    require_csrf,
    require_principal,
)
from sqube_agent_guard.control_plane.cookies import SESSION_COOKIE, clear_session_cookie, set_session_cookie
from sqube_agent_guard.control_plane.identity import IdentityStore
from sqube_agent_guard.control_plane.models import AgentRegistration, PolicyRegistration
from sqube_agent_guard.control_plane.rbac import Role, role_name
from sqube_agent_guard.control_plane.sso_oidc import (
    new_oidc_state,
    oidc_authorize_url,
    oidc_exchange_code,
)
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
    policy_version: str | None = None


class PolicyBody(BaseModel):
    policy_id: str
    version: str = "1"
    name: str | None = None
    bundle: dict[str, Any]
    set_active: bool = True


class ApprovalDecisionBody(BaseModel):
    reason: str | None = None


class EventBatchBody(BaseModel):
    events: list[dict[str, Any]]


class WebhookDestinationBody(BaseModel):
    url: str
    secret: str
    event_types: list[str]


class LoginBody(BaseModel):
    username: str
    password: str
    team_id: str | None = None


class SetupBody(BaseModel):
    username: str = "admin"
    password: str
    email: str | None = None
    team_name: str = "Default team"


class TeamBody(BaseModel):
    name: str


class TeamMemberBody(BaseModel):
    username: str
    role: str
    password: str | None = None


class SsoProviderBody(BaseModel):
    provider_id: str | None = None
    team_id: str | None = None
    protocol: str
    display_name: str
    enabled: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class AgentPolicyBody(BaseModel):
    policy_id: str
    policy_version: str | None = None


def create_app(store: ControlPlaneStore) -> FastAPI:
    app = FastAPI(title="Sqube Control Plane", version="1.0.0")
    app.state.control_plane_store = store
    app.state.oidc_states: dict[str, str] = {}

    def _actor(principal) -> dict[str, Any]:
        return {
            "user_id": principal.user_id,
            "username": principal.username,
            "team_id": principal.team_id,
        }

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/auth/config")
    def auth_config(identity: Annotated[IdentityStore, Depends(get_identity)]) -> dict[str, object]:
        return {
            "setup_required": identity.setup_required(),
            "auth_required": identity.auth_required(),
            "sso_providers": identity.list_sso_providers(public=True) if identity.auth_required() else [],
        }

    @app.post("/api/v1/auth/setup")
    def auth_setup(
        body: SetupBody,
        response: Response,
        identity: Annotated[IdentityStore, Depends(get_identity)],
    ) -> dict[str, object]:
        try:
            user = identity.setup_initial_admin(
                body.username,
                body.password,
                email=body.email,
                team_name=body.team_name,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session = identity.create_session(user["user_id"], user["team_id"])
        set_session_cookie(response, session["session_id"])
        return {
            "username": user["username"],
            "team_id": user["team_id"],
            "csrf_token": session["csrf_token"],
            "message": "Administrator created. Use this username and password to sign in next time.",
        }

    @app.post("/api/v1/auth/login")
    def login(
        body: LoginBody,
        request: Request,
        response: Response,
        identity: Annotated[IdentityStore, Depends(get_identity)],
    ) -> dict[str, object]:
        user = identity.authenticate_local(body.username, body.password)
        if not user:
            raise HTTPException(status_code=401, detail="invalid credentials")
        teams = identity.user_teams(user["user_id"])
        if not teams and not user["is_platform_admin"]:
            raise HTTPException(status_code=403, detail="user has no team membership")
        team_id = body.team_id or (teams[0]["team_id"] if teams else "sq_team_default")
        old_sid = request.cookies.get(SESSION_COOKIE)
        if old_sid:
            identity.delete_session(old_sid)
        clear_session_cookie(response)
        session = identity.create_session(user["user_id"], team_id)
        set_session_cookie(response, session["session_id"])
        identity.audit(team_id, user["user_id"], user["username"], "auth.login", "session", None, {})
        sess = identity.get_session(session["session_id"]) or {}
        return {
            "username": user["username"],
            "team_id": team_id,
            "role": sess.get("role"),
            "csrf_token": session["csrf_token"],
            "teams": teams,
        }

    @app.post("/api/v1/auth/logout")
    def logout(
        request: Request,
        response: Response,
        identity: Annotated[IdentityStore, Depends(get_identity)],
    ) -> dict[str, str]:
        sid = request.cookies.get(SESSION_COOKIE)
        if sid:
            identity.delete_session(sid)
            identity.audit(None, None, None, "auth.logout", "session", sid, {})
        clear_session_cookie(response)
        return {"status": "logged_out"}

    @app.get("/api/v1/auth/me")
    def auth_me(
        request: Request,
        identity: Annotated[IdentityStore, Depends(get_identity)],
    ) -> dict[str, object]:
        if identity.setup_required():
            raise HTTPException(status_code=401, detail="setup_required")
        principal = require_principal(request, identity)
        csrf_token = principal.csrf_token
        if principal.session_id and not csrf_token:
            sess = identity.get_session(principal.session_id)
            csrf_token = sess.get("csrf_token") if sess else None
        return {
            "authenticated": True,
            "username": principal.username,
            "role": role_name(principal.role) if principal.role else None,
            "team_id": principal.team_id,
            "teams": identity.user_teams(principal.user_id or ""),
            "csrf_token": csrf_token,
        }

    @app.get("/api/v1/auth/sso/{provider_id}/start")
    def sso_start(
        provider_id: str,
        request: Request,
        identity: Annotated[IdentityStore, Depends(get_identity)],
    ) -> RedirectResponse:
        provider = identity.get_sso_provider(provider_id)
        if not provider or not provider.get("enabled"):
            raise HTTPException(status_code=404, detail="SSO provider not found")
        protocol = provider["protocol"].lower()
        if protocol == "saml":
            raise HTTPException(
                status_code=501,
                detail="SAML login requires enterprise SAML module; use OIDC (Azure AD, Okta, Google) or configure SAML ACS separately",
            )
        if protocol != "oidc":
            raise HTTPException(status_code=400, detail="unsupported SSO protocol")
        state = new_oidc_state()
        app.state.oidc_states[state] = provider_id
        redirect_uri = str(request.url_for("sso_callback", provider_id=provider_id))
        url = oidc_authorize_url(provider, redirect_uri, state)
        return RedirectResponse(url)

    @app.get("/api/v1/auth/sso/{provider_id}/callback", name="sso_callback")
    def sso_callback(
        provider_id: str,
        request: Request,
        response: Response,
        identity: Annotated[IdentityStore, Depends(get_identity)],
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> Response:
        if error:
            raise HTTPException(status_code=400, detail=f"SSO error: {error}")
        if not code or not state or app.state.oidc_states.get(state) != provider_id:
            raise HTTPException(status_code=400, detail="invalid SSO state")
        app.state.oidc_states.pop(state, None)
        provider = identity.get_sso_provider(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="provider not found")
        redirect_uri = str(request.url_for("sso_callback", provider_id=provider_id))
        try:
            profile = oidc_exchange_code(provider, code, redirect_uri)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        username = profile["username"]
        team_id = provider.get("team_id") or "sq_team_default"
        default_role = (provider.get("config") or {}).get("default_role", "viewer")
        user_id = identity.provision_sso_user(
            username, profile.get("email"), team_id, default_role
        )
        session = identity.create_session(user_id, team_id)
        redirect = RedirectResponse(url="/")
        set_session_cookie(redirect, session["session_id"])
        identity.audit(team_id, user_id, username, "auth.sso_login", "sso_provider", provider_id, {})
        return redirect

    @app.post("/api/v1/auth/saml/{provider_id}/acs")
    def saml_acs(provider_id: str) -> JSONResponse:
        return JSONResponse(
            status_code=501,
            content={
                "detail": "SAML ACS endpoint reserved; configure OIDC for Azure AD / Entra ID or install SAML enterprise module",
                "provider_id": provider_id,
            },
        )

    @app.get("/api/v1/overview")
    def overview(principal: RequireViewer) -> dict[str, Any]:
        return store.overview()

    @app.post("/api/v1/agents")
    def register_agent(body: AgentBody, principal: RequireAdmin, request: Request) -> dict[str, Any]:
        require_csrf(request, principal)
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
                policy_version=body.policy_version,
            ),
            actor_username=principal.username,
        )

    @app.patch("/api/v1/agents/{agent_id}/policy")
    def assign_policy(
        agent_id: str,
        body: AgentPolicyBody,
        principal: RequireAdmin,
        request: Request,
    ) -> dict[str, Any]:
        require_csrf(request, principal)
        try:
            return store.assign_agent_policy(
                agent_id, body.policy_id, body.policy_version, principal.username
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/agents")
    def list_agents(principal: RequireViewer, limit: int = 100) -> list[dict[str, Any]]:
        return store.list_agents(limit=limit)

    @app.get("/api/v1/agents/{agent_id}")
    def get_agent(agent_id: str, principal: RequireViewer) -> dict[str, Any]:
        row = store.get_agent(agent_id)
        if not row:
            raise HTTPException(status_code=404, detail="agent not found")
        return row

    @app.post("/api/v1/policies")
    def register_policy(body: PolicyBody, principal: RequireAdmin, request: Request) -> dict[str, Any]:
        require_csrf(request, principal)
        return store.register_policy(
            PolicyRegistration(
                policy_id=body.policy_id,
                version=body.version,
                name=body.name,
                bundle=body.bundle,
            ),
            actor_username=principal.username,
            set_active=body.set_active,
        )

    @app.get("/api/v1/policies")
    def list_policies(principal: RequireViewer, limit: int = 100) -> list[dict[str, Any]]:
        policies = store.list_policies(limit=limit)
        for p in policies:
            p["active_version"] = store.identity.get_active_policy_version(p["policy_id"])
            p["is_active"] = p["active_version"] == p["version"]
        return policies

    @app.get("/api/v1/policies/{policy_id}/{version}")
    def get_policy(policy_id: str, version: str, principal: RequireViewer) -> dict[str, Any]:
        row = store.get_policy(policy_id, version)
        if not row:
            raise HTTPException(status_code=404, detail="policy not found")
        row["history"] = store.identity.list_policy_history(policy_id)
        row["active_version"] = store.identity.get_active_policy_version(policy_id)
        return row

    @app.get("/api/v1/executions")
    def list_executions(
        principal: RequireViewer,
        agent_id: str | None = None,
        status: str | None = None,
        action: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return store.list_executions(
            agent_id=agent_id, status=status, action=action, limit=limit
        )

    @app.get("/api/v1/executions/{execution_id}")
    def get_execution(execution_id: str, principal: RequireViewer) -> dict[str, Any]:
        detail = store.get_execution_detail(execution_id)
        if not detail:
            raise HTTPException(status_code=404, detail="execution not found")
        return detail

    @app.get("/api/v1/approvals/pending")
    def pending_approvals(principal: RequireViewer, limit: int = 50) -> list[dict[str, Any]]:
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
        approval_id: str,
        body: ApprovalDecisionBody,
        principal: RequireOperator,
        request: Request,
    ) -> dict[str, str]:
        require_csrf(request, principal)
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        decided_by = principal.username or "operator"
        execution_id = store.ledger.grant_approval(approval_id, decided_by, now)
        store.identity.audit(
            principal.team_id,
            principal.user_id,
            principal.username,
            "approval.granted",
            "approval",
            approval_id,
            {"execution_id": execution_id, "reason": body.reason},
        )
        return {"status": "granted", "execution_id": execution_id}

    @app.post("/api/v1/approvals/{approval_id}/deny")
    def deny_approval(
        approval_id: str,
        body: ApprovalDecisionBody,
        principal: RequireOperator,
        request: Request,
    ) -> dict[str, str]:
        require_csrf(request, principal)
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        decided_by = principal.username or "operator"
        reason = body.reason or "denied"
        execution_id = store.ledger.deny_approval(approval_id, decided_by, reason, now)
        store.identity.audit(
            principal.team_id,
            principal.user_id,
            principal.username,
            "approval.denied",
            "approval",
            approval_id,
            {"execution_id": execution_id, "reason": reason},
        )
        return {"status": "denied", "execution_id": execution_id}

    @app.post("/api/v1/events/batch")
    def ingest_events(
        body: EventBatchBody,
        request: Request,
        identity: Annotated[IdentityStore, Depends(get_identity)],
    ) -> dict[str, object]:
        if identity.auth_required():
            require_principal(request, identity, minimum_role=Role.VIEWER, ingest_only=True)
        return store.ingest_events_batch(body.events)

    @app.get("/api/v1/events/stream")
    def events_stream(
        request: Request,
        identity: Annotated[IdentityStore, Depends(get_identity)],
    ) -> StreamingResponse:
        require_principal(request, identity, minimum_role=Role.VIEWER)

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
    def add_webhook(
        body: WebhookDestinationBody,
        principal: RequireAdmin,
        request: Request,
    ) -> dict[str, object]:
        require_csrf(request, principal)
        dest = store.webhooks.add_destination(body.url, body.secret, body.event_types)
        store.identity.audit(
            principal.team_id,
            principal.user_id,
            principal.username,
            "webhook.created",
            "webhook",
            dest.get("destination_id"),
            {"url": body.url, "event_types": body.event_types},
        )
        return {k: v for k, v in dest.items() if k != "secret"}

    @app.get("/api/v1/webhooks/destinations")
    def list_webhooks(principal: RequireAdmin) -> list[dict[str, object]]:
        return store.webhooks.list_destinations()

    @app.get("/api/v1/admin/teams")
    def list_teams(principal: RequireAdmin) -> list[dict[str, Any]]:
        return store.identity.list_teams()

    @app.post("/api/v1/admin/teams")
    def create_team(
        body: TeamBody, principal: RequireAdmin, request: Request
    ) -> dict[str, Any]:
        require_csrf(request, principal)
        return store.identity.create_team(body.name, _actor(principal))

    @app.get("/api/v1/admin/teams/{team_id}/members")
    def team_members(team_id: str, principal: RequireAdmin) -> list[dict[str, Any]]:
        return store.identity.list_team_members(team_id)

    @app.post("/api/v1/admin/teams/{team_id}/members")
    def add_member(
        team_id: str,
        body: TeamMemberBody,
        principal: RequireAdmin,
        request: Request,
    ) -> dict[str, Any]:
        require_csrf(request, principal)
        try:
            return store.identity.add_team_member(
                team_id, body.username, body.role, body.password, _actor(principal)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/admin/sso/providers")
    def list_sso_admin(principal: RequireAdmin) -> list[dict[str, Any]]:
        return store.identity.list_sso_providers(public=False)

    @app.post("/api/v1/admin/sso/providers")
    def upsert_sso(
        body: SsoProviderBody, principal: RequireAdmin, request: Request
    ) -> dict[str, Any]:
        require_csrf(request, principal)
        return store.identity.upsert_sso_provider(body.model_dump(), _actor(principal))

    @app.get("/api/v1/admin/audit")
    def audit_log(principal: RequireAdmin, limit: int = 100) -> list[dict[str, Any]]:
        return store.identity.list_audit(limit=limit)

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

        @app.get("/")
        def dashboard() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        @app.get("/login")
        def login_page() -> FileResponse:
            return FileResponse(static_dir / "login.html")

        @app.get("/setup")
        def setup_page() -> FileResponse:
            return FileResponse(static_dir / "setup.html")

    return app


def default_store(data_dir: str) -> ControlPlaneStore:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    return ControlPlaneStore(
        plane_db_path=str(base / "control_plane.sqlite3"),
        ledger_path=str(base / "sqube_ledger.sqlite3"),
    )
