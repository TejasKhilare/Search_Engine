from datetime import UTC, datetime
from typing import Any

from fastapi import Response

from app.core.config import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"


def _refresh_cookie_path() -> str:
    # Refresh token is only ever sent to the auth endpoints
    return f"{settings.API_V1_PREFIX}/auth"


def _common() -> dict[str, Any]:
    return {
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "domain": settings.COOKIE_DOMAIN,
    }


def _max_age(expires_at: datetime) -> int:
    return max(0, int((expires_at - datetime.now(UTC)).total_seconds()))


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    access_expires_at: datetime,
    refresh_token: str,
    refresh_expires_at: datetime,
    csrf_token: str,
) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=_max_age(access_expires_at),
        httponly=True,
        path=settings.API_V1_PREFIX,
        **_common(),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=_max_age(refresh_expires_at),
        httponly=True,
        path=_refresh_cookie_path(),
        **_common(),
    )
    # Readable by JS so a same-site frontend can echo it in the X-CSRF-Token header
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=_max_age(refresh_expires_at),
        httponly=False,
        path="/",
        **_common(),
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path=settings.API_V1_PREFIX, **_common())
    response.delete_cookie(REFRESH_COOKIE, path=_refresh_cookie_path(), **_common())
    response.delete_cookie(CSRF_COOKIE, path="/", **_common())
