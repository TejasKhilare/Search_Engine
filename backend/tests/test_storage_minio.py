"""Integration test against the real MinIO server. Skipped if MinIO is not running."""

import io
import uuid
from collections.abc import AsyncIterator

import pytest
from minio import Minio

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.services.storage import MinioStorage


@pytest.fixture
async def minio_storage() -> AsyncIterator[MinioStorage]:
    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY.get_secret_value(),
        secure=settings.MINIO_SECURE,
    )
    try:
        client.list_buckets()
    except Exception:
        pytest.skip("MinIO is not reachable")

    bucket = f"test-{uuid.uuid4().hex[:12]}"
    storage = MinioStorage(client, bucket)
    await storage.ensure_bucket()
    try:
        yield storage
    finally:
        for obj in client.list_objects(bucket, recursive=True):
            client.remove_object(bucket, obj.object_name)
        client.remove_bucket(bucket)


async def test_minio_roundtrip(minio_storage: MinioStorage) -> None:
    data = b"%PDF-1.7 " + bytes(range(256)) * 1000
    key = "users/u/documents/d.pdf"

    await minio_storage.put(key, io.BytesIO(data), len(data), "application/pdf")
    stat = await minio_storage.stat(key)
    assert stat.size == len(data) and stat.content_type == "application/pdf"

    assert b"".join(minio_storage.iter_bytes(key)) == data
    assert b"".join(minio_storage.iter_bytes(key, 10, 20)) == data[10:30]
    assert await minio_storage.ping()

    await minio_storage.delete(key)
    with pytest.raises(NotFoundError):
        await minio_storage.stat(key)
