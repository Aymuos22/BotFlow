"""Repository for PortalUser."""
import uuid
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portal_user import PortalUser
from app.repositories.base import BaseRepository


class PortalUserRepository(BaseRepository[PortalUser]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(PortalUser, db)

    async def get_by_username(self, username: str) -> Optional[PortalUser]:
        result = await self.db.execute(
            select(PortalUser).where(PortalUser.username == username)
        )
        return result.scalar_one_or_none()

    async def count_all(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(PortalUser))
        return int(result.scalar_one())

    async def list_all(self, limit: int = 500) -> List[PortalUser]:
        result = await self.db.execute(
            select(PortalUser).order_by(PortalUser.username).limit(limit)
        )
        return list(result.scalars().all())
