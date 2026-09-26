from __future__ import annotations

import os
from typing import Callable

from fastapi import HTTPException, Request


def api_key_dependency() -> Callable[[Request], None]:
    expected = os.environ.get("SQUBE_API_KEY")

    def _check(request: Request) -> None:
        if not expected:
            return
        provided = request.headers.get("X-Sqube-Api-Key")
        if provided != expected:
            raise HTTPException(status_code=401, detail="invalid or missing API key")

    return _check
