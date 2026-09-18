import pytest
from httpx import AsyncClient

from app.core.config import settings
from tests.fakes import InMemoryStorage

PREFIX = settings.API_V1_PREFIX


async def test_health(client: AsyncClient) -> None:
    res = await client.get(f"{PREFIX}/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert res.headers["x-request-id"]


async def test_ready_checks_all_dependencies(client: AsyncClient) -> None:
    res = await client.get(f"{PREFIX}/ready")
    assert res.status_code == 200
    assert res.json()["checks"] == {"database": "ok", "pgvector": "ok", "storage": "ok"}


async def test_ready_is_503_when_storage_down(
    client: AsyncClient, storage: InMemoryStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def down() -> bool:
        return False

    monkeypatch.setattr(storage, "ping", down)
    res = await client.get(f"{PREFIX}/ready")
    assert res.status_code == 503
    assert res.json() == {
        "status": "not_ready",
        "checks": {"database": "ok", "pgvector": "ok", "storage": "unavailable"},
    }


async def test_request_id_is_propagated(client: AsyncClient) -> None:
    res = await client.get(f"{PREFIX}/health", headers={"X-Request-ID": "abc-123"})
    assert res.headers["x-request-id"] == "abc-123"


async def test_unknown_route_uses_error_envelope(client: AsyncClient) -> None:
    res = await client.get(f"{PREFIX}/does-not-exist")
    assert res.status_code == 404
    body = res.json()["error"]
    assert body["code"] == "http_error"
    assert body["request_id"]
