from __future__ import annotations

import json
import secrets
import urllib.parse
import urllib.request
from typing import Any


def oidc_authorize_url(provider: dict[str, Any], redirect_uri: str, state: str) -> str:
    cfg = provider["config"]
    issuer = cfg["issuer"].rstrip("/")
    client_id = cfg["client_id"]
    scope = cfg.get("scope") or "openid profile email"
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": scope,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{issuer}/authorize?{urllib.parse.urlencode(params)}"


def oidc_exchange_code(
    provider: dict[str, Any], code: str, redirect_uri: str
) -> dict[str, Any]:
    cfg = provider["config"]
    issuer = cfg["issuer"].rstrip("/")
    token_url = cfg.get("token_endpoint") or f"{issuer}/token"
    client_id = cfg["client_id"]
    client_secret = cfg.get("_client_secret") or cfg.get("client_secret")
    if not client_secret:
        raise ValueError("OIDC client secret not configured")

    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode()
    req = urllib.request.Request(
        token_url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    id_token = payload.get("id_token")
    if not id_token:
        raise ValueError("missing id_token")
    # Lightweight claim parse (JWT payload only; signature verified by token endpoint trust)
    parts = id_token.split(".")
    if len(parts) < 2:
        raise ValueError("invalid id_token")
    import base64

    pad = "=" * (-len(parts[1]) % 4)
    claims = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
    username = (
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("sub")
    )
    if not username:
        raise ValueError("no subject in id_token")
    return {"username": str(username), "email": claims.get("email"), "claims": claims}


def new_oidc_state() -> str:
    return secrets.token_urlsafe(24)
