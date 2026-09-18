from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AuthServiceDep, ClientInfoDep, CurrentUser
from app.core.config import settings
from app.core.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.exceptions import UnauthorizedError, app_error_response
from app.core.rate_limit import limiter
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.schemas.common import ErrorResponse
from app.services.auth_service import IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"])

_ERRORS = {
    401: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


def _auth_response(response: Response, user_out: UserOut, tokens: IssuedTokens) -> AuthResponse:
    set_auth_cookies(
        response,
        access_token=tokens.access_token,
        access_expires_at=tokens.access_expires_at,
        refresh_token=tokens.refresh_token,
        refresh_expires_at=tokens.refresh_expires_at,
        csrf_token=tokens.csrf_token,
    )
    return AuthResponse(
        user=user_out, csrf_token=tokens.csrf_token, access_token_expires_at=tokens.access_expires_at
    )


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={**_ERRORS, 409: {"model": ErrorResponse}},
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(request: Request, body: RegisterRequest, auth: AuthServiceDep) -> UserOut:
    user = await auth.register(body.email, body.username, body.password.get_secret_value())
    return UserOut.model_validate(user)


@router.post("/login", response_model=AuthResponse, responses=_ERRORS)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    request: Request, response: Response, body: LoginRequest, auth: AuthServiceDep, client: ClientInfoDep
) -> AuthResponse:
    """Browser login: sets HttpOnly access/refresh cookies and returns the CSRF token."""
    user, tokens = await auth.login(body.email, body.password.get_secret_value(), client)
    return _auth_response(response, UserOut.model_validate(user), tokens)


@router.post("/token", response_model=TokenResponse, responses=_ERRORS)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def token(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth: AuthServiceDep,
    client: ClientInfoDep,
) -> TokenResponse:
    """OAuth2 password flow for API clients / Swagger UI. `username` is the email. No cookies."""
    _, tokens = await auth.login(form.username, form.password, client)
    return TokenResponse(
        access_token=tokens.access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=AuthResponse, responses=_ERRORS)
@limiter.limit("30/minute")
async def refresh(
    request: Request, response: Response, auth: AuthServiceDep, client: ClientInfoDep
) -> AuthResponse | JSONResponse:
    """
    Rotates the refresh token and issues a new access token.
    Not CSRF-protected: it changes nothing an attacker could observe or use, and it
    must work after a page reload when the frontend has no CSRF token in memory yet.
    """
    try:
        user, tokens = await auth.refresh(request.cookies.get(REFRESH_COOKIE), client)
    except UnauthorizedError as e:
        error = app_error_response(e)
        clear_auth_cookies(error)
        return error
    return _auth_response(response, UserOut.model_validate(user), tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, auth: AuthServiceDep) -> Response:
    """Ends the current session. Works even if the access token has already expired."""
    await auth.logout(request.cookies.get(REFRESH_COOKIE))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response)
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def logout_all(user: CurrentUser, auth: AuthServiceDep) -> Response:
    """Ends every session of the current user on every device."""
    await auth.logout_all(user.id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response)
    return response


@router.get("/me", response_model=UserOut, responses=_ERRORS)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
