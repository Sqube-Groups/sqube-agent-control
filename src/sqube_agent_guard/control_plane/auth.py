from __future__ import annotations

import os
from typing import Callable

from fastapi import HTTPException, Request


def verify_request_auth(request: Request) -> None:
    expected = os.environ.get("SQUBE_API_KEY")
    if not expected:
        return
    provided = request.headers.get("X-Sqube-Api-Key") or request.query_params.get(
        "access_token"
    )
    if provided != expected:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def api_key_dependency() -> Callable[[Request], None]:
    def _check(request: Request) -> None:
        verify_request_auth(request)

    return _check
