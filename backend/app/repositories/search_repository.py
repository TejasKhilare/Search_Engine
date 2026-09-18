import uuid
from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

# Highlight markers for ts_headline. Control characters never occur in cleaned
# document text, so they can be parsed out unambiguously (and no HTML is built
# from document content).
HL_START = "\x02"
HL_END = "\x03"
_HEADLINE_OPTIONS = (
    f"StartSel={HL_START}, StopSel={HL_END}, MaxWords=40, MinWords=20, "
    'MaxFragments=2, FragmentDelimiter=" … "'
)
# Fuzzy (trigram) matching helps with typos, names and codes; on long natural-
# language questions it adds cost without adding recall.
_FUZZY_MAX_WORDS = 5


@dataclass(frozen=True, slots=True)
class ChunkHit:
    chunk_id: int
    document_id: uuid.UUID
    filename: str
    page_number: int
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    token_count: int
    rrf_score: float
    similarity: float
    keyword_coverage: float  # share of the query's terms present in the chunk, 0–1
    fuzzy_match: bool
    headline: str


def _hybrid_sql(filter_documents: bool, use_fuzzy: bool) -> str:
    # Only constant SQL fragments are interpolated (chosen by the two booleans);
    # every user-supplied value is a bound parameter.
    doc_filter = "AND c.document_id = ANY(:document_ids)" if filter_documents else ""
    fuzzy_cte = (
        f"""
        SELECT id, row_number() OVER (ORDER BY score DESC) AS rank FROM (
            SELECT c.id, word_similarity(:q, c.content) AS score
            FROM chunks c
            WHERE c.user_id = :user_id {doc_filter} AND :q <% c.content
            ORDER BY score DESC
            LIMIT :k
        ) f"""
        if use_fuzzy
        else "SELECT NULL::bigint AS id, NULL::bigint AS rank WHERE false"
    )
    # Each retriever orders+limits in a subquery FIRST so the indexes are used;
    # ranks are assigned afterwards (a window over the whole table would force a scan).
    return f"""
    WITH q AS (
        -- OR the query terms (plainto/websearch AND them, so natural questions like
        -- "how much did revenue grow" would need every word to match). ts_rank_cd
        -- still ranks chunks matching more terms higher.
        SELECT
            CAST(replace(CAST(plainto_tsquery('english', :q) AS text), ' & ', ' | ') AS tsquery) AS tsq,
            ARRAY(SELECT lexeme FROM unnest(to_tsvector('english', :q))) AS lexemes
    ),
    semantic AS (
        SELECT id, row_number() OVER (ORDER BY distance) AS rank FROM (
            SELECT c.id, c.embedding <=> CAST(:qv AS vector) AS distance
            FROM chunks c
            WHERE c.user_id = :user_id {doc_filter}
            ORDER BY distance
            LIMIT :k
        ) s
    ),
    keyword AS (
        SELECT id, row_number() OVER (ORDER BY score DESC) AS rank FROM (
            SELECT c.id, ts_rank_cd(c.content_tsv, q.tsq) AS score
            FROM chunks c, q
            WHERE c.user_id = :user_id {doc_filter} AND c.content_tsv @@ q.tsq
            ORDER BY score DESC
            LIMIT :k
        ) kw
    ),
    fuzzy AS ({fuzzy_cte}),
    fused AS (
        SELECT
            id,
            COALESCE(1.0 / (:rrf_k + s.rank), 0)
              + COALESCE(1.0 / (:rrf_k + kw.rank), 0)
              + COALESCE(0.5 / (:rrf_k + f.rank), 0) AS rrf,
            f.rank IS NOT NULL AS fuzzy_match
        FROM semantic s
        FULL OUTER JOIN keyword kw USING (id)
        FULL OUTER JOIN fuzzy f USING (id)
    )
    SELECT
        c.id AS chunk_id, c.document_id, d.filename, c.page_number, c.chunk_index,
        c.content, c.char_start, c.char_end, c.token_count,
        fused.rrf AS rrf_score,
        1 - (c.embedding <=> CAST(:qv AS vector)) AS similarity,
        CASE WHEN cardinality(q.lexemes) = 0 THEN 0.0 ELSE (
            SELECT count(*) FROM unnest(q.lexemes) AS l WHERE l = ANY(tsvector_to_array(c.content_tsv))
        )::float / cardinality(q.lexemes) END AS keyword_coverage,
        fused.fuzzy_match,
        ts_headline('english', c.content, q.tsq, :hl_options) AS headline
    FROM fused
    CROSS JOIN q
    JOIN chunks c ON c.id = fused.id
    JOIN documents d ON d.id = c.document_id
    ORDER BY fused.rrf DESC, c.id
    LIMIT :k
    """


class SearchRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def hybrid_search(
        self,
        *,
        user_id: uuid.UUID,
        query: str,
        query_vector: list[float],
        document_ids: list[uuid.UUID] | None,
        candidates: int,
    ) -> list[ChunkHit]:
        # Transaction-scoped planner settings:
        #  - ef_search: HNSW candidate list size (recall vs speed)
        #  - iterative_scan: keep scanning the index until enough rows pass the
        #    user_id filter (pgvector >= 0.8); otherwise filtered ANN can return
        #    too few results once many users share the table
        await self.db.execute(text(f"SET LOCAL hnsw.ef_search = {int(settings.HNSW_EF_SEARCH)}"))
        await self.db.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        await self.db.execute(text("SET LOCAL pg_trgm.word_similarity_threshold = 0.5"))

        use_fuzzy = len(query.split()) <= _FUZZY_MAX_WORDS
        stmt = text(_hybrid_sql(bool(document_ids), use_fuzzy)).bindparams(
            bindparam("qv", type_=Vector(settings.EMBEDDING_DIM)),
        )
        params: dict[str, object] = {
            "user_id": user_id,
            "q": query,
            "qv": query_vector,
            "k": candidates,
            "rrf_k": settings.SEARCH_RRF_K,
            "hl_options": _HEADLINE_OPTIONS,
        }
        if document_ids:
            stmt = stmt.bindparams(bindparam("document_ids", type_=ARRAY(UUID(as_uuid=True))))
            params["document_ids"] = document_ids

        rows = (await self.db.execute(stmt, params)).mappings().all()
        return [
            ChunkHit(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                filename=r["filename"],
                page_number=r["page_number"],
                chunk_index=r["chunk_index"],
                content=r["content"],
                char_start=r["char_start"],
                char_end=r["char_end"],
                token_count=r["token_count"],
                rrf_score=float(r["rrf_score"]),
                similarity=float(r["similarity"]),
                keyword_coverage=float(r["keyword_coverage"]),
                fuzzy_match=r["fuzzy_match"],
                headline=r["headline"],
            )
            for r in rows
        ]
