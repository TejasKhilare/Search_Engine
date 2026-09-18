"""
ANN benchmark: HNSW recall vs exact search, and retrieval latency.

For each query vector, the exact top-k (sequential scan, no index) is the ground
truth. HNSW results are compared against it while sweeping `hnsw.ef_search`, the
knob that trades recall for speed. The query mirrors production: filtered by owner,
cosine distance, iterative index scan.

    POSTGRES_DB=docsearch_bench python -m benchmarks.ann --dataset scifact
"""

import argparse
import asyncio
import json
import random
import time
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import settings
from app.db.session import SessionLocal, engine
from benchmarks import beir
from benchmarks.beir import DATA_DIR
from benchmarks.common import (
    embed_queries_cached,
    environment,
    environment_markdown,
    get_bench_user_id,
    guard_bench_database,
    write_report,
)
from benchmarks.metrics import mean, overlap_recall, percentile

_VECTOR_SQL = text(
    """
    SELECT c.id FROM chunks c
    WHERE c.user_id = :user_id
    ORDER BY c.embedding <=> CAST(:qv AS vector)
    LIMIT :k
    """
).bindparams(bindparam("qv", type_=Vector(settings.EMBEDDING_DIM)))

_INDEX_DDL = (
    "CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) "
    "WITH (m = {m}, ef_construction = {ef_construction})"
)


async def _search(
    conn: AsyncConnection, user_id: uuid.UUID, vector: list[float], k: int
) -> tuple[list[int], float]:
    started = time.perf_counter()
    rows = (await conn.execute(_VECTOR_SQL, {"user_id": user_id, "qv": vector, "k": k})).scalars().all()
    return list(rows), (time.perf_counter() - started) * 1000


async def _configure(conn: AsyncConnection, ef_search: int | None) -> None:
    if ef_search is None:  # exact: forbid index scans → sequential scan + top-k sort
        await conn.execute(text("SET enable_indexscan = off"))
        await conn.execute(text("SET enable_bitmapscan = off"))
    else:
        await conn.execute(text("SET enable_indexscan = on"))
        await conn.execute(text(f"SET hnsw.ef_search = {int(ef_search)}"))
        await conn.execute(text("SET hnsw.iterative_scan = relaxed_order"))


async def _run_sequential(
    user_id: uuid.UUID, vectors: list[list[float]], k: int, ef_search: int | None, warmup: int = 20
) -> tuple[list[list[int]], list[float]]:
    async with engine.connect() as conn:
        await _configure(conn, ef_search)
        for v in vectors[:warmup]:  # load index pages into cache before timing
            await _search(conn, user_id, v, k)
        results, latencies = [], []
        for v in vectors:
            ids, ms = await _search(conn, user_id, v, k)
            results.append(ids)
            latencies.append(ms)
        await conn.rollback()
    return results, latencies


async def _run_concurrent(
    user_id: uuid.UUID, vectors: list[list[float]], k: int, ef_search: int, workers: int
) -> tuple[list[float], float]:
    """`workers` connections issue queries in parallel; returns latencies and throughput."""
    queue: asyncio.Queue[list[float]] = asyncio.Queue()
    for v in vectors:
        queue.put_nowait(v)
    latencies: list[float] = []

    async def worker() -> None:
        async with engine.connect() as conn:
            await _configure(conn, ef_search)
            while not queue.empty():
                v = queue.get_nowait()
                _, ms = await _search(conn, user_id, v, k)
                latencies.append(ms)
            await conn.rollback()

    started = time.perf_counter()
    await asyncio.gather(*(worker() for _ in range(workers)))
    return latencies, len(vectors) / (time.perf_counter() - started)


async def _rebuild_index(m: int, ef_construction: int) -> float:
    async with engine.connect() as conn:
        # Session only (server config untouched); Windows caps this just below 2GB
        await conn.execute(text("SET maintenance_work_mem = '1900MB'"))
        await conn.execute(text("SET max_parallel_maintenance_workers = 3"))
        await conn.execute(text("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw"))
        started = time.perf_counter()
        await conn.execute(text(_INDEX_DDL.format(m=m, ef_construction=ef_construction)))
        await conn.commit()
        return time.perf_counter() - started


