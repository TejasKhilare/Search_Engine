"""
Loads a BEIR corpus into the benchmark database through the production code path:
same chunker, same title-prefixed embedding input, same `chunks` table and HNSW index.

Resumable: documents already loaded are skipped, so an interrupted run can be restarted.

    POSTGRES_DB=docsearch_bench python -m benchmarks.load_beir --dataset scifact
"""

import argparse
import asyncio
import hashlib
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, insert, select

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models import Chunk, Document, DocumentStatus
from app.services.chunking import chunk_text, count_tokens
from app.services.ingestion_service import embedding_input
from benchmarks import beir
from benchmarks.common import (
    DEFAULT_EMBEDDING_PRICE_PER_M,
    bench_embedder,
    get_or_create_bench_user,
    guard_bench_database,
)

DOCS_PER_BATCH = 200  # one DB transaction per batch → progress survives interruption


def storage_key(dataset: str, doc_id: str) -> str:
    # Benchmark docs have no stored file; the key doubles as the resume marker
    return f"bench/{dataset}/{doc_id}"


async def load(dataset: str, limit: int | None, price: float, assume_yes: bool, concurrency: int) -> None:
    guard_bench_database()
    data = beir.load(dataset)
    corpus = data.corpus[:limit] if limit else data.corpus

    async with SessionLocal() as db:
        user = await get_or_create_bench_user(db, dataset)
        done = set(await db.scalars(select(Document.storage_key).where(Document.user_id == user.id)))
    todo = [d for d in corpus if storage_key(dataset, d.id) not in done]
    print(f"BEIR/{dataset}: {len(corpus)} docs, {len(done)} already loaded, {len(todo)} to go")
    if not todo:
        return

    # Chunk everything up front: exact token count → exact cost estimate before spending
    started = time.perf_counter()
    prepared = []
    total_tokens = 0
    for doc in todo:
        chunks = chunk_text(doc.text, settings.CHUNK_SIZE_TOKENS, settings.CHUNK_OVERLAP_TOKENS)
        inputs = [embedding_input(doc.title, c.content) for c in chunks]
        total_tokens += sum(count_tokens(t) for t in inputs)
        prepared.append((doc, chunks, inputs))
    n_chunks = sum(len(c) for _, c, _ in prepared)
    cost = total_tokens / 1_000_000 * price
    print(f"{n_chunks} chunks, {total_tokens:,} embedding tokens ≈ ${cost:.2f} (at ${price}/1M tokens)")
    confirm = "y" if cost <= 0.05 or assume_yes else await asyncio.to_thread(input, "Proceed? [y/N] ")
    if confirm.strip().lower() != "y":
        print("Aborted.")
        return

    embedder = bench_embedder()
    semaphore = asyncio.Semaphore(concurrency)

    async def embed_batch(batch: list) -> list[list[list[float]]]:
        flat = [text for _, _, inputs in batch for text in inputs]
        async with semaphore:
            vectors = await embedder.embed_documents(flat)
        # Split flat vectors back per document
        out, i = [], 0
        for _, chunks, _ in batch:
            out.append(vectors[i : i + len(chunks)])
            i += len(chunks)
        return out

    batches = [prepared[i : i + DOCS_PER_BATCH] for i in range(0, len(prepared), DOCS_PER_BATCH)]
    loaded_chunks = 0
    # Embed a few batches concurrently (network-bound); write to the DB in order
    for window_start in range(0, len(batches), concurrency):
        window = batches[window_start : window_start + concurrency]
        embedded = await asyncio.gather(*(embed_batch(b) for b in window))

        async with SessionLocal() as db:
            for batch, batch_vectors in zip(window, embedded, strict=True):
                documents, chunk_rows = [], []
                now = datetime.now(UTC)
                for (doc, chunks, _), vectors in zip(batch, batch_vectors, strict=True):
                    document_id = uuid.uuid4()
                    documents.append(
                        {
                            "id": document_id,
                            "user_id": user.id,
                            "filename": doc.id,  # BEIR doc id: maps results back to qrels
                            "content_type": "text/plain",
                            "size_bytes": len(doc.text.encode()),
                            "checksum_sha256": hashlib.sha256(f"{dataset}:{doc.id}".encode()).hexdigest(),
                            "storage_key": storage_key(dataset, doc.id),
                            "status": DocumentStatus.READY,
                            "page_count": 1,
                            "chunk_count": len(chunks),
                            "processed_at": now,
                        }
                    )
                    chunk_rows.extend(
                        {
                            "document_id": document_id,
                            "user_id": user.id,
                            "chunk_index": i,
                            "page_number": 1,
                            "content": c.content,
                            "token_count": c.token_count,
                            "char_start": c.char_start,
                            "char_end": c.char_end,
                            "embedding": v,
                        }
                        for i, (c, v) in enumerate(zip(chunks, vectors, strict=True))
                    )
                await db.execute(insert(Document), documents)
                await db.execute(insert(Chunk), chunk_rows)
                loaded_chunks += len(chunk_rows)
            await db.commit()

        elapsed = time.perf_counter() - started
        docs_done = min((window_start + len(window)) * DOCS_PER_BATCH, len(prepared))
        print(
            f"  {docs_done}/{len(prepared)} docs · {loaded_chunks} chunks · "
            f"{loaded_chunks / elapsed:.0f} chunks/s",
            flush=True,
        )

    async with SessionLocal() as db:
        total = await db.scalar(select(func.count()).select_from(Chunk).where(Chunk.user_id == user.id))
    print(f"Done in {time.perf_counter() - started:.0f}s. {total} chunks indexed for BEIR/{dataset}.")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", required=True, help=", ".join(beir.KNOWN_DATASETS))
    parser.add_argument("--limit", type=int, help="load only the first N documents")
    parser.add_argument(
        "--price", type=float, default=DEFAULT_EMBEDDING_PRICE_PER_M, help="USD per 1M tokens"
    )
    parser.add_argument("--yes", action="store_true", help="skip the cost confirmation")
    parser.add_argument("--concurrency", type=int, default=4, help="parallel embedding requests")
    args = parser.parse_args()
    asyncio.run(load(args.dataset, args.limit, args.price, args.yes, args.concurrency))


if __name__ == "__main__":
    main()
