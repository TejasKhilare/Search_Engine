import json
import uuid
from collections.abc import Callable

import httpx
import openai
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import SearchLog
from app.services.ingestion_service import process_document
from app.services.rag_service import NOT_FOUND_ANSWER, cited_indexes
from app.services.search_service import parse_headline
from tests.conftest import bearer_headers
from tests.fakes import FakeChatModel, FakeEmbedder, InMemoryStorage

API = settings.API_V1_PREFIX

REPORT = [
    "Annual revenue reached 48 million dollars, an increase of 18 percent. "
    "Enterprise subscriptions drove most of the revenue growth.",
    "Headcount grew to 402 employees. A new engineering centre opened in Pune.",
    "Invoice INV-2024-0042 was issued to Contoso for consulting services.",
]
RECIPES = ["Knead the dough for ten minutes, then let the bread rise overnight."]


@pytest.fixture
def ingest(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: InMemoryStorage,
    embedder: FakeEmbedder,
    make_pdf: Callable,
) -> Callable:
    async def _ingest(headers: dict, pages: list[str], name: str = "report.pdf") -> str:
        res = await client.post(
            f"{API}/documents",
            files={"file": (name, make_pdf(page_texts=pages), "application/pdf")},
            headers=headers,
        )
        assert res.status_code == 201, res.text
        doc_id = res.json()["id"]
        await process_document(db_session, storage, embedder, uuid.UUID(doc_id))
        return doc_id

    return _ingest


# ── Search ───────────────────────────────────────────────────────────────────
async def test_semantic_search_ranks_relevant_page_first(client: AsyncClient, ingest: Callable) -> None:
    headers = await bearer_headers(client)
    doc_id = await ingest(headers, REPORT)
    await ingest(headers, RECIPES, "recipes.pdf")

    res = await client.get(f"{API}/search", params={"q": "revenue growth"}, headers=headers)
    assert res.status_code == 200
    body = res.json()
    top = body["results"][0]
    assert top["document_id"] == doc_id
    assert top["page_number"] == 1
    assert top["filename"] == "report.pdf"
    assert "semantic" in top["match_types"] and "keyword" in top["match_types"]
    assert all(r["filename"] != "recipes.pdf" for r in body["results"])
    assert body["took_ms"] >= 0


async def test_keyword_search_finds_exact_codes(client: AsyncClient, ingest: Callable) -> None:
    headers = await bearer_headers(client)
    await ingest(headers, REPORT)

    res = await client.get(f"{API}/search", params={"q": "INV-2024-0042"}, headers=headers)
    [top, *_] = res.json()["results"]
    assert top["page_number"] == 3


async def test_keyword_search_does_not_require_every_word(client: AsyncClient, ingest: Callable) -> None:
    # "dividends" appears nowhere; an AND query would find nothing
    headers = await bearer_headers(client)
    await ingest(headers, REPORT)
    res = await client.get(f"{API}/search", params={"q": "revenue dividends"}, headers=headers)
    [top, *_] = res.json()["results"]
    assert top["page_number"] == 1
    assert "keyword" in top["match_types"]


async def test_fuzzy_search_tolerates_typos(client: AsyncClient, ingest: Callable) -> None:
    headers = await bearer_headers(client)
    await ingest(headers, REPORT)

    res = await client.get(f"{API}/search", params={"q": "subscriptons"}, headers=headers)
    results = res.json()["results"]
    assert results and results[0]["page_number"] == 1
    assert "fuzzy" in results[0]["match_types"]


async def test_irrelevant_query_returns_nothing(client: AsyncClient, ingest: Callable) -> None:
    headers = await bearer_headers(client)
    await ingest(headers, REPORT)
    res = await client.get(f"{API}/search", params={"q": "zebra xylophone quantum"}, headers=headers)
    assert res.json()["results"] == []


async def test_search_never_returns_other_users_documents(client: AsyncClient, ingest: Callable) -> None:
    alice = await bearer_headers(client)
    bob = await bearer_headers(client)
    await ingest(alice, REPORT)

    res = await client.get(f"{API}/search", params={"q": "revenue growth"}, headers=bob)
    assert res.json()["results"] == []


async def test_search_within_one_document(client: AsyncClient, ingest: Callable) -> None:
    headers = await bearer_headers(client)
    await ingest(headers, REPORT)
    recipes_id = await ingest(headers, RECIPES + ["Revenue from bread sales was modest."], "recipes.pdf")

    res = await client.get(
        f"{API}/search", params={"q": "revenue", "document_id": recipes_id}, headers=headers
    )
    results = res.json()["results"]
    assert results and all(r["document_id"] == recipes_id for r in results)


async def test_search_other_users_document_filter_is_404(client: AsyncClient, ingest: Callable) -> None:
    alice = await bearer_headers(client)
    doc_id = await ingest(alice, REPORT)
    res = await client.get(
        f"{API}/search", params={"q": "revenue", "document_id": doc_id}, headers=await bearer_headers(client)
    )
    assert res.status_code == 404


