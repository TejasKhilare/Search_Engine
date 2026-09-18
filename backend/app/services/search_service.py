import logging
import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models import Document, SearchLog, User
from app.repositories.search_repository import HL_END, HL_START, ChunkHit, SearchRepository
from app.schemas.search import MatchType, SearchResponse, SearchResult, Snippet
from app.services.embedding import Embedder

logger = logging.getLogger(__name__)


def parse_headline(headline: str) -> Snippet:
    """Turns ts_headline output with control-char markers into text + highlight ranges."""
    text_parts: list[str] = []
    highlights: list[tuple[int, int]] = []
    position = 0
    start: int | None = None
    for ch in headline:
        if ch == HL_START:
            start = position
        elif ch == HL_END:
            if start is not None and position > start:
                highlights.append((start, position))
            start = None
        else:
            text_parts.append(ch)
            position += 1
    return Snippet(text="".join(text_parts), highlights=highlights)


def keyword_match(hit: ChunkHit) -> bool:
    return hit.keyword_coverage >= settings.SEARCH_KEYWORD_MIN_COVERAGE


def is_relevant(hit: ChunkHit) -> bool:
    # Strong lexical matches are relevant on their own; otherwise the semantic
    # similarity must clear the bar
    return keyword_match(hit) or hit.fuzzy_match or hit.similarity >= settings.SEARCH_MIN_SCORE


def match_types(hit: ChunkHit) -> list[MatchType]:
    types: list[MatchType] = []
    if hit.similarity >= settings.SEARCH_MIN_SCORE:
        types.append("semantic")
    if keyword_match(hit):
        types.append("keyword")
    if hit.fuzzy_match:
        types.append("fuzzy")
    return types


class SearchService:
    def __init__(self, db: AsyncSession, embedder: Embedder) -> None:
        self.db = db
        self.embedder = embedder
        self.repo = SearchRepository(db)

    async def _ensure_owned(self, user: User, document_ids: list[uuid.UUID] | None) -> None:
        if not document_ids:
            return
        owned = await self.db.scalar(
            select(func.count()).where(Document.id.in_(document_ids), Document.user_id == user.id)
        )
        if owned != len(set(document_ids)):
            raise NotFoundError("One or more documents were not found")

    async def retrieve(
        self, user: User, query: str, document_ids: list[uuid.UUID] | None, candidates: int
    ) -> list[ChunkHit]:
        """Hybrid retrieval over the user's chunks, relevance-filtered, best first."""
        await self._ensure_owned(user, document_ids)
        query_vector = await self.embedder.embed_query(query)
        hits = await self.repo.hybrid_search(
            user_id=user.id,
            query=query,
            query_vector=query_vector,
            document_ids=document_ids,
            candidates=candidates,
        )
        return [h for h in hits if is_relevant(h)]

    async def search(
        self, user: User, query: str, document_id: uuid.UUID | None, limit: int
    ) -> SearchResponse:
        started = time.perf_counter()
        hits = await self.retrieve(
            user, query, [document_id] if document_id else None, settings.SEARCH_CANDIDATES
        )

        # One result per page: overlapping chunks from the same page are redundant in a result list
        results: list[SearchResult] = []
        seen_pages: set[tuple[uuid.UUID, int]] = set()
        for hit in hits:
            page_key = (hit.document_id, hit.page_number)
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            results.append(
                SearchResult(
                    document_id=hit.document_id,
                    filename=hit.filename,
                    page_number=hit.page_number,
                    chunk_index=hit.chunk_index,
                    content=hit.content,
                    char_start=hit.char_start,
                    char_end=hit.char_end,
                    snippet=parse_headline(hit.headline),
                    score=round(max(hit.similarity, 0.0), 4),
                    match_types=match_types(hit),
                )
            )
            if len(results) >= limit:
                break

        took_ms = round((time.perf_counter() - started) * 1000)
        await self.log(user, query, "search", document_id, len(results), took_ms)
        return SearchResponse(query=query, results=results, took_ms=took_ms)

    async def log(
        self,
        user: User,
        query: str,
        search_type: str,
        document_id: uuid.UUID | None,
        results_count: int,
        latency_ms: int,
    ) -> None:
        # Analytics must never break the user's request
        try:
            self.db.add(
                SearchLog(
                    user_id=user.id,
                    document_id=document_id,
                    query=query[:2000],
                    search_type=search_type,
                    results_count=results_count,
                    latency_ms=latency_ms,
                )
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to write search log")
