import hashlib
import math
import re
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import BinaryIO

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.services.storage import ObjectInfo, StoredObject


class InMemoryStorage:
    """ObjectStorage test double."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.modified: dict[str, datetime] = {}

    async def ensure_bucket(self) -> None:
        return None

    async def put(self, key: str, data: BinaryIO, size: int, content_type: str) -> None:
        payload = data.read()
        assert len(payload) == size
        self.objects[key] = (payload, content_type)
        self.modified[key] = datetime.now(UTC)

    async def stat(self, key: str) -> StoredObject:
        if key not in self.objects:
            raise NotFoundError("File not found in storage")
        payload, content_type = self.objects[key]
        return StoredObject(size=len(payload), content_type=content_type)

    def iter_bytes(self, key: str, offset: int = 0, length: int | None = None) -> Iterator[bytes]:
        payload, _ = self.objects[key]
        end = len(payload) if length is None else offset + length
        yield payload[offset:end]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)
        self.modified.pop(key, None)

    async def list_objects(self, prefix: str) -> list[ObjectInfo]:
        return [ObjectInfo(k, self.modified[k]) for k in self.objects if k.startswith(prefix)]

    async def ping(self) -> bool:
        return True


class FakeEmbedder:
    """
    Deterministic bag-of-words embedder: texts sharing words have high cosine
    similarity, so semantic ranking is testable without calling OpenAI.
    """

    def __init__(self, dim: int = settings.EMBEDDING_DIM) -> None:
        self.dim = dim
        self.calls: list[list[str]] = []
        self.fail_with: Exception | None = None

    def vector(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for word in re.findall(r"\w+", text.lower()):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.0  # noqa: S324
        norm = math.sqrt(sum(x * x for x in v))
        if norm == 0:
            v[0] = 1.0
            return v
        return [x / norm for x in v]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.fail_with:
            raise self.fail_with
        self.calls.append(texts)
        return [self.vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        if self.fail_with:
            raise self.fail_with
        return self.vector(text)


class RecordingQueue:
    """IngestionQueue test double: records instead of running."""

    def __init__(self) -> None:
        self.enqueued: list[uuid.UUID] = []

    def enqueue(self, document_id: uuid.UUID) -> None:
        self.enqueued.append(document_id)


class FakeChatModel:
    """ChatModel test double: records prompts, returns a canned answer."""

    def __init__(self, answer: str = "Revenue grew 18 percent [1].") -> None:
        self.answer = answer
        self.calls: list[list[dict[str, str]]] = []
        self.fail_with: Exception | None = None

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if self.fail_with:
            raise self.fail_with
        return self.answer

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        self.calls.append(messages)
        if self.fail_with:
            raise self.fail_with
        for word in self.answer.split(" "):
            yield word + " "
