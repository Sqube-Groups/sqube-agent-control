from __future__ import annotations

import os

from fastapi import Response

SESSION_COOKIE = "sqube_session"
SESSION_MAX_AGE = 86400
COOKIE_PATH = "/"


def _secure_flag() -> bool:
    return os.environ.get("SQUBE_COOKIE_SECURE", "").lower() in ("1", "true", "yes")


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_secure_flag(),
        path=COOKIE_PATH,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=_secure_flag(),
    )
