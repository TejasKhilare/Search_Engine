"""
Loads a public set of precomputed OpenAI embeddings — no API calls, no cost:

    Qdrant/dbpedia-entities-openai3-text-embedding-3-small-1536-100K (Hugging Face)
    100,000 DBpedia articles embedded with text-embedding-3-small (1536-dim),
    the same model the application uses.

A seeded random 1,000 vectors are held out as queries (never indexed), so ANN recall
is measured on unseen queries. The remaining 99,000 are indexed as chunks. The HNSW
index is dropped during the bulk load and rebuilt once at the end (timed), which is
far faster than incremental inserts.

    POSTGRES_DB=docsearch_bench python -m benchmarks.load_vectors
"""

import argparse
import asyncio
import hashlib
import json
import random
import time
import uuid
from datetime import UTC, datetime

import httpx
import pyarrow.parquet as pq
from sqlalchemy import delete, insert, text

from app.db.session import SessionLocal, engine
from app.models import Chunk, Document, DocumentStatus
from app.services.chunking import count_tokens
from benchmarks.beir import DATA_DIR
from benchmarks.common import get_or_create_bench_user, guard_bench_database

DATASET = "dbpedia-100k"
HF_REPO = "Qdrant/dbpedia-entities-openai3-text-embedding-3-small-1536-100K"
PARQUET_URL = f"https://huggingface.co/api/datasets/{HF_REPO}/parquet/default/train/{{i}}.parquet"
VECTOR_COLUMN = "text-embedding-3-small-1536-embedding"
N_FILES = 4
ROWS_PER_TX = 1000
HELDOUT_FILE = DATA_DIR / DATASET / "heldout_queries.json"

INDEX_DDL = (
    "CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) "
    "WITH (m = 16, ef_construction = 64)"
)


def _download() -> list:
    folder = DATA_DIR / DATASET
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(N_FILES):
        path = folder / f"{i}.parquet"
        if not path.exists():
            print(f"Downloading part {i + 1}/{N_FILES} …", flush=True)
            with httpx.stream("GET", PARQUET_URL.format(i=i), follow_redirects=True, timeout=300) as r:
                r.raise_for_status()
                with path.open("wb") as f:
                    for block in r.iter_bytes(1 << 20):
                        f.write(block)
        paths.append(path)
    return paths


def _rows(document: dict, user_id: uuid.UUID, now: datetime) -> tuple[dict, dict]:
    document_id = uuid.uuid4()
    content = f"{document['title']}\n\n{document['text']}"
    doc_row = {
        "id": document_id,
        "user_id": user_id,
        "filename": document["_id"],
        "content_type": "text/plain",
        "size_bytes": len(content.encode()),
        "checksum_sha256": hashlib.sha256(f"{DATASET}:{document['_id']}".encode()).hexdigest(),
        "storage_key": f"bench/{DATASET}/{document['_id']}",
        "status": DocumentStatus.READY,
        "page_count": 1,
        "chunk_count": 1,
        "processed_at": now,
    }
    chunk_row = {
        "document_id": document_id,
        "user_id": user_id,
        "chunk_index": 0,
        "page_number": 1,
        "content": content,
        "token_count": count_tokens(content),
        "char_start": 0,
        "char_end": len(content),
        "embedding": document[VECTOR_COLUMN],
    }
    return doc_row, chunk_row


async def load(heldout: int, seed: int) -> None:
    guard_bench_database()
    paths = _download()

    # Pick held-out ids from the (small) id column first; vectors are then streamed
    # in batches so ~150M floats never sit in memory at once
    all_ids = [i for path in paths for i in pq.read_table(path, columns=["_id"]).column("_id").to_pylist()]
    rng = random.Random(seed)
    heldout_ids = set(rng.sample(all_ids, heldout))
    print(
        f"{len(all_ids):,} precomputed embeddings; {heldout:,} held out as queries, "
        f"{len(all_ids) - heldout:,} to index"
    )

    async with SessionLocal() as db:
        user = await get_or_create_bench_user(db, DATASET)
        # Idempotent: replace any previous load of this dataset
        await db.execute(delete(Document).where(Document.user_id == user.id))
        await db.commit()

    async with engine.connect() as conn:
        await conn.execute(text("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw"))
        await conn.commit()

    started = time.perf_counter()
    now = datetime.now(UTC)
    queries: dict[str, list[float]] = {}
    indexed = 0
    columns = ["_id", "title", "text", VECTOR_COLUMN]
    for path in paths:
        for record_batch in pq.ParquetFile(path).iter_batches(batch_size=ROWS_PER_TX, columns=columns):
            documents, chunks = [], []
            for record in record_batch.to_pylist():
                if record["_id"] in heldout_ids:
                    queries[record["_id"]] = record[VECTOR_COLUMN]
                    continue
                doc_row, chunk_row = _rows(record, user.id, now)
                documents.append(doc_row)
                chunks.append(chunk_row)
            async with SessionLocal() as db:
                await db.execute(insert(Document), documents)
                await db.execute(insert(Chunk), chunks)
                await db.commit()
            previous, indexed = indexed, indexed + len(chunks)
            if indexed // 10_000 != previous // 10_000:
                rate = indexed / (time.perf_counter() - started)
                print(f"  {indexed:,} rows · {rate:.0f} rows/s", flush=True)

    HELDOUT_FILE.write_text(json.dumps(queries))
    corpus_size = indexed
    print(f"Inserted {indexed:,} rows in {time.perf_counter() - started:.0f}s")

    print("Building HNSW index (m=16, ef_construction=64) …", flush=True)
    async with engine.connect() as conn:
        await conn.execute(text("SET maintenance_work_mem = '1900MB'"))  # this session only
        await conn.execute(text("SET max_parallel_maintenance_workers = 3"))
        build_started = time.perf_counter()
        await conn.execute(text(INDEX_DDL))
        await conn.commit()
        build_seconds = time.perf_counter() - build_started
        size_mb = await conn.scalar(text("SELECT pg_relation_size('ix_chunks_embedding_hnsw') / 1048576.0"))
        total = await conn.scalar(text("SELECT count(*) FROM chunks"))
    print(f"Index built over {total:,} chunks in {build_seconds:.1f}s ({size_mb:,.0f} MB)")

    meta = DATA_DIR / DATASET / "load_meta.json"
    meta.write_text(
        json.dumps(
            {
                "indexed": corpus_size,
                "heldout": len(queries),
                "index_build_seconds": build_seconds,
                "index_size_mb": float(size_mb),
                "total_chunks_in_table": total,
                "seed": seed,
            }
        )
    )
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--heldout", type=int, default=1000, help="vectors held out as queries")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    asyncio.run(load(args.heldout, args.seed))


if __name__ == "__main__":
    main()
