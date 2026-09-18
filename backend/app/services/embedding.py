import logging
from functools import lru_cache
from typing import Protocol

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# OpenAI embedding models accept at most 8191 tokens per input
_MAX_INPUT_TOKENS = 8191


class Embedder(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


class OpenAIEmbedder:
    """
    Batched embeddings. Transient failures (429, 5xx, timeouts, connection errors)
    are retried with exponential backoff by the OpenAI SDK (max_retries).
    """

    def __init__(self, client: AsyncOpenAI, model: str, dimensions: int, batch_size: int) -> None:
        self.client = client
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dimensions, encoding_format="float"
        )
        # The API returns items with an index; never assume order
        vectors = [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
        if len(vectors) != len(texts):
            raise RuntimeError(f"Embedding count mismatch: sent {len(texts)}, got {len(vectors)}")
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            vectors.extend(await self._embed(batch))
            logger.debug("Embedded batch %d-%d", i, i + len(batch))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text]))[0]


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
        max_retries=settings.OPENAI_MAX_RETRIES,
    )


@lru_cache
def get_embedder() -> Embedder:
    return OpenAIEmbedder(
        get_openai_client(),
        model=settings.OPENAI_EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIM,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
    )
