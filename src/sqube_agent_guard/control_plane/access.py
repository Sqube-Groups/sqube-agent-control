from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request

from sqube_agent_guard.control_plane.identity import IdentityStore
from sqube_agent_guard.control_plane.rbac import PERM_ADMIN, PERM_APPROVE, PERM_READ_FLEET, Role


from sqube_agent_guard.control_plane.cookies import SESSION_COOKIE
CSRF_HEADER = "X-Sqube-CSRF-Token"


@dataclass
class Principal:
    kind: str  # session | ingest_key
    user_id: str | None = None
    username: str | None = None
    team_id: str | None = None
    role: Role | None = None
    session_id: str | None = None
    csrf_token: str | None = None

    def has_role(self, minimum: Role) -> bool:
        if self.kind == "ingest_key":
            return False
        if self.role is None:
            return False
        return int(self.role) >= int(minimum)


def _ingest_api_key_valid(request: Request) -> bool:
    expected = os.environ.get("SQUBE_API_KEY")
    if not expected:
        return False
    provided = request.headers.get("X-Sqube-Api-Key")
    return bool(provided and provided == expected)


def get_identity(request: Request) -> IdentityStore:
    store = request.app.state.control_plane_store
    return store.identity


def resolve_principal(
    request: Request, identity: IdentityStore, *, allow_ingest: bool = False
) -> Principal | None:
    if allow_ingest and _ingest_api_key_valid(request):
        return Principal(kind="ingest_key")

    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        session = identity.get_session(session_id)
        if session:
            return Principal(
                kind="session",
                user_id=session["user_id"],
                username=session["username"],
                team_id=session["team_id"],
                role=identity.effective_role(session),
                session_id=session_id,
                csrf_token=session["csrf_token"],
            )
    return None


def require_principal(
    request: Request,
    identity: Annotated[IdentityStore, Depends(get_identity)],
    minimum_role: Role = PERM_READ_FLEET,
    ingest_only: bool = False,
) -> Principal:
    if ingest_only:
        if not identity.auth_required():
            return Principal(kind="ingest_key")
        p = resolve_principal(request, identity, allow_ingest=True)
        if p and p.kind == "ingest_key":
            return p
        raise HTTPException(status_code=401, detail="ingest API key required")

    if identity.setup_required():
        raise HTTPException(status_code=401, detail="setup_required")

    principal = resolve_principal(request, identity)
    if not principal or principal.kind != "session":
        raise HTTPException(status_code=401, detail="authentication required")
    if not principal.has_role(minimum_role):
        raise HTTPException(status_code=403, detail="insufficient role")
    return principal


def require_csrf(
    request: Request,
    principal: Principal,
) -> None:
    if not principal.session_id or not principal.csrf_token:
        return
    token = request.headers.get(CSRF_HEADER)
    if token != principal.csrf_token:
        raise HTTPException(status_code=403, detail="invalid CSRF token")


def role_dependency(minimum: Role) -> Callable[..., Principal]:
    def _dep(
        request: Request,
        identity: Annotated[IdentityStore, Depends(get_identity)],
    ) -> Principal:
        return require_principal(request, identity, minimum_role=minimum)

    return _dep


RequireViewer = Annotated[Principal, Depends(role_dependency(PERM_READ_FLEET))]
RequireOperator = Annotated[Principal, Depends(role_dependency(PERM_APPROVE))]
RequireAdmin = Annotated[Principal, Depends(role_dependency(PERM_ADMIN))]
