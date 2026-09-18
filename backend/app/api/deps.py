from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import ACCESS_COOKIE, CSRF_HEADER
from app.core.exceptions import CsrfError, UnauthorizedError
from app.core.security import decode_access_token, verify_csrf_token
from app.db.session import get_db
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService, ClientInfo
from app.services.document_service import DocumentService
from app.services.embedding import Embedder, get_embedder
from app.services.ingestion_queue import IngestionQueue, get_ingestion_queue
from app.services.llm import ChatModel, get_chat_model
from app.services.rag_service import RagService
from app.services.search_service import SearchService
from app.services.storage import ObjectStorage, get_storage

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Lets Swagger UI's "Authorize" button obtain a token; auto_error=False because the
# cookie is the primary transport and is checked below.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/token", auto_error=False)

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def get_current_user(
    request: Request,
    db: DbSession,
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    """
    Accepts the access token from the Authorization header (API clients) or the
    HttpOnly cookie (browser). Cookie-authenticated unsafe requests must carry a
    valid X-CSRF-Token, because browsers attach cookies automatically.
    """
    via_cookie = bearer_token is None
    token = bearer_token or request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise UnauthorizedError("Not authenticated", headers={"WWW-Authenticate": "Bearer"})

    claims = decode_access_token(token)

    if via_cookie and request.method not in _SAFE_METHODS:
        csrf = request.headers.get(CSRF_HEADER)
        if not csrf or not verify_csrf_token(claims.session_id, csrf):
            raise CsrfError("CSRF token missing or invalid")

    user = await UserRepository(db).get_active_with_live_session(claims.user_id, claims.session_id)
    if user is None:
        raise UnauthorizedError("Session expired or revoked", headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


StorageDep = Annotated[ObjectStorage, Depends(get_storage)]


def get_document_service(
    db: DbSession, storage: StorageDep, queue: Annotated[IngestionQueue, Depends(get_ingestion_queue)]
) -> DocumentService:
    return DocumentService(db, storage, queue)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


def get_search_service(db: DbSession, embedder: Annotated[Embedder, Depends(get_embedder)]) -> SearchService:
    return SearchService(db, embedder)


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]


def get_rag_service(
    search: SearchServiceDep, llm: Annotated[ChatModel, Depends(get_chat_model)]
) -> RagService:
    return RagService(search, llm)


RagServiceDep = Annotated[RagService, Depends(get_rag_service)]


def get_client_info(request: Request) -> ClientInfo:
    return ClientInfo(
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


ClientInfoDep = Annotated[ClientInfo, Depends(get_client_info)]
