"""
In-process job runner for document ingestion.

Jobs run on the API's event loop after the response is sent (CPU-heavy steps are
pushed to threads). A semaphore caps concurrent jobs. Documents left unfinished by
a crash or restart are picked up again on startup.

To move to a dedicated worker (ARQ/Celery), implement IngestionQueue.enqueue to
publish a message instead; process_document stays unchanged.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol

from fastapi import BackgroundTasks
from sqlalchemy import select, update

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Document, DocumentStatus
from app.services.embedding import get_embedder
from app.services.ingestion_service import process_document
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

_semaphore = asyncio.Semaphore(settings.INGESTION_CONCURRENCY)
_running: set[asyncio.Task[None]] = set()  # strong refs so tasks aren't garbage-collected


class IngestionQueue(Protocol):
    def enqueue(self, document_id: uuid.UUID) -> None: ...


async def run_ingestion_job(document_id: uuid.UUID) -> None:
    async with _semaphore:
        try:
            async with SessionLocal() as db:
                await process_document(db, get_storage(), get_embedder(), document_id)
        except Exception:
            logger.exception("Ingestion job crashed", extra={"document_id": str(document_id)})


class BackgroundTasksQueue:
    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self.background_tasks = background_tasks

    def enqueue(self, document_id: uuid.UUID) -> None:
        self.background_tasks.add_task(run_ingestion_job, document_id)


def get_ingestion_queue(background_tasks: BackgroundTasks) -> IngestionQueue:
    return BackgroundTasksQueue(background_tasks)


async def resume_unfinished_documents() -> int:
    """Re-queues pending documents and ones stuck in processing (e.g. after a crash)."""
    stale_before = datetime.now(UTC) - timedelta(minutes=settings.INGESTION_STALE_AFTER_MINUTES)
    async with SessionLocal() as db:
        await db.execute(
            update(Document)
            .where(Document.status == DocumentStatus.PROCESSING, Document.updated_at < stale_before)
            .values(status=DocumentStatus.PENDING)
        )
        ids = (
            await db.scalars(
                select(Document.id)
                .where(Document.status == DocumentStatus.PENDING)
                .order_by(Document.created_at)
            )
        ).all()
        await db.commit()

    for document_id in ids:
        task = asyncio.create_task(run_ingestion_job(document_id))
        _running.add(task)
        task.add_done_callback(_running.discard)
    return len(ids)