async def test_one_result_per_page(
    client: AsyncClient, ingest: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force several overlapping chunks on the same page
    monkeypatch.setattr(settings, "CHUNK_SIZE_TOKENS", 20)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP_TOKENS", 5)
    headers = await bearer_headers(client)
    long_page = " ".join(f"Revenue fact number {i} is recorded here." for i in range(12))
    await ingest(headers, [long_page])

    results = (await client.get(f"{API}/search", params={"q": "revenue fact"}, headers=headers)).json()[
        "results"
    ]
    pages = [(r["document_id"], r["page_number"]) for r in results]
    assert len(pages) == len(set(pages)) == 1


async def test_snippet_highlights_are_plain_text_ranges(client: AsyncClient, ingest: Callable) -> None:
    headers = await bearer_headers(client)
    await ingest(headers, REPORT)
    [top, *_] = (await client.get(f"{API}/search", params={"q": "revenue"}, headers=headers)).json()[
        "results"
    ]

    snippet = top["snippet"]
    assert "<" not in snippet["text"]  # no HTML markup
    assert snippet["highlights"]
    for start, end in snippet["highlights"]:
        assert snippet["text"][start:end].lower() == "revenue"


async def test_search_is_logged(client: AsyncClient, ingest: Callable, db_session: AsyncSession) -> None:
    headers = await bearer_headers(client)
    await ingest(headers, REPORT)
    await client.get(f"{API}/search", params={"q": "revenue"}, headers=headers)

    log = await db_session.scalar(select(SearchLog).where(SearchLog.query == "revenue"))
    assert log is not None and log.search_type == "search" and log.results_count >= 1


async def test_search_validation(client: AsyncClient) -> None:
    headers = await bearer_headers(client)
    assert (await client.get(f"{API}/search", params={"q": ""}, headers=headers)).status_code == 422
    assert (await client.get(f"{API}/search", params={"q": "x" * 501}, headers=headers)).status_code == 422
    assert (await client.get(f"{API}/search", params={"q": "revenue"})).status_code == 401


def test_parse_headline() -> None:
    snippet = parse_headline("Total \x02revenue\x03 grew; \x02revenue\x03 again")
    assert snippet.text == "Total revenue grew; revenue again"
    assert snippet.highlights == [(6, 13), (20, 27)]


# ── Ask (RAG) ────────────────────────────────────────────────────────────────
async def test_ask_answers_with_citations(
    client: AsyncClient, ingest: Callable, chat_model: FakeChatModel
) -> None:
    headers = await bearer_headers(client)
    doc_id = await ingest(headers, REPORT)
    chat_model.answer = "Revenue grew 18 percent [1]."

    res = await client.post(
        f"{API}/ask", json={"question": "What was the revenue increase?"}, headers=headers
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["answer"] == "Revenue grew 18 percent [1]."
    [citation] = body["citations"]
    assert citation["index"] == 1
    assert citation["document_id"] == doc_id
    assert citation["page_number"] == 1
    assert len(body["sources"]) >= 1

    # The prompt carried the sources, delimited, plus the question
    [messages] = chat_model.calls
    assert messages[0]["role"] == "system" and "ONLY" in messages[0]["content"]
    assert '<source id="1" document="report.pdf" page="1">' in messages[1]["content"]
    assert messages[1]["content"].endswith("Question: What was the revenue increase?")


async def test_ask_without_relevant_sources_skips_llm(
    client: AsyncClient, ingest: Callable, chat_model: FakeChatModel
) -> None:
    headers = await bearer_headers(client)
    await ingest(headers, REPORT)

    res = await client.post(f"{API}/ask", json={"question": "zebra xylophone quantum"}, headers=headers)
    body = res.json()
    assert body["answer"] == NOT_FOUND_ANSWER
    assert body["citations"] == [] and body["sources"] == []
    assert chat_model.calls == []


async def test_ask_llm_outage_is_503(
    client: AsyncClient, ingest: Callable, chat_model: FakeChatModel
) -> None:
    headers = await bearer_headers(client)
    await ingest(headers, REPORT)
    chat_model.fail_with = openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))

    res = await client.post(f"{API}/ask", json={"question": "revenue growth?"}, headers=headers)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "service_unavailable"


async def test_ask_stream_emits_sse_events(
    client: AsyncClient, ingest: Callable, chat_model: FakeChatModel
) -> None:
    headers = await bearer_headers(client)
    await ingest(headers, REPORT)
    chat_model.answer = "Revenue grew 18 percent [1]."

    res = await client.post(f"{API}/ask/stream", json={"question": "revenue growth?"}, headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    events = [
        (
            block.split("\n")[0].removeprefix("event: "),
            json.loads(block.split("\n")[1].removeprefix("data: ")),
        )
        for block in res.text.strip().split("\n\n")
    ]
    names = [name for name, _ in events]
    assert names[0] == "sources" and names[-1] == "done"
    assert set(names[1:-1]) == {"delta"}
    assert "".join(d["text"] for n, d in events if n == "delta").strip() == chat_model.answer
    assert events[-1][1] == {"citations": [1]}


async def test_ask_rejects_blank_question(client: AsyncClient) -> None:
    res = await client.post(f"{API}/ask", json={"question": "   "}, headers=await bearer_headers(client))
    assert res.status_code == 422


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Fact [1]. Other [3].", [1, 3]),
        ("Both [1][2] and [2, 3].", [1, 2, 3]),
        ("Out of range [9] ignored.", []),
        ("No citations.", []),
    ],
)
def test_cited_indexes(answer: str, expected: list[int]) -> None:
    assert cited_indexes(answer, source_count=3) == expected
