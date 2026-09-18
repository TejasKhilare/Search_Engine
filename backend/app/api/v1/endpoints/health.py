import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import DbSession, StorageDep
from app.schemas.common import HealthResponse, ReadinessResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: the process is up. Does not touch dependencies."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def ready(db: DbSession, storage: StorageDep, response: Response) -> ReadinessResponse:
    """Readiness: dependencies are reachable. Returns 503 if any check fails."""
    checks: dict[str, str] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.warning("Readiness: database check failed: %s", e)
        checks["database"] = "unavailable"

    if checks["database"] == "ok":
        has_vector = await db.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        checks["pgvector"] = "ok" if has_vector else "missing"

    checks["storage"] = "ok" if await storage.ping() else "unavailable"

    is_ready = all(v == "ok" for v in checks.values())
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ready" if is_ready else "not_ready", checks=checks)
