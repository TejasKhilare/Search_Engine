import uuid
from datetime import UTC, datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken, User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        return await self.db.scalar(select(User).where(User.email == email))

    async def email_or_username_taken(self, email: str, username: str) -> bool:
        stmt = select(exists().where(or_(User.email == email, func.lower(User.username) == username.lower())))
        return bool(await self.db.scalar(stmt))

    async def get_active_with_live_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> User | None:
        """
        The user, only if active AND the session (refresh-token family) still has a
        live token. This is what makes logout / revocation take effect immediately
        for access tokens that have not yet expired.
        """
        live_session = exists().where(
            RefreshToken.family_id == session_id,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(UTC),
        )
        stmt = select(User).where(User.id == user_id, User.is_active.is_(True), live_session)
        return await self.db.scalar(stmt)

    def add(self, user: User) -> User:
        self.db.add(user)
        return user
