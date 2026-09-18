import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.body_limit import MaxBodySizeMiddleware
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db.session import engine
from app.services.ingestion_queue import resume_unfinished_documents
from app.services.maintenance import maintenance_loop
from app.services.storage import get_storage

setup_logging(settings.LOG_LEVEL, json_logs=settings.is_production)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Fail fast if the database is unreachable or pgvector is not enabled
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        has_vector = await conn.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
    if not has_vector:
        raise RuntimeError(
            f"pgvector extension is not enabled in database '{settings.POSTGRES_DB}'. "
            "Run: CREATE EXTENSION vector;"
        )

    try:
        await get_storage().ensure_bucket()
    except Exception as e:
        raise RuntimeError(
            f"Object storage is unreachable at {settings.MINIO_ENDPOINT}. Is MinIO running? ({e})"
        ) from e

    resumed = await resume_unfinished_documents()
    if resumed:
        logger.info("Re-queued %d unfinished document(s)", resumed)

    maintenance = asyncio.create_task(maintenance_loop()) if settings.MAINTENANCE_ENABLED else None

    logger.info("Startup complete (env=%s)", settings.ENVIRONMENT)

    yield

    if maintenance:
        maintenance.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await maintenance
    await engine.dispose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="2.0.0",
        lifespan=lifespan,
        # Hide interactive docs in production
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else f"{settings.API_V1_PREFIX}/openapi.json",
    )

    # Middleware added later wraps earlier ones. Body limit sits inside CORS so a
    # 413 still carries CORS headers the browser can read.
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_upload_bytes + 1024 * 1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,  # required for auth cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Request-ID", "Range"],
        expose_headers=["X-Request-ID", "Content-Range", "Accept-Ranges", "Content-Disposition"],
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.COOKIE_SECURE)
    # Added last so it wraps everything, including CORS and error responses
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()
