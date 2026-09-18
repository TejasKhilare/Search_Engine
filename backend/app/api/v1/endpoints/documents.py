import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Header, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DocumentServiceDep
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models import DocumentStatus
from app.schemas.common import ErrorResponse, Page
from app.schemas.document import DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])

_ERRORS = {401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}


def _content_disposition(filename: str) -> str:
    ascii_fallback = filename.encode("ascii", "ignore").decode() or "document.pdf"
    ascii_fallback = ascii_fallback.replace('"', "")
    return f"inline; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"


@router.post(
    "",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Same file already uploaded"},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse, "description": "Not a valid PDF"},
    },
)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_document(
    request: Request,
    user: CurrentUser,
    service: DocumentServiceDep,
    file: Annotated[UploadFile, File(description="PDF file")],
) -> DocumentOut:
    document = await service.upload(user, file)
    return DocumentOut.model_validate(document)


@router.get("", response_model=Page[DocumentOut], responses={401: {"model": ErrorResponse}})
async def list_documents(
    user: CurrentUser,
    service: DocumentServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[DocumentStatus | None, Query(alias="status")] = None,
) -> Page[DocumentOut]:
    items, total = await service.list(user, limit=limit, offset=offset, status=status_filter)
    return Page(items=[DocumentOut.model_validate(d) for d in items], total=total, limit=limit, offset=offset)


@router.get("/{document_id}", response_model=DocumentOut, responses=_ERRORS)
async def get_document(document_id: uuid.UUID, user: CurrentUser, service: DocumentServiceDep) -> DocumentOut:
    """Poll this for processing status."""
    return DocumentOut.model_validate(await service.get(user, document_id))


@router.get(
    "/{document_id}/file",
    response_class=StreamingResponse,
    responses={
        **_ERRORS,
        200: {"content": {"application/pdf": {}}},
        206: {"description": "Partial content (Range request)"},
        416: {"model": ErrorResponse},
    },
)
async def download_document_file(
    document_id: uuid.UUID,
    user: CurrentUser,
    service: DocumentServiceDep,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    """
    Streams the original PDF through the API (storage is never exposed to browsers).
    Supports single byte-range requests so PDF.js can load large files progressively.
    """
    document, size, byte_range, stream = await service.open_file(user, document_id, range_header)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": _content_disposition(document.filename),
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
    }
    if byte_range is None:
        headers["Content-Length"] = str(size)
        return StreamingResponse(stream, media_type=document.content_type, headers=headers)

    headers["Content-Length"] = str(byte_range.length)
    headers["Content-Range"] = f"bytes {byte_range.start}-{byte_range.end}/{size}"
    return StreamingResponse(
        stream,
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=document.content_type,
        headers=headers,
    )


@router.post(
    "/{document_id}/reprocess",
    response_model=DocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**_ERRORS, 409: {"model": ErrorResponse, "description": "Already queued/processing"}},
)
async def reprocess_document(
    document_id: uuid.UUID, user: CurrentUser, service: DocumentServiceDep
) -> DocumentOut:
    """Queues a failed (or ready) document to be processed again."""
    return DocumentOut.model_validate(await service.reprocess(user, document_id))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def delete_document(document_id: uuid.UUID, user: CurrentUser, service: DocumentServiceDep) -> Response:
    """Deletes the document, its chunks/embeddings and the stored file."""
    await service.delete(user, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
