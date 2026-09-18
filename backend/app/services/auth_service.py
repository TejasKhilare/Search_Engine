import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    burn_password_check,
    create_access_token,
    csrf_token_for,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

_INVALID_CREDENTIALS = "Invalid email or password"
_INVALID_SESSION = "Session expired or invalid. Please log in again."


@dataclass(frozen=True, slots=True)
class ClientInfo:
    user_agent: str | None
    ip_address: str | None


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    csrf_token: str
    session_id: uuid.UUID


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.tokens = RefreshTokenRepository(db)

    # ── Registration ─────────────────────────────────────────────────────────
    async def register(self, email: str, username: str, password: str) -> User:
        email = normalize_email(email)
        if await self.users.email_or_username_taken(email, username):
            raise ConflictError("Email or username is already registered")

        user = self.users.add(User(email=email, username=username, password_hash=hash_password(password)))
        try:
            await self.db.commit()
        except IntegrityError as e:  # lost a race with a concurrent registration
            await self.db.rollback()
            raise ConflictError("Email or username is already registered") from e

        logger.info("User registered", extra={"user_id": str(user.id)})
        return user

    # ── Login ────────────────────────────────────────────────────────────────
    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(normalize_email(email))
        if user is None:
            burn_password_check(password)  # equalise timing with the "wrong password" path
            raise UnauthorizedError(_INVALID_CREDENTIALS)

        valid, new_hash = verify_password(password, user.password_hash)
        if not valid:
            raise UnauthorizedError(_INVALID_CREDENTIALS)
        if not user.is_active:
            raise UnauthorizedError("Account is disabled")
        if new_hash:  # hashing parameters were upgraded since this hash was made
            user.password_hash = new_hash
        return user

    async def login(self, email: str, password: str, client: ClientInfo) -> tuple[User, IssuedTokens]:
        user = await self.authenticate(email, password)
        user.last_login_at = datetime.now(UTC)
        tokens, _ = self._issue(user, family_id=uuid.uuid4(), client=client)
        await self.db.commit()
        logger.info("User logged in", extra={"user_id": str(user.id), "session_id": str(tokens.session_id)})
        return user, tokens

    # ── Refresh (rotation + reuse detection) ─────────────────────────────────
    async def refresh(self, raw_refresh_token: str | None, client: ClientInfo) -> tuple[User, IssuedTokens]:
        if not raw_refresh_token:
            raise UnauthorizedError(_INVALID_SESSION)

        now = datetime.now(UTC)
        current = await self.tokens.get_by_hash_for_update(hash_token(raw_refresh_token))
        if current is None:
            raise UnauthorizedError(_INVALID_SESSION)

        if current.revoked_at is not None:
            await self._handle_revoked_token_reuse(current, now)
            raise UnauthorizedError(_INVALID_SESSION)

        if current.expires_at <= now:
            raise UnauthorizedError(_INVALID_SESSION)

        user = await self.db.get(User, current.user_id)
        if user is None or not user.is_active:
            await self.tokens.revoke_family(current.family_id, now)
            await self.db.commit()
            raise UnauthorizedError(_INVALID_SESSION)

        tokens, new_record = self._issue(user, family_id=current.family_id, client=client)
        await self.db.flush()  # assigns new_record.id
        current.revoked_at = now
        current.replaced_by_id = new_record.id
        await self.db.commit()
        return user, tokens

    async def _handle_revoked_token_reuse(self, token: RefreshToken, now: datetime) -> None:
        rotated_recently = (
            token.replaced_by_id is not None
            and token.revoked_at is not None
            and now - token.revoked_at < timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS)
        )
        if rotated_recently:
            # Benign race (e.g. two tabs refreshing at once): reject, keep the session.
            return

        # A rotated-away token came back: it was copied. Kill the whole session.
        await self.tokens.revoke_family(token.family_id, now)
        await self.db.commit()
        logger.warning(
            "Refresh token reuse detected; session revoked",
            extra={"user_id": str(token.user_id), "session_id": str(token.family_id)},
        )

    # ── Logout ───────────────────────────────────────────────────────────────
    async def logout(self, raw_refresh_token: str | None) -> None:
        """Revokes the current session. Idempotent; never fails for a bad/missing token."""
        if not raw_refresh_token:
            return
        token = await self.tokens.get_by_hash(hash_token(raw_refresh_token))
        if token is not None:
            await self.tokens.revoke_family(token.family_id, datetime.now(UTC))
            await self.db.commit()

    async def logout_all(self, user_id: uuid.UUID) -> None:
        await self.tokens.revoke_all_for_user(user_id, datetime.now(UTC))
        await self.db.commit()
        logger.info("All sessions revoked", extra={"user_id": str(user_id)})

    # ── Internal ─────────────────────────────────────────────────────────────
    def _issue(
        self, user: User, family_id: uuid.UUID, client: ClientInfo
    ) -> tuple[IssuedTokens, RefreshToken]:
        raw_refresh = generate_refresh_token()
        refresh_expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        record = self.tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(raw_refresh),
                family_id=family_id,
                expires_at=refresh_expires_at,
                user_agent=(client.user_agent or "")[:512] or None,
                ip_address=client.ip_address,
            )
        )
        access_token, access_expires_at = create_access_token(user.id, family_id)
        tokens = IssuedTokens(
            access_token=access_token,
            access_expires_at=access_expires_at,
            refresh_token=raw_refresh,
            refresh_expires_at=refresh_expires_at,
            csrf_token=csrf_token_for(family_id),
            session_id=family_id,
        )
        return tokens, record
