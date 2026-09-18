import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, RagServiceDep, SearchServiceDep
from app.core.config import settings
from app.core.rate_limit import limiter
from app.schemas.common import ErrorResponse
from app.schemas.search import AskRequest, AskResponse, SearchResponse

router = APIRouter(tags=["search"])

_ERRORS = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


@router.get("/search", response_model=SearchResponse, responses=_ERRORS)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def search(
    request: Request,
    user: CurrentUser,
    service: SearchServiceDep,
    q: Annotated[str, Query(min_length=1, max_length=500, description="Search query")],
    document_id: Annotated[uuid.UUID | None, Query(description="Search within one document")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = settings.SEARCH_TOP_K,
) -> SearchResponse:
    """
    Hybrid search (semantic + keyword + fuzzy) over your documents.
    Returns at most one result per page, best first.
    """
    return await service.search(user, q.strip(), document_id, limit)


@router.post("/ask", response_model=AskResponse, responses={**_ERRORS, 503: {"model": ErrorResponse}})
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def ask(request: Request, body: AskRequest, user: CurrentUser, rag: RagServiceDep) -> AskResponse:
    """Answers a question from your documents, with [n] citations."""
    return await rag.answer(user, body.question, body.document_ids)


@router.post(
    "/ask/stream",
    response_class=StreamingResponse,
    responses={
        **_ERRORS,
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE events: `sources`, then `delta` (repeated), then `done` or `error`",
        },
    },
)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def ask_stream(
    request: Request, body: AskRequest, user: CurrentUser, rag: RagServiceDep
) -> StreamingResponse:
    """Same as /ask, streamed token by token as Server-Sent Events."""
    events = await rag.prepare_stream(user, body.question, body.document_ids)
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # disable proxy buffering
    )
