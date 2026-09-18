import asyncio
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import BinaryIO, Protocol

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024
_MISSING_CODES = {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}


@dataclass(frozen=True, slots=True)
class StoredObject:
    size: int
    content_type: str


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    key: str
    last_modified: datetime


class ObjectStorage(Protocol):
    """Blob storage used for original documents. MinIO today; S3 is a drop-in implementation."""

    async def ensure_bucket(self) -> None: ...
    async def put(self, key: str, data: BinaryIO, size: int, content_type: str) -> None: ...
    async def stat(self, key: str) -> StoredObject: ...
    def iter_bytes(self, key: str, offset: int = 0, length: int | None = None) -> Iterator[bytes]: ...
    async def delete(self, key: str) -> None: ...
    async def list_objects(self, prefix: str) -> list[ObjectInfo]: ...
    async def ping(self) -> bool: ...


class MinioStorage:
    """
    The MinIO SDK is synchronous; every call is pushed to a worker thread so it
    never blocks the event loop.
    """

    def __init__(self, client: Minio, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    async def ensure_bucket(self) -> None:
        if not await asyncio.to_thread(self.client.bucket_exists, self.bucket):
            await asyncio.to_thread(self.client.make_bucket, self.bucket)
            logger.info("Created storage bucket %s", self.bucket)

    async def put(self, key: str, data: BinaryIO, size: int, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.put_object, self.bucket, key, data, size, content_type=content_type
        )

    async def stat(self, key: str) -> StoredObject:
        try:
            obj = await asyncio.to_thread(self.client.stat_object, self.bucket, key)
        except S3Error as e:
            if e.code in _MISSING_CODES:
                raise NotFoundError("File not found in storage") from e
            raise
        return StoredObject(size=obj.size or 0, content_type=obj.content_type or "application/octet-stream")

    def iter_bytes(self, key: str, offset: int = 0, length: int | None = None) -> Iterator[bytes]:
        # Synchronous generator: Starlette runs it in a threadpool when streaming
        response = self.client.get_object(self.bucket, key, offset=offset, length=length or 0)
        try:
            yield from response.stream(_CHUNK_SIZE)
        finally:
            response.close()
            response.release_conn()

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.remove_object, self.bucket, key)

    async def list_objects(self, prefix: str) -> list[ObjectInfo]:
        def _list() -> list[ObjectInfo]:
            return [
                ObjectInfo(key=o.object_name, last_modified=o.last_modified)
                for o in self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
                if o.object_name and o.last_modified
            ]

        return await asyncio.to_thread(_list)

    async def ping(self) -> bool:
        try:
            return await asyncio.to_thread(self.client.bucket_exists, self.bucket)
        except Exception as e:
            logger.warning("Storage ping failed: %s", e)
            return False


@lru_cache
def get_storage() -> ObjectStorage:
    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY.get_secret_value(),
        secure=settings.MINIO_SECURE,
    )
    return MinioStorage(client, settings.MINIO_BUCKET)
