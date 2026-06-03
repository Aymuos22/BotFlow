"""
Repository for the Company domain model.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    """Async repository for Company records."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Company, db)

    async def get_by_name(self, name: str) -> Optional[Company]:
        """Find a company by its unique machine-readable name (slug)."""
        result = await self.db.execute(
            select(Company).where(Company.name == name)
        )
        return result.scalar_one_or_none()

    async def get_by_status(self, status: str) -> List[Company]:
        """Return all companies with a given status."""
        result = await self.db.execute(
            select(Company).where(Company.status == status)
        )
        return list(result.scalars().all())

    async def get_active_companies(self) -> List[Company]:
        """Return all companies with status='active'."""
        return await self.get_by_status("active")
