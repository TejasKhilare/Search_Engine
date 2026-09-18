import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath

import openai
from sqlalchemy import delete, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Chunk, Document, DocumentStatus
from app.services.chunking import TextChunk, chunk_text
from app.services.embedding import Embedder
from app.services.pdf import PageText, extract_pages
from app.services.storage import ObjectStorage

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """A failure whose message is safe and useful to show the user."""


def _user_facing_error(exc: Exception) -> str:
    if isinstance(exc, IngestionError):
        return str(exc)
    if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
        return "Embedding service rejected our credentials. Contact support."
    if isinstance(exc, openai.APIError):  # rate limits, timeouts, 5xx after retries
        return "Embedding service is temporarily unavailable. Please retry."
    return "Processing failed due to an internal error. Please retry."


def _document_title(filename: str) -> str:
    return PurePosixPath(filename).stem.replace("_", " ").replace("-", " ").strip()


def embedding_input(title: str, content: str) -> str:
    # Prefixing the title gives each chunk document-level context in vector space
    # ("Q3 report" + a table fragment embeds closer to "Q3 revenue" queries).
    return f"{title}\n\n{content}" if title else content


def chunk_pages(pages: list[PageText]) -> list[tuple[int, TextChunk]]:
    """Chunks never cross pages, so each chunk maps to exactly one page for citations."""
    return [
        (page.page_number, chunk)
        for page in pages
        for chunk in chunk_text(page.text, settings.CHUNK_SIZE_TOKENS, settings.CHUNK_OVERLAP_TOKENS)
    ]


async def _claim(db: AsyncSession, document_id: uuid.UUID) -> bool:
    """Atomically moves pending -> processing, so a document is never processed twice at once."""
    claimed = await db.scalar(
        update(Document)
        .where(Document.id == document_id, Document.status == DocumentStatus.PENDING)
        .values(status=DocumentStatus.PROCESSING, error_message=None)
        .returning(Document.id)
    )
    await db.commit()
    return claimed is not None


async def process_document(
    db: AsyncSession, storage: ObjectStorage, embedder: Embedder, document_id: uuid.UUID
) -> None:
    """
    pending -> processing -> ready | failed.
    Idempotent: existing chunks are replaced, so a failed document can simply be re-run.
    """
    if not await _claim(db, document_id):
        logger.info("Document %s is not pending; skipping", document_id)
        return

    document = await db.get(Document, document_id, populate_existing=True)
    if document is None:  # deleted between claim and load
        return

    started = time.perf_counter()
    log_ctx = {"document_id": str(document_id)}
    try:
        data = await asyncio.to_thread(lambda: b"".join(storage.iter_bytes(document.storage_key)))

        pages = await asyncio.to_thread(extract_pages, data)
        if not pages:
            raise IngestionError(
                "No text could be extracted from this PDF. If it is a scan, the image quality may be too low."
            )

        chunks = await asyncio.to_thread(chunk_pages, pages)
        title = _document_title(document.filename)
        vectors = await embedder.embed_documents([embedding_input(title, c.content) for _, c in chunks])

        # Replace any chunks from a previous attempt in the same transaction
        await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
        await db.execute(
            insert(Chunk),
            [
                {
                    "document_id": document_id,
                    "user_id": document.user_id,
                    "chunk_index": index,
                    "page_number": page_number,
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "embedding": vector,
                }
                for index, ((page_number, chunk), vector) in enumerate(zip(chunks, vectors, strict=True))
            ],
        )
        document.status = DocumentStatus.READY
        document.chunk_count = len(chunks)
        document.error_message = None
        document.processed_at = datetime.now(UTC)
        await db.commit()

        logger.info(
            "Document processed",
            extra={
                **log_ctx,
                "pages_with_text": len(pages),
                "ocr_pages": sum(p.ocr for p in pages),
                "chunks": len(chunks),
                "duration_ms": round((time.perf_counter() - started) * 1000),
            },
        )
    except Exception as e:
        await db.rollback()
        logger.exception("Document processing failed", extra=log_ctx)
        await db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status=DocumentStatus.FAILED, error_message=_user_facing_error(e))
        )
        await db.commit()
