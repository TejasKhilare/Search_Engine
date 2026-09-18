import uuid
from collections.abc import Callable

import httpx
import openai
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Chunk, Document, DocumentStatus
from app.services.ingestion_service import process_document
from tests.conftest import bearer_headers
from tests.fakes import FakeEmbedder, InMemoryStorage, RecordingQueue

DOCS = f"{settings.API_V1_PREFIX}/documents"

PAGE_1 = (
    "Quarterly revenue grew by twelve percent compared to the previous year. "
    "The growth was driven mainly by strong enterprise subscriptions in Europe."
)
PAGE_2 = (
    "Employee headcount increased to four hundred people. "
    "The company opened a new engineering office in Pune during the quarter."
)


async def _upload(client: AsyncClient, headers: dict, pdf: bytes, name: str = "Q3_report.pdf") -> str:
    res = await client.post(DOCS, files={"file": (name, pdf, "application/pdf")}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def test_upload_enqueues_processing(
    client: AsyncClient, queue: RecordingQueue, make_pdf: Callable
) -> None:
    doc_id = await _upload(client, await bearer_headers(client), make_pdf())
    assert queue.enqueued == [uuid.UUID(doc_id)]


async def test_process_document_end_to_end(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: InMemoryStorage,
    embedder: FakeEmbedder,
    make_pdf: Callable,
) -> None:
    headers = await bearer_headers(client)
    doc_id = uuid.UUID(await _upload(client, headers, make_pdf(page_texts=[PAGE_1, PAGE_2])))

    await process_document(db_session, storage, embedder, doc_id)

    doc = (await client.get(f"{DOCS}/{doc_id}", headers=headers)).json()
    assert doc["status"] == "ready"
    assert doc["error_message"] is None
    assert doc["processed_at"] is not None
    assert doc["chunk_count"] == 2  # one short page -> one chunk each

    chunks = (
        await db_session.scalars(select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index))
    ).all()
    assert [c.page_number for c in chunks] == [1, 2]
    assert "twelve percent" in chunks[0].content
    assert "Pune" in chunks[1].content
    assert len(chunks[0].embedding) == settings.EMBEDDING_DIM

    # Title is prefixed for embedding only, not stored in the chunk text
    [embedded] = embedder.calls
    assert embedded[0].startswith("Q3 report\n\n")
    assert not chunks[0].content.startswith("Q3 report")


async def test_processed_chunks_are_keyword_searchable(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: InMemoryStorage,
    embedder: FakeEmbedder,
    make_pdf: Callable,
) -> None:
    doc_id = uuid.UUID(
        await _upload(client, await bearer_headers(client), make_pdf(page_texts=[PAGE_1, PAGE_2]))
    )
    await process_document(db_session, storage, embedder, doc_id)

    page = await db_session.scalar(
        select(Chunk.page_number).where(
            Chunk.document_id == doc_id,
            Chunk.content_tsv.op("@@")(func.websearch_to_tsquery("english", "engineering offices")),
        )
    )
    assert page == 2


async def test_reprocessing_replaces_chunks(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: InMemoryStorage,
    embedder: FakeEmbedder,
    make_pdf: Callable,
) -> None:
    headers = await bearer_headers(client)
    doc_id = uuid.UUID(await _upload(client, headers, make_pdf(page_texts=[PAGE_1, PAGE_2])))
    await process_document(db_session, storage, embedder, doc_id)

    assert (await client.post(f"{DOCS}/{doc_id}/reprocess", headers=headers)).status_code == 202
    await process_document(db_session, storage, embedder, doc_id)

    count = await db_session.scalar(select(func.count()).where(Chunk.document_id == doc_id))
    assert count == 2  # not duplicated


async def test_embedding_failure_marks_document_failed(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: InMemoryStorage,
    embedder: FakeEmbedder,
    queue: RecordingQueue,
    make_pdf: Callable,
) -> None:
    headers = await bearer_headers(client)
    doc_id = uuid.UUID(await _upload(client, headers, make_pdf(page_texts=[PAGE_1])))
    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    embedder.fail_with = openai.APIConnectionError(request=request)

    await process_document(db_session, storage, embedder, doc_id)

    doc = (await client.get(f"{DOCS}/{doc_id}", headers=headers)).json()
    assert doc["status"] == "failed"
    assert doc["error_message"] == "Embedding service is temporarily unavailable. Please retry."
    assert await db_session.scalar(select(func.count()).where(Chunk.document_id == doc_id)) == 0

    # Retry from the API once the problem is fixed
    embedder.fail_with = None
    res = await client.post(f"{DOCS}/{doc_id}/reprocess", headers=headers)
    assert res.status_code == 202
    assert res.json()["status"] == "pending"
    assert queue.enqueued[-1] == doc_id
    await process_document(db_session, storage, embedder, doc_id)
    assert (await client.get(f"{DOCS}/{doc_id}", headers=headers)).json()["status"] == "ready"


async def test_pdf_without_text_fails_with_helpful_message(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: InMemoryStorage,
    embedder: FakeEmbedder,
    make_pdf: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.pdf.ocr_available", lambda: False)
    headers = await bearer_headers(client)
    doc_id = uuid.UUID(await _upload(client, headers, make_pdf(page_texts=[""])))

    await process_document(db_session, storage, embedder, doc_id)

    doc = (await client.get(f"{DOCS}/{doc_id}", headers=headers)).json()
    assert doc["status"] == "failed"
    assert doc["error_message"].startswith("No text could be extracted")


async def test_already_processing_document_is_not_claimed_twice(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: InMemoryStorage,
    embedder: FakeEmbedder,
    make_pdf: Callable,
) -> None:
    headers = await bearer_headers(client)
    doc_id = uuid.UUID(await _upload(client, headers, make_pdf(page_texts=[PAGE_1])))
    document = await db_session.get(Document, doc_id)
    assert document is not None
    document.status = DocumentStatus.PROCESSING
    await db_session.commit()

    await process_document(db_session, storage, embedder, doc_id)
    assert embedder.calls == []  # skipped

    res = await client.post(f"{DOCS}/{doc_id}/reprocess", headers=headers)
    assert res.status_code == 409
