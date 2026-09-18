import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

# ── Passwords (Argon2id) ─────────────────────────────────────────────────────
_password_hash = PasswordHash.recommended()
# Verified against when the user does not exist, so response time doesn't reveal it
_DUMMY_HASH = _password_hash.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Returns (valid, new_hash). new_hash is set when the stored hash uses outdated parameters."""
    return _password_hash.verify_and_update(password, password_hash)


def burn_password_check(password: str) -> None:
    _password_hash.verify(password, _DUMMY_HASH)


# ── Access tokens (JWT) ──────────────────────────────────────────────────────
_TOKEN_TYPE_ACCESS = "access"  # noqa: S105
_INVALID_TOKEN = "Invalid or expired token"  # noqa: S105


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID  # refresh-token family this access token belongs to


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "type": _TOKEN_TYPE_ACCESS,
        "iss": settings.JWT_ISSUER,
        "iat": now,
        "exp": expires_at,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> AccessTokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],  # pinned: never trust the token's own "alg"
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "sid", "type", "iss"]},
        )
        if payload["type"] != _TOKEN_TYPE_ACCESS:
            raise UnauthorizedError(_INVALID_TOKEN)
        return AccessTokenClaims(user_id=uuid.UUID(payload["sub"]), session_id=uuid.UUID(payload["sid"]))
    except (jwt.PyJWTError, ValueError, KeyError) as e:
        raise UnauthorizedError(_INVALID_TOKEN, headers={"WWW-Authenticate": "Bearer"}) from e


# ── Refresh tokens (opaque, hashed at rest) ──────────────────────────────────
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── CSRF (HMAC of the session id) ────────────────────────────────────────────
# Stateless and bound to the session: an attacker can neither read it cross-origin
# nor compute it without the server secret.
def csrf_token_for(session_id: uuid.UUID) -> str:
    return hmac.new(
        settings.JWT_SECRET_KEY.get_secret_value().encode(),
        f"csrf:{session_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_csrf_token(session_id: uuid.UUID, token: str) -> bool:
    return hmac.compare_digest(csrf_token_for(session_id), token)
