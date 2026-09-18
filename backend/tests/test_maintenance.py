import io
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, RefreshToken, SearchLog, User
from app.services.maintenance import (
    delete_orphan_objects,
    purge_expired_refresh_tokens,
    purge_old_search_logs,
    run_maintenance,
)
from tests.fakes import InMemoryStorage


async def _user(db: AsyncSession) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(email=f"m{suffix}@example.com", username=f"m{suffix}", password_hash="x")
    db.add(user)
    await db.flush()
    return user


def _token(user: User, *, expires_in: timedelta, revoked: bool = False) -> RefreshToken:
    now = datetime.now(UTC)
    return RefreshToken(
        user_id=user.id,
        token_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        family_id=uuid.uuid4(),
        expires_at=now + expires_in,
        revoked_at=now if revoked else None,
    )


async def test_purges_only_long_expired_refresh_tokens(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    expired = _token(user, expires_in=-timedelta(days=2))
    just_expired = _token(user, expires_in=-timedelta(hours=1))
    revoked_live = _token(user, expires_in=timedelta(days=3), revoked=True)  # needed for reuse detection
    active = _token(user, expires_in=timedelta(days=3))
    db_session.add_all([expired, just_expired, revoked_live, active])
    await db_session.commit()

    await purge_expired_refresh_tokens(db_session)

    remaining = set(await db_session.scalars(select(RefreshToken.id).where(RefreshToken.user_id == user.id)))
    assert remaining == {just_expired.id, revoked_live.id, active.id}


async def test_purges_search_logs_past_retention(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    old = SearchLog(
        user_id=user.id,
        query="old",
        search_type="search",
        results_count=0,
        latency_ms=1,
        created_at=datetime.now(UTC) - timedelta(days=365),
    )
    recent = SearchLog(user_id=user.id, query="recent", search_type="search", results_count=0, latency_ms=1)
    db_session.add_all([old, recent])
    await db_session.commit()

    await purge_old_search_logs(db_session)

    remaining = set(await db_session.scalars(select(SearchLog.query).where(SearchLog.user_id == user.id)))
    assert remaining == {"recent"}


async def test_deletes_only_old_orphan_objects(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    storage = InMemoryStorage()
    referenced = f"users/{user.id}/documents/{uuid.uuid4()}.pdf"
    old_orphan = f"users/{user.id}/documents/{uuid.uuid4()}.pdf"
    new_orphan = f"users/{user.id}/documents/{uuid.uuid4()}.pdf"  # upload may still be committing
    for key in (referenced, old_orphan, new_orphan):
        await storage.put(key, io.BytesIO(b"%PDF-"), 5, "application/pdf")
    storage.modified[referenced] = storage.modified[old_orphan] = datetime.now(UTC) - timedelta(days=1)

    db_session.add(
        Document(
            user_id=user.id,
            filename="a.pdf",
            content_type="application/pdf",
            size_bytes=5,
            checksum_sha256="c" * 64,
            storage_key=referenced,
        )
    )
    await db_session.commit()

    deleted = await delete_orphan_objects(db_session, storage)

    assert deleted == 1
    assert set(storage.objects) == {referenced, new_orphan}


async def test_run_maintenance_takes_and_releases_lock(db_session: AsyncSession) -> None:
    storage = InMemoryStorage()
    first = await run_maintenance(db_session, storage)
    second = await run_maintenance(db_session, storage)  # lock was released, so it runs again
    assert first is not None and second is not None


# ── Security headers ─────────────────────────────────────────────────────────
async def test_security_headers_on_api_responses(client: AsyncClient) -> None:
    res = await client.get("/api/v1/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert res.headers["content-security-policy"].startswith("default-src 'none'")


async def test_docs_page_has_no_strict_csp(client: AsyncClient) -> None:
    res = await client.get("/docs")
    assert res.status_code == 200
    assert "content-security-policy" not in res.headers
    assert res.headers["x-content-type-options"] == "nosniff"
