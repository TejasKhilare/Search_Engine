import json
import os
import platform
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.config import settings
from app.models import User
from app.services.embedding import OpenAIEmbedder
from benchmarks.beir import DATA_DIR

RESULTS_DIR = Path(__file__).parent / "results"

# USD per 1M input tokens for text-embedding-3-small at the time of writing.
# Check current pricing; override with --price.
DEFAULT_EMBEDDING_PRICE_PER_M = 0.02


def guard_bench_database() -> None:
    """Benchmarks write 100K+ rows: refuse to run against a non-benchmark database."""
    if "bench" not in settings.POSTGRES_DB:
        sys.exit(
            f"Refusing to run against database '{settings.POSTGRES_DB}'. "
            "Set POSTGRES_DB to a benchmark database, e.g. POSTGRES_DB=docsearch_bench"
        )


def bench_embedder() -> OpenAIEmbedder:
    # Long bulk runs hit rate limits; allow more retries than the API does
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
        max_retries=8,
    )
    return OpenAIEmbedder(
        client,
        model=settings.OPENAI_EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIM,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
    )


def bench_username(dataset: str) -> str:
    return f"bench_{dataset}"


async def get_or_create_bench_user(db: AsyncSession, dataset: str) -> User:
    username = bench_username(dataset)
    user = await db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            email=f"{username}@bench.local",
            username=username,
            password_hash="!",  # not a valid hash: this account can never log in
        )
        db.add(user)
        await db.commit()
    return user


async def get_bench_user_id(db: AsyncSession, dataset: str) -> uuid.UUID:
    user_id = await db.scalar(select(User.id).where(User.username == bench_username(dataset)))
    if user_id is None:
        sys.exit(
            f"Dataset '{dataset}' is not loaded. Run: python -m benchmarks.load_beir --dataset {dataset}"
        )
    return user_id


async def embed_queries_cached(dataset: str, queries: dict[str, str]) -> dict[str, list[float]]:
    """Query embeddings are cached on disk so repeated benchmark runs cost nothing."""
    cache = (
        DATA_DIR
        / dataset
        / f"query_embeddings_{settings.OPENAI_EMBEDDING_MODEL}_{settings.EMBEDDING_DIM}.json"
    )
    cached: dict[str, list[float]] = json.loads(cache.read_text()) if cache.exists() else {}
    missing = [qid for qid in queries if qid not in cached]
    if missing:
        print(f"Embedding {len(missing)} queries …", flush=True)
        vectors = await bench_embedder().embed_documents([queries[q] for q in missing])
        cached.update(zip(missing, vectors, strict=True))
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(cached))
    return {qid: cached[qid] for qid in queries}


async def environment(conn: AsyncConnection) -> dict[str, str]:
    """Hardware/DB details recorded with every result, so numbers are reproducible."""
    info = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "os": f"{platform.system()} {platform.release()}",
        "cpu": platform.processor() or platform.machine(),
        "cpu_threads": str(os.cpu_count()),
        "python": platform.python_version(),
        "embedding_model": f"{settings.OPENAI_EMBEDDING_MODEL} ({settings.EMBEDDING_DIM}-dim)",
    }
    for name in ("server_version", "shared_buffers", "work_mem", "maintenance_work_mem"):
        info[f"postgres.{name}"] = str(await conn.scalar(text(f"SHOW {name}")))
    info["pgvector"] = str(
        await conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
    )
    info["hnsw_index"] = str(
        await conn.scalar(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_chunks_embedding_hnsw'")
        )
    )
    return info


def environment_markdown(env: dict[str, str]) -> str:
    return "\n".join(f"| {k} | `{v}` |" for k, v in env.items())


def write_report(dataset: str, name: str, markdown: str, data: dict) -> Path:
    out = RESULTS_DIR / dataset
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.md").write_text(markdown, encoding="utf-8")
    (out / f"{name}.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return out / f"{name}.md"