async def _query_vectors(
    dataset: str, user_id: uuid.UUID, count: int, seed: int
) -> tuple[list[list[float]], str]:
    """
    Held-out vectors (never indexed) when the dataset provides them — no API calls.
    Otherwise real BEIR queries (embedded once, cached), topped up with sampled
    document vectors if the dataset has few queries.
    """
    heldout_file = DATA_DIR / dataset / "heldout_queries.json"
    if heldout_file.exists():
        vectors = list(json.loads(heldout_file.read_text()).values())[:count]
        return vectors, f"{len(vectors)} held-out vectors (not in the index)"

    data = beir.load(dataset)
    rng = random.Random(seed)
    qids = sorted(data.queries)
    rng.shuffle(qids)
    qids = qids[:count]
    embedded = await embed_queries_cached(dataset, {q: data.queries[q] for q in qids})
    vectors = [embedded[q] for q in qids]
    source = f"{len(vectors)} BEIR queries"

    if len(vectors) < count:
        extra = count - len(vectors)
        async with engine.connect() as conn:
            rows = await conn.execute(
                text("SELECT embedding FROM chunks WHERE user_id = :u ORDER BY md5(id::text || :s) LIMIT :n"),
                {"u": user_id, "s": str(seed), "n": extra},
            )
            vectors += [json.loads(r[0]) if isinstance(r[0], str) else list(r[0]) for r in rows]
        source += f" + {extra} sampled document vectors"
    return vectors, source


