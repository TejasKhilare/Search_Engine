from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.exceptions import error_response

# In-memory storage: correct for a single process. With multiple workers/instances,
# pass storage_uri="redis://..." so limits are shared.
limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED)


async def rate_limit_exceeded_handler(_: Request, exc: Exception) -> Response:
    limit = exc.detail if isinstance(exc, RateLimitExceeded) else "exceeded"
    return error_response(
        429,
        "rate_limited",
        f"Too many requests: limit is {limit}",
        headers={"Retry-After": "60"},
    )
