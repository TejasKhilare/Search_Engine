import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentStatus


class DocumentRepository:
    """Every read is scoped to an owner: there is deliberately no unscoped get()."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, document: Document) -> Document:
        self.db.add(document)
        return document

    async def get_for_user(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document | None:
        return await self.db.scalar(
            select(Document).where(Document.id == document_id, Document.user_id == user_id)
        )

    async def get_by_checksum(self, user_id: uuid.UUID, checksum: str) -> Document | None:
        return await self.db.scalar(
            select(Document).where(Document.user_id == user_id, Document.checksum_sha256 == checksum)
        )

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
        status: DocumentStatus | None = None,
    ) -> tuple[Sequence[Document], int]:
        filters = [Document.user_id == user_id]
        if status is not None:
            filters.append(Document.status == status)

        total = await self.db.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
        items = (
            await self.db.scalars(
                select(Document)
                .where(*filters)
                .order_by(Document.created_at.desc(), Document.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return items, total

    async def delete(self, document: Document) -> None:
        # Chunks are removed by ON DELETE CASCADE in the database
        await self.db.delete(document)
