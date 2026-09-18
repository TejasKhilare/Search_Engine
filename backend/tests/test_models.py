import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Chunk, Document, DocumentStatus, User

DIM = settings.EMBEDDING_DIM


def _unit_vector(hot: int) -> list[float]:
    v = [0.0] * DIM
    v[hot] = 1.0
    return v


async def _make_user(db: AsyncSession) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(email=f"u{suffix}@example.com", username=f"u{suffix}", password_hash="x")
    db.add(user)
    await db.flush()
    return user


async def _make_document(db: AsyncSession, user: User, checksum: str = "a" * 64) -> Document:
    doc = Document(
        user_id=user.id,
        filename="test.pdf",
        content_type="application/pdf",
        size_bytes=123,
        checksum_sha256=checksum,
        storage_key=f"{user.id}/{uuid.uuid4()}.pdf",
    )
    db.add(doc)
    await db.flush()
    return doc


def _chunk(doc: Document, index: int, content: str, vector: list[float]) -> Chunk:
    return Chunk(
        document_id=doc.id,
        user_id=doc.user_id,
        chunk_index=index,
        page_number=1,
        content=content,
        token_count=len(content.split()),
        char_start=0,
        char_end=len(content),
        embedding=vector,
    )


async def test_document_defaults(db_session: AsyncSession) -> None:
    doc = await _make_document(db_session, await _make_user(db_session))
    await db_session.refresh(doc)
    assert doc.status == DocumentStatus.PENDING
    assert doc.chunk_count == 0
    assert doc.created_at is not None


async def test_duplicate_upload_per_user_is_rejected(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    await _make_document(db_session, user, checksum="b" * 64)
    with pytest.raises(IntegrityError):
        await _make_document(db_session, user, checksum="b" * 64)


async def test_vector_search_orders_by_cosine_distance(db_session: AsyncSession) -> None:
    doc = await _make_document(db_session, await _make_user(db_session))
    db_session.add_all(
        [
            _chunk(doc, 0, "far away", _unit_vector(5)),
            _chunk(doc, 1, "closest match", _unit_vector(0)),
        ]
    )
    await db_session.flush()

    distance = Chunk.embedding.cosine_distance(_unit_vector(0))
    rows = (
        await db_session.execute(
            select(Chunk.content, distance.label("d")).where(Chunk.document_id == doc.id).order_by(distance)
        )
    ).all()

    assert [r.content for r in rows] == ["closest match", "far away"]
    assert rows[0].d == pytest.approx(0.0)
    assert rows[1].d == pytest.approx(1.0)


async def test_full_text_column_is_generated(db_session: AsyncSession) -> None:
    doc = await _make_document(db_session, await _make_user(db_session))
    db_session.add(_chunk(doc, 0, "Invoices are processed quarterly", _unit_vector(1)))
    await db_session.flush()

    hit = await db_session.scalar(
        select(func.count())
        .select_from(Chunk)
        .where(Chunk.document_id == doc.id)
        .where(Chunk.content_tsv.op("@@")(func.websearch_to_tsquery("english", "invoice processing")))
    )
    assert hit == 1  # stemming: "invoice" ~ "Invoices", "processing" ~ "processed"


async def test_trigram_similarity_tolerates_typos(db_session: AsyncSession) -> None:
    score = await db_session.scalar(text("SELECT word_similarity('recieve', 'please receive the goods')"))
    assert score > 0.3


async def test_deleting_document_cascades_to_chunks(db_session: AsyncSession) -> None:
    doc = await _make_document(db_session, await _make_user(db_session))
    db_session.add(_chunk(doc, 0, "text", _unit_vector(2)))
    await db_session.flush()

    await db_session.delete(doc)
    await db_session.flush()

    remaining = await db_session.scalar(select(func.count()).where(Chunk.document_id == doc.id))
    assert remaining == 0


async def test_hnsw_index_exists(db_session: AsyncSession) -> None:
    indexdef = await db_session.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_chunks_embedding_hnsw'")
    )
    assert indexdef is not None
    assert "hnsw" in indexdef and "vector_cosine_ops" in indexdef
