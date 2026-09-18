"""
Periodic housekeeping. Every task is idempotent and safe to run concurrently; a
Postgres advisory lock still ensures only one instance does the work per cycle.
"""

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models import Document, RefreshToken, SearchLog
from app.services.storage import ObjectStorage, get_storage

logger = logging.getLogger(__name__)

_ADVISORY_LOCK_ID = 7_310_442_001  # arbitrary constant identifying this job
_DOCUMENTS_PREFIX = "users/"
_KEY_BATCH = 1000


@dataclass(frozen=True, slots=True)
class MaintenanceReport:
    refresh_tokens_deleted: int
    search_logs_deleted: int
    orphan_objects_deleted: int


async def purge_expired_refresh_tokens(db: AsyncSession) -> int:
    """
    Deletes refresh tokens that expired over a day ago. Revoked-but-unexpired tokens
    are kept on purpose: they are what makes refresh-token reuse detectable.
    """
    cutoff = datetime.now(UTC) - timedelta(days=1)
    result = await db.execute(delete(RefreshToken).where(RefreshToken.expires_at < cutoff))
    await db.commit()
    return result.rowcount or 0


async def purge_old_search_logs(db: AsyncSession) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=settings.SEARCH_LOG_RETENTION_DAYS)
    result = await db.execute(delete(SearchLog).where(SearchLog.created_at < cutoff))
    await db.commit()
    return result.rowcount or 0


async def delete_orphan_objects(db: AsyncSession, storage: ObjectStorage) -> int:
    """Removes stored files whose document row no longer exists (e.g. a failed blob delete)."""
    min_age = datetime.now(UTC) - timedelta(minutes=settings.ORPHAN_OBJECT_MIN_AGE_MINUTES)
    candidates = [o.key for o in await storage.list_objects(_DOCUMENTS_PREFIX) if o.last_modified < min_age]

    deleted = 0
    for i in range(0, len(candidates), _KEY_BATCH):
        batch = candidates[i : i + _KEY_BATCH]
        known = set(await db.scalars(select(Document.storage_key).where(Document.storage_key.in_(batch))))
        for key in batch:
            if key not in known:
                await storage.delete(key)
                deleted += 1
                logger.info("Deleted orphan storage object %s", key)
    return deleted


async def run_maintenance(db: AsyncSession, storage: ObjectStorage) -> MaintenanceReport | None:
    """Runs all tasks if this instance wins the advisory lock; otherwise returns None."""
    # Session-level advisory locks belong to a connection, and a session may switch
    # connections between commits, so the lock is held on its own connection.
    async with engine.connect() as lock_conn:
        acquired = await lock_conn.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": _ADVISORY_LOCK_ID})
        if not acquired:
            return None
        try:
            report = MaintenanceReport(
                refresh_tokens_deleted=await purge_expired_refresh_tokens(db),
                search_logs_deleted=await purge_old_search_logs(db),
                orphan_objects_deleted=await delete_orphan_objects(db, storage),
            )
        finally:
            await lock_conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _ADVISORY_LOCK_ID})
    logger.info("Maintenance complete", extra=asdict(report))
    return report


async def maintenance_loop() -> None:
    """Runs maintenance every MAINTENANCE_INTERVAL_MINUTES until cancelled."""
    interval = settings.MAINTENANCE_INTERVAL_MINUTES * 60
    while True:
        await asyncio.sleep(interval)
        try:
            async with SessionLocal() as db:
                await run_maintenance(db, get_storage())
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Maintenance run failed")