async def run(args: argparse.Namespace) -> None:
    guard_bench_database()
    async with SessionLocal() as db:
        user_id = await get_bench_user_id(db, args.dataset)

    build_seconds = None
    load_meta = DATA_DIR / args.dataset / "load_meta.json"
    if load_meta.exists():  # index was built at the end of the bulk load
        build_seconds = json.loads(load_meta.read_text())["index_build_seconds"]
    if args.rebuild_index:
        print(f"Rebuilding HNSW index (m={args.m}, ef_construction={args.ef_construction}) …", flush=True)
        build_seconds = await _rebuild_index(args.m, args.ef_construction)
        print(f"  built in {build_seconds:.1f}s")

    async with engine.connect() as conn:
        n_chunks = await conn.scalar(text("SELECT count(*) FROM chunks WHERE user_id = :u"), {"u": user_id})
        table_chunks = await conn.scalar(text("SELECT count(*) FROM chunks"))
        index_mb = await conn.scalar(text("SELECT pg_relation_size('ix_chunks_embedding_hnsw') / 1048576.0"))
        table_mb = await conn.scalar(text("SELECT pg_total_relation_size('chunks') / 1048576.0"))
        env = await environment(conn)

    vectors, query_source = await _query_vectors(args.dataset, user_id, args.queries, args.seed)
    k = args.k
    print(f"{n_chunks} chunks · {len(vectors)} queries ({query_source}) · k={k}")

    print("Exact search (ground truth) …", flush=True)
    exact, exact_latency = await _run_sequential(user_id, vectors, k, ef_search=None)

    sweep = []
    for ef in args.ef_search:
        approx, latency = await _run_sequential(user_id, vectors, k, ef_search=ef)
        recalls = [overlap_recall(a, e, k) for a, e in zip(approx, exact, strict=True)]
        row = {
            "ef_search": ef,
            "recall": mean(recalls),
            "p50_ms": percentile(latency, 50),
            "p95_ms": percentile(latency, 95),
            "p99_ms": percentile(latency, 99),
            "qps_single": 1000 / mean(latency),
        }
        sweep.append(row)
        print(
            f"  ef_search={ef:<4} Recall@{k}={row['recall']:.3f}  p50={row['p50_ms']:.1f}ms  "
            f"p95={row['p95_ms']:.1f}ms  p99={row['p99_ms']:.1f}ms",
            flush=True,
        )

    # Operating point: the cheapest ef_search that meets the recall target
    target = next((r for r in sweep if r["recall"] >= args.target_recall), sweep[-1])
    print(f"Load test at ef_search={target['ef_search']} …", flush=True)
    load = []
    for workers in args.concurrency:
        latency, qps = await _run_concurrent(user_id, vectors, k, target["ef_search"], workers)
        load.append(
            {
                "workers": workers,
                "p50_ms": percentile(latency, 50),
                "p95_ms": percentile(latency, 95),
                "qps": qps,
            }
        )
        print(
            f"  {workers:>2} concurrent: p95={load[-1]['p95_ms']:.1f}ms  throughput={qps:.0f} QPS", flush=True
        )

    exact_p95 = percentile(exact_latency, 95)
    report = {
        "dataset": args.dataset,
        "chunks": n_chunks,
        "dimensions": settings.EMBEDDING_DIM,
        "k": k,
        "queries": len(vectors),
        "query_source": query_source,
        "chunks_in_index": table_chunks,
        "index_size_mb": float(index_mb),
        "table_size_mb": float(table_mb),
        "index_build_seconds": build_seconds,
        "exact": {"p50_ms": percentile(exact_latency, 50), "p95_ms": exact_p95},
        "sweep": sweep,
        "target_recall": args.target_recall,
        "operating_point": target,
        "load": load,
        "environment": env,
    }

    lines = [
        f"# ANN benchmark — {args.dataset}",
        "",
        f"**{n_chunks:,} chunks** · {settings.EMBEDDING_DIM}-dim · HNSW (cosine) · "
        f"{len(vectors)} queries ({query_source}) · Recall@{k} measured against exact search",
        "",
        f"- HNSW index size: **{index_mb:,.0f} MB** over {table_chunks:,} chunks in the table "
        f"(table incl. indexes: {table_mb:,.0f} MB)",
    ]
    if build_seconds is not None:
        lines.append(
            f"- Index build time: **{build_seconds:.1f}s** "
            f"(m={args.m}, ef_construction={args.ef_construction})"
        )
    lines += [
        f"- Exact search (sequential scan): p50 {report['exact']['p50_ms']:.1f} ms, p95 {exact_p95:.1f} ms",
        "",
        "## Recall vs latency (single client)",
        "",
        f"| ef_search | Recall@{k} | p50 (ms) | p95 (ms) | p99 (ms) | QPS | speed-up vs exact (p95) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        *(
            f"| {r['ef_search']} | {r['recall']:.3f} | {r['p50_ms']:.1f} | {r['p95_ms']:.1f} | "
            f"{r['p99_ms']:.1f} | {r['qps_single']:.0f} | {exact_p95 / r['p95_ms']:.1f}× |"
            for r in sweep
        ),
        "",
        f"Operating point (lowest ef_search with Recall@{k} ≥ {args.target_recall}): "
        f"**ef_search={target['ef_search']} → Recall@{k} {target['recall']:.3f}, "
        f"p95 {target['p95_ms']:.1f} ms**",
        "",
        f"## Under concurrent load (ef_search={target['ef_search']})",
        "",
        "| concurrent clients | p50 (ms) | p95 (ms) | throughput (QPS) |",
        "|---:|---:|---:|---:|",
        *(f"| {r['workers']} | {r['p50_ms']:.1f} | {r['p95_ms']:.1f} | {r['qps']:.0f} |" for r in load),
        "",
        "Latency is database retrieval time for the production vector query (owner filter, cosine, "
        "iterative index scan), measured client-side over a local connection. It excludes the OpenAI "
        "query-embedding call.",
        "",
        "## Environment",
        "",
        "| | |",
        "|---|---|",
        environment_markdown(env),
        "",
    ]
    path = write_report(args.dataset, "ann", "\n".join(lines), report)
    print(f"Report: {path}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--queries", type=int, default=500)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--ef-search", type=int, nargs="+", default=[10, 20, 40, 64, 100, 200, 400])
    parser.add_argument("--target-recall", type=float, default=0.95)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 8, 16])
    parser.add_argument("--rebuild-index", action="store_true", help="drop/recreate HNSW and time the build")
    parser.add_argument("--m", type=int, default=16)
    parser.add_argument("--ef-construction", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
