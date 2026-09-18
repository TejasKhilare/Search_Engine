"""
Retrieval-quality benchmark against BEIR human relevance judgements (qrels).

Compares, on the same queries and index:
  - vector:  HNSW cosine search only
  - keyword: Postgres full-text search only (same OR-ed query as production)
  - hybrid:  the production query (vector + keyword + fuzzy, fused with RRF)

    POSTGRES_DB=docsearch_bench python -m benchmarks.quality --dataset scifact
"""

import argparse
import asyncio
import time
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.repositories.search_repository import SearchRepository
from benchmarks import beir
from benchmarks.common import (
    embed_queries_cached,
    environment,
    environment_markdown,
    get_bench_user_id,
    guard_bench_database,
    write_report,
)
from benchmarks.metrics import dedupe_preserving_order, mean, mrr_at_k, ndcg_at_k, percentile, recall_at_k

DEPTH = 50  # chunks fetched per query before collapsing to documents

_VECTOR_SQL = text(
    """
    SELECT d.filename FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE c.user_id = :user_id
    ORDER BY c.embedding <=> CAST(:qv AS vector)
    LIMIT :depth
    """
).bindparams(bindparam("qv", type_=Vector(settings.EMBEDDING_DIM)))

_KEYWORD_SQL = text(
    """
    WITH q AS (
        SELECT CAST(replace(CAST(plainto_tsquery('english', :q) AS text), ' & ', ' | ') AS tsquery) AS tsq
    )
    SELECT d.filename FROM chunks c JOIN documents d ON d.id = c.document_id, q
    WHERE c.user_id = :user_id AND c.content_tsv @@ q.tsq
    ORDER BY ts_rank_cd(c.content_tsv, q.tsq) DESC
    LIMIT :depth
    """
)


async def _vector(user_id: uuid.UUID, query: str, vector: list[float]) -> list[str]:
    async with SessionLocal() as db:
        await db.execute(text(f"SET LOCAL hnsw.ef_search = {int(settings.HNSW_EF_SEARCH)}"))
        await db.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        rows = await db.execute(_VECTOR_SQL, {"user_id": user_id, "qv": vector, "depth": DEPTH})
        return list(rows.scalars())


async def _keyword(user_id: uuid.UUID, query: str, vector: list[float]) -> list[str]:
    async with SessionLocal() as db:
        rows = await db.execute(_KEYWORD_SQL, {"user_id": user_id, "q": query, "depth": DEPTH})
        return list(rows.scalars())


async def _hybrid(user_id: uuid.UUID, query: str, vector: list[float]) -> list[str]:
    async with SessionLocal() as db:
        hits = await SearchRepository(db).hybrid_search(
            user_id=user_id,
            query=query,
            query_vector=vector,
            document_ids=None,
            candidates=settings.SEARCH_CANDIDATES,
        )
        return [h.filename for h in hits]


MODES = {"vector": _vector, "keyword": _keyword, "hybrid": _hybrid}


async def run(args: argparse.Namespace) -> None:
    guard_bench_database()
    data = beir.load(args.dataset, split=args.split)
    async with SessionLocal() as db:
        user_id = await get_bench_user_id(db, args.dataset)

    qids = [q for q in sorted(data.qrels) if q in data.queries][: args.max_queries]
    if not qids:
        raise SystemExit(f"No judged queries for split '{args.split}'")
    vectors = await embed_queries_cached(args.dataset, {q: data.queries[q] for q in qids})
    k = args.k
    print(f"BEIR/{args.dataset}: {len(qids)} judged queries ({args.split} split), k={k}")

    results = {}
    for name, retrieve in MODES.items():
        recalls, ndcgs, mrrs, latencies = [], [], [], []
        for qid in qids:
            started = time.perf_counter()
            chunk_docs = await retrieve(user_id, data.queries[qid], vectors[qid])
            latencies.append((time.perf_counter() - started) * 1000)
            ranked = dedupe_preserving_order(chunk_docs)
            relevant = data.qrels[qid]
            recalls.append(recall_at_k(ranked, relevant, k))
            ndcgs.append(ndcg_at_k(ranked, relevant, k))
            mrrs.append(mrr_at_k(ranked, relevant, k))
        results[name] = {
            f"recall@{k}": mean(recalls),
            f"ndcg@{k}": mean(ndcgs),
            f"mrr@{k}": mean(mrrs),
            "p50_ms": percentile(latencies, 50),
            "p95_ms": percentile(latencies, 95),
        }
        r = results[name]
        print(
            f"  {name:<8} Recall@{k}={r[f'recall@{k}']:.3f}  nDCG@{k}={r[f'ndcg@{k}']:.3f}  "
            f"MRR@{k}={r[f'mrr@{k}']:.3f}  p95={r['p95_ms']:.1f}ms",
            flush=True,
        )

    async with engine.connect() as conn:
        env = await environment(conn)
        n_chunks = await conn.scalar(text("SELECT count(*) FROM chunks WHERE user_id = :u"), {"u": user_id})

    base = results["vector"]
    lines = [
        f"# Retrieval quality — BEIR/{args.dataset}",
        "",
        f"{len(qids)} human-judged queries ({args.split} split) · {n_chunks:,} chunks · "
        f"document-level ranking (best chunk per document)",
        "",
        f"| method | Recall@{k} | nDCG@{k} | MRR@{k} | p50 (ms) | p95 (ms) |",
        "|---|---:|---:|---:|---:|---:|",
        *(
            f"| {name} | {r[f'recall@{k}']:.3f} | {r[f'ndcg@{k}']:.3f} | {r[f'mrr@{k}']:.3f} | "
            f"{r['p50_ms']:.1f} | {r['p95_ms']:.1f} |"
            for name, r in results.items()
        ),
        "",
        f"Hybrid vs vector-only: nDCG@{k} "
        f"{(results['hybrid'][f'ndcg@{k}'] / base[f'ndcg@{k}'] - 1) * 100:+.1f}%, Recall@{k} "
        f"{(results['hybrid'][f'recall@{k}'] / base[f'recall@{k}'] - 1) * 100:+.1f}%",
        "",
        "- **vector**: HNSW cosine search (ef_search="
        f"{settings.HNSW_EF_SEARCH}), `{settings.OPENAI_EMBEDDING_MODEL}` embeddings",
        "- **keyword**: Postgres full-text search (English stemming, OR-ed terms, `ts_rank_cd`)",
        "- **hybrid**: production query — vector + keyword + trigram, Reciprocal Rank Fusion "
        f"(k={settings.SEARCH_RRF_K}), {settings.SEARCH_CANDIDATES} candidates per retriever",
        "",
        "Latency is database time for the query (query embeddings are precomputed).",
        "",
        "## Environment",
        "",
        "| | |",
        "|---|---|",
        environment_markdown(env),
        "",
    ]
    report = {
        "dataset": args.dataset,
        "split": args.split,
        "queries": len(qids),
        "chunks": n_chunks,
        "k": k,
        "results": results,
        "environment": env,
    }
    path = write_report(args.dataset, "quality", "\n".join(lines), report)
    print(f"Report: {path}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--max-queries", type=int, default=1000)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
