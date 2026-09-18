import asyncio
import hashlib
import io
import logging
import re
import unicodedata
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    RangeNotSatisfiableError,
)
from app.models import Document, DocumentStatus, User
from app.repositories.document_repository import DocumentRepository
from app.services.ingestion_queue import IngestionQueue
from app.services.pdf import inspect_pdf
from app.services.storage import ObjectStorage

logger = logging.getLogger(__name__)

PDF_CONTENT_TYPE = "application/pdf"
_READ_CHUNK = 1024 * 1024
_FORBIDDEN_FILENAME_CHARS = set('<>:"/\\|?*')
_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def sanitize_filename(raw: str | None) -> str:
    """Strip paths, control and reserved characters; always end in .pdf; max 255 chars."""
    name = PurePosixPath((raw or "").replace("\\", "/")).name
    name = unicodedata.normalize("NFC", name)
    name = "".join(c for c in name if c.isprintable() and c not in _FORBIDDEN_FILENAME_CHARS)
    name = name.strip(" .")
    if not name:
        name = "document.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    if len(name) > 255:
        name = name[: 255 - 4].rstrip(" .") + ".pdf"
    return name


def storage_key_for(user_id: uuid.UUID, document_id: uuid.UUID) -> str:
    return f"users/{user_id}/documents/{document_id}.pdf"


@dataclass(frozen=True, slots=True)
class ByteRange:
    start: int
    end: int  # inclusive

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_range_header(header: str | None, size: int) -> ByteRange | None:
    """
    Parses a single `bytes=` range (RFC 9110). Returns None for "whole file"
    (no header, or a multi-range/unparseable header, which servers may ignore).
    """
    if not header:
        return None
    match = _RANGE_RE.fullmatch(header.strip())
    if not match or match.groups() == ("", ""):
        return None

    start_s, end_s = match.groups()
    if start_s == "":  # suffix range: last N bytes
        suffix = int(end_s)
        if suffix == 0:
            raise RangeNotSatisfiableError("Invalid range", headers={"Content-Range": f"bytes */{size}"})
        return ByteRange(max(0, size - suffix), size - 1)

    start = int(start_s)
    end = min(int(end_s), size - 1) if end_s else size - 1
    if start >= size or start > end:
        raise RangeNotSatisfiableError("Invalid range", headers={"Content-Range": f"bytes */{size}"})
    return ByteRange(start, end)


class DocumentService:
    def __init__(self, db: AsyncSession, storage: ObjectStorage, queue: IngestionQueue) -> None:
        self.db = db
        self.storage = storage
        self.queue = queue
        self.documents = DocumentRepository(db)

    # ── Upload ───────────────────────────────────────────────────────────────
    async def upload(self, user: User, upload: UploadFile) -> Document:
        data, checksum = await self._read_limited(upload)
        info = await asyncio.to_thread(inspect_pdf, data)

        existing = await self.documents.get_by_checksum(user.id, checksum)
        if existing is not None:
            raise ConflictError(
                "This file has already been uploaded",
                details={"document_id": str(existing.id), "filename": existing.filename},
            )

        document_id = uuid.uuid4()
        key = storage_key_for(user.id, document_id)
        await self.storage.put(key, io.BytesIO(data), len(data), PDF_CONTENT_TYPE)

        document = self.documents.add(
            Document(
                id=document_id,
                user_id=user.id,
                filename=sanitize_filename(upload.filename),
                content_type=PDF_CONTENT_TYPE,
                size_bytes=len(data),
                checksum_sha256=checksum,
                storage_key=key,
                page_count=info.page_count,
                status=DocumentStatus.PENDING,
            )
        )
        try:
            await self.db.commit()
        except Exception as e:
            # Compensate: never leave an orphan file in storage without a DB row
            await self.db.rollback()
            await self._delete_blob_quietly(key)
            if isinstance(e, IntegrityError):  # concurrent upload of the same file
                raise ConflictError("This file has already been uploaded") from e
            raise

        await self.db.refresh(document)
        logger.info(
            "Document uploaded",
            extra={"document_id": str(document.id), "size_bytes": len(data), "pages": info.page_count},
        )
        self.queue.enqueue(document.id)
        return document

    async def reprocess(self, user: User, document_id: uuid.UUID) -> Document:
        """Re-runs ingestion, e.g. after a failure or a pipeline improvement."""
        document = await self.get(user, document_id)
        if document.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
            raise ConflictError("Document is already queued or being processed")
        document.status = DocumentStatus.PENDING
        document.error_message = None
        await self.db.commit()
        self.queue.enqueue(document.id)
        return document

    async def _read_limited(self, upload: UploadFile) -> tuple[bytes, str]:
        """Reads the upload in chunks, enforcing the size cap and hashing as it goes."""
        limit = settings.max_upload_bytes
        hasher = hashlib.sha256()
        buffer = bytearray()
        while chunk := await upload.read(_READ_CHUNK):
            buffer.extend(chunk)
            if len(buffer) > limit:
                raise PayloadTooLargeError(f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit")
            hasher.update(chunk)
        if not buffer:
            raise AppError("File is empty")
        return bytes(buffer), hasher.hexdigest()

    # ── Read ─────────────────────────────────────────────────────────────────
    async def get(self, user: User, document_id: uuid.UUID) -> Document:
        # 404 (not 403) for other users' documents, so IDs can't be probed
        document = await self.documents.get_for_user(document_id, user.id)
        if document is None:
            raise NotFoundError("Document not found")
        return document

    async def list(
        self, user: User, *, limit: int, offset: int, status: DocumentStatus | None
    ) -> tuple[Sequence[Document], int]:
        return await self.documents.list_for_user(user.id, limit=limit, offset=offset, status=status)

    async def open_file(
        self, user: User, document_id: uuid.UUID, range_header: str | None
    ) -> tuple[Document, int, ByteRange | None, Iterator[bytes]]:
        document = await self.get(user, document_id)
        size = (await self.storage.stat(document.storage_key)).size
        byte_range = parse_range_header(range_header, size)
        if byte_range is None:
            stream = self.storage.iter_bytes(document.storage_key)
        else:
            stream = self.storage.iter_bytes(document.storage_key, byte_range.start, byte_range.length)
        return document, size, byte_range, stream

    # ── Delete ───────────────────────────────────────────────────────────────
    async def delete(self, user: User, document_id: uuid.UUID) -> None:
        document = await self.get(user, document_id)
        key = document.storage_key
        await self.documents.delete(document)
        await self.db.commit()
        # DB first: a failed blob delete leaves an orphan file (logged), never a broken document
        await self._delete_blob_quietly(key)
        logger.info("Document deleted", extra={"document_id": str(document_id)})

    async def _delete_blob_quietly(self, key: str) -> None:
        try:
            await self.storage.delete(key)
        except Exception:
            logger.exception("Failed to delete storage object %s; it is now orphaned", key)
