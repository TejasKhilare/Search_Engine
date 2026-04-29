from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Index,ForeignKey, UniqueConstraint
from datetime import datetime, timezone
from db.postgres import Base
import uuid
from sqlalchemy.dialects.postgresql import UUID

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True,default=uuid.uuid4)
    doc_id = Column(String, unique=True, index=True, nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    path = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending | processing | completed | failed
    total_chunks = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id=Column(UUID(as_uuid=True),ForeignKey("users.id",ondelete='CASCADE'),nullable=False,index=True)


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    doc_id = Column(String, index=True, nullable=False)
    page_no = Column(Integer, index=True, nullable=False)
    chunk_id = Column(Integer, index=True, nullable=False)
    content = Column(Text, nullable=False)
    start_pos = Column(Integer)
    end_pos = Column(Integer)
    vector_id = Column(String)  # Qdrant point ID
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_doc_page", "doc_id", "page_no"),
        UniqueConstraint("doc_id", "page_no", "chunk_id", name="unique_doc_page_chunk"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True,default=uuid.uuid4)
    username = Column(String, unique=True, nullable=False,index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True)
    query = Column(String, nullable=False)
    doc_id = Column(String, nullable=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    results_count = Column(Integer, default=0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))