import uuid
from collections.abc import AsyncIterator, Callable

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import engine, get_db
from app.main import app
from app.services.embedding import get_embedder
from app.services.ingestion_queue import get_ingestion_queue
from app.services.llm import get_chat_model
from app.services.storage import get_storage
from tests.fakes import FakeChatModel, FakeEmbedder, InMemoryStorage, RecordingQueue

# Rate limits are exercised explicitly in their own test
limiter.enabled = False

AUTH = f"{settings.API_V1_PREFIX}/auth"
TEST_PASSWORD = "Secret123!"


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """
    Session inside an outer transaction that is always rolled back, so tests
    never leave data behind. Commits inside the code under test become savepoints.
    """
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
def storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def queue() -> RecordingQueue:
    return RecordingQueue()


@pytest.fixture
def chat_model() -> FakeChatModel:
    return FakeChatModel()


@pytest.fixture
async def client(
    db_session: AsyncSession,
    storage: InMemoryStorage,
    embedder: FakeEmbedder,
    queue: RecordingQueue,
    chat_model: FakeChatModel,
) -> AsyncIterator[AsyncClient]:
    """HTTP client wired to the rolled-back DB session and in-memory fakes."""

    async def _get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_ingestion_queue] = lambda: queue
    app.dependency_overrides[get_chat_model] = lambda: chat_model
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


async def bearer_headers(client: AsyncClient) -> dict[str, str]:
    """Registers a fresh user and returns Authorization headers for them."""
    suffix = uuid.uuid4().hex[:8]
    email = f"user{suffix}@example.com"
    res = await client.post(
        f"{AUTH}/register", json={"email": email, "username": f"user_{suffix}", "password": TEST_PASSWORD}
    )
    assert res.status_code == 201, res.text
    res = await client.post(f"{AUTH}/token", data={"username": email, "password": TEST_PASSWORD})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def make_pdf() -> Callable[..., bytes]:
    def _make(
        pages: int = 1,
        text: str = "Hello world",
        password: str | None = None,
        page_texts: list[str] | None = None,
    ) -> bytes:
        doc = pymupdf.open()
        for body in page_texts or [f"{text} — page {n + 1}" for n in range(pages)]:
            # insert_textbox wraps long text inside the page margins
            doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 770), body, fontsize=10)
        if password:
            data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw=password, user_pw=password)
        else:
            data = doc.tobytes()
        doc.close()
        return data

    return _make
