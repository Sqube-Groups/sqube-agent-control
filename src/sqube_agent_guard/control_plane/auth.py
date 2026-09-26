"""Legacy API-key helper — event ingest uses access.require_principal(ingest_only=True)."""

from __future__ import annotations

import os

from fastapi import HTTPException, Request


def verify_ingest_api_key(request: Request) -> None:
    expected = os.environ.get("SQUBE_API_KEY")
    if not expected:
        return
    provided = request.headers.get("X-Sqube-Api-Key")
    if provided != expected:
        raise HTTPException(status_code=401, detail="invalid or missing API key")
