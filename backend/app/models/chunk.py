import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Computed, DateTime, ForeignKey, Identity, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Chunk(Base):
    """
    A piece of a document's text plus its embedding.

    user_id is denormalised from documents so search can filter by owner
    directly on this table, without a join, before ranking.
    """

    __tablename__ = "chunks"
    __table_args__ = (
        Index("uq_chunks_document_id_chunk_index", "document_id", "chunk_index", unique=True),
        Index("ix_chunks_user_id_document_id", "user_id", "document_id"),
        # Approximate nearest-neighbour search on cosine distance
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # Full-text (keyword) search
        Index("ix_chunks_content_tsv", "content_tsv", postgresql_using="gin"),
        # Fuzzy / typo-tolerant matching
        Index(
            "ix_chunks_content_trgm",
            "content",
            postgresql_using="gin",
            postgresql_ops={"content": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)  # order within the document
    page_number: Mapped[int] = mapped_column(Integer)  # 1-based
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)  # offsets within the page text, for highlighting
    char_end: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIM))
    # Maintained by Postgres on every insert/update
    content_tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', content)", persisted=True)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")
