import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        return token

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshToken | None:
        """Row-locks the token so two concurrent refreshes can't both rotate it."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        return await self.db.scalar(stmt)

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return await self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    async def revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    async def revoke_all_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
