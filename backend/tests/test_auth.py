import uuid
from datetime import UTC, datetime, timedelta

import jwt
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.models import RefreshToken

AUTH = f"{settings.API_V1_PREFIX}/auth"
PASSWORD = "Secret123!"


async def _register(client: AsyncClient, **overrides: str) -> dict:
    suffix = uuid.uuid4().hex[:8]
    body = {"email": f"User{suffix}@Example.com", "username": f"user_{suffix}", "password": PASSWORD}
    body.update(overrides)
    res = await client.post(f"{AUTH}/register", json=body)
    assert res.status_code == 201, res.text
    return body


async def _login(client: AsyncClient) -> tuple[dict, dict]:
    creds = await _register(client)
    res = await client.post(f"{AUTH}/login", json={"email": creds["email"], "password": PASSWORD})
    assert res.status_code == 200, res.text
    return creds, res.json()


def _cookie_only(client: AsyncClient, **cookies: str) -> dict[str, str]:
    """Drop the client's cookie jar and send exactly these cookies."""
    client.cookies.clear()
    return {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}


# ── Registration ─────────────────────────────────────────────────────────────
async def test_register_normalises_email_and_hides_password(client: AsyncClient) -> None:
    res = await client.post(
        f"{AUTH}/register", json={"email": "Jane@Example.COM", "username": "jane_doe", "password": PASSWORD}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "jane@example.com"
    assert "password" not in body and "password_hash" not in body


async def test_register_duplicate_email_or_username(client: AsyncClient) -> None:
    creds = await _register(client)
    res = await client.post(
        f"{AUTH}/register",
        json={"email": creds["email"].upper(), "username": "someone_else", "password": PASSWORD},
    )
    assert res.status_code == 409
    res = await client.post(
        f"{AUTH}/register",
        json={"email": "other@example.com", "username": creds["username"].upper(), "password": PASSWORD},
    )
    assert res.status_code == 409


async def test_register_rejects_weak_password(client: AsyncClient) -> None:
    res = await client.post(
        f"{AUTH}/register", json={"email": "a@example.com", "username": "abc", "password": "onlyletters"}
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


# ── Login ────────────────────────────────────────────────────────────────────
async def test_login_sets_secure_cookies(client: AsyncClient) -> None:
    creds = await _register(client)
    res = await client.post(f"{AUTH}/login", json={"email": creds["email"], "password": PASSWORD})
    assert res.status_code == 200

    set_cookie = res.headers.get_list("set-cookie")
    by_name = {c.split("=", 1)[0]: c.lower() for c in set_cookie}
    assert "httponly" in by_name["access_token"]
    assert "httponly" in by_name["refresh_token"]
    assert f"path={AUTH}".lower() in by_name["refresh_token"]
    assert "httponly" not in by_name["csrf_token"]  # frontend must be able to read it
    assert all("samesite=lax" in c for c in by_name.values())

    body = res.json()
    assert body["csrf_token"]
    assert "access_token" not in body  # tokens never exposed to JS


async def test_login_failures_are_indistinguishable(client: AsyncClient) -> None:
    creds = await _register(client)
    wrong_pw = await client.post(f"{AUTH}/login", json={"email": creds["email"], "password": "Wrong1234"})
    no_user = await client.post(
        f"{AUTH}/login", json={"email": "nobody@example.com", "password": "Wrong1234"}
    )
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["error"]["message"] == no_user.json()["error"]["message"]


async def test_me_with_cookie(client: AsyncClient) -> None:
    creds, _ = await _login(client)
    res = await client.get(f"{AUTH}/me")
    assert res.status_code == 200
    assert res.json()["email"] == creds["email"].lower()


async def test_me_with_bearer_token(client: AsyncClient) -> None:
    creds = await _register(client)
    res = await client.post(f"{AUTH}/token", data={"username": creds["email"], "password": PASSWORD})
    assert res.status_code == 200
    token = res.json()["access_token"]

    client.cookies.clear()
    res = await client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


async def test_unauthenticated_and_tampered_tokens_rejected(client: AsyncClient) -> None:
    assert (await client.get(f"{AUTH}/me")).status_code == 401

    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "sid": str(uuid.uuid4()),
            "type": "access",
            "iss": settings.JWT_ISSUER,
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "not-the-real-secret-key-at-all-0123456789",
        algorithm="HS256",
    )
    res = await client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401

    unsigned = jwt.encode({"sub": str(uuid.uuid4())}, key=None, algorithm="none")
    res = await client.get(f"{AUTH}/me", headers={"Authorization": f"Bearer {unsigned}"})
    assert res.status_code == 401


# ── CSRF ─────────────────────────────────────────────────────────────────────
async def test_cookie_auth_requires_csrf_on_unsafe_methods(client: AsyncClient) -> None:
    _, body = await _login(client)

    res = await client.post(f"{AUTH}/logout-all")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "csrf_failed"

    res = await client.post(f"{AUTH}/logout-all", headers={"X-CSRF-Token": "forged"})
    assert res.status_code == 403

    res = await client.post(f"{AUTH}/logout-all", headers={"X-CSRF-Token": body["csrf_token"]})
    assert res.status_code == 204


async def test_bearer_auth_does_not_need_csrf(client: AsyncClient) -> None:
    creds = await _register(client)
    token = (
        await client.post(f"{AUTH}/token", data={"username": creds["email"], "password": PASSWORD})
    ).json()
    client.cookies.clear()
    res = await client.post(
        f"{AUTH}/logout-all", headers={"Authorization": f"Bearer {token['access_token']}"}
    )
    assert res.status_code == 204


# ── Refresh rotation & reuse detection ───────────────────────────────────────
async def test_refresh_rotates_tokens(client: AsyncClient) -> None:
    await _login(client)
    old_refresh = client.cookies.get("refresh_token")

    res = await client.post(f"{AUTH}/refresh")
    assert res.status_code == 200
    new_refresh = res.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh
    assert (await client.get(f"{AUTH}/me")).status_code == 200


async def test_refresh_without_cookie_is_401(client: AsyncClient) -> None:
    res = await client.post(f"{AUTH}/refresh")
    assert res.status_code == 401


async def test_concurrent_refresh_within_grace_keeps_session(client: AsyncClient) -> None:
    await _login(client)
    old_refresh = client.cookies.get("refresh_token")
    await client.post(f"{AUTH}/refresh")
    new_access = client.cookies.get("access_token")

    # Second tab replays the old token a moment later: rejected, but session survives
    res = await client.post(f"{AUTH}/refresh", headers=_cookie_only(client, refresh_token=old_refresh))
    assert res.status_code == 401
    res = await client.get(f"{AUTH}/me", headers=_cookie_only(client, access_token=new_access))
    assert res.status_code == 200


async def test_refresh_token_reuse_revokes_session(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login(client)
    stolen = client.cookies.get("refresh_token")
    await client.post(f"{AUTH}/refresh")
    legit_access = client.cookies.get("access_token")
    legit_refresh = client.cookies.get("refresh_token")

    # Move the rotation outside the grace window, then the attacker replays the stolen token
    await db_session.execute(
        update(RefreshToken)
        .where(RefreshToken.replaced_by_id.is_not(None))
        .values(revoked_at=datetime.now(UTC) - timedelta(minutes=5))
    )
    res = await client.post(f"{AUTH}/refresh", headers=_cookie_only(client, refresh_token=stolen))
    assert res.status_code == 401

    # The whole family is dead: the legitimate user's tokens stop working too
    res = await client.get(f"{AUTH}/me", headers=_cookie_only(client, access_token=legit_access))
    assert res.status_code == 401
    res = await client.post(f"{AUTH}/refresh", headers=_cookie_only(client, refresh_token=legit_refresh))
    assert res.status_code == 401

    live = await db_session.scalar(select(RefreshToken).where(RefreshToken.revoked_at.is_(None)))
    assert live is None


# ── Logout ───────────────────────────────────────────────────────────────────
async def test_logout_invalidates_access_token_immediately(client: AsyncClient) -> None:
    await _login(client)
    access = client.cookies.get("access_token")

    res = await client.post(f"{AUTH}/logout")
    assert res.status_code == 204
    assert 'access_token=""' in res.headers.get("set-cookie", "")

    # Access token is still within its 15 minutes, but the session is gone
    res = await client.get(f"{AUTH}/me", headers=_cookie_only(client, access_token=access))
    assert res.status_code == 401


async def test_logout_is_idempotent(client: AsyncClient) -> None:
    assert (await client.post(f"{AUTH}/logout")).status_code == 204


# ── Rate limiting ────────────────────────────────────────────────────────────
async def test_login_is_rate_limited(client: AsyncClient) -> None:
    limiter.enabled = True
    limiter.reset()
    try:
        limit = int(settings.RATE_LIMIT_AUTH.split("/")[0])
        statuses = [
            (
                await client.post(f"{AUTH}/login", json={"email": "x@example.com", "password": "Wrong1234"})
            ).status_code
            for _ in range(limit + 1)
        ]
        assert statuses[:limit] == [401] * limit
        assert statuses[-1] == 429
    finally:
        limiter.reset()
        limiter.enabled = False
