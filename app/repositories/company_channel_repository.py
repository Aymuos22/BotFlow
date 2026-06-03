"""
Repository for the CompanyChannel domain model.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_channel import CompanyChannel
from app.repositories.base import BaseRepository


class CompanyChannelRepository(BaseRepository[CompanyChannel]):
    """Async repository for CompanyChannel records."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(CompanyChannel, db)

    async def get_by_company(self, company_id: UUID) -> List[CompanyChannel]:
        """Return all channels for a company."""
        result = await self.db.execute(
            select(CompanyChannel).where(CompanyChannel.company_id == company_id)
        )
        return list(result.scalars().all())

    async def get_primary_by_company(
        self, company_id: UUID, channel_type: str = "whatsapp"
    ) -> Optional[CompanyChannel]:
        """
        Return the primary channel for a company+type combination.

        Used to enforce the constraint that only one primary channel
        of each type may exist per company.
        """
        result = await self.db.execute(
            select(CompanyChannel).where(
                CompanyChannel.company_id == company_id,
                CompanyChannel.channel_type == channel_type,
                CompanyChannel.is_primary.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_session_name(self, session_name: str) -> Optional[CompanyChannel]:
        """Find a channel by its ``session_name`` (deterministic channel key)."""
        result = await self.db.execute(
            select(CompanyChannel).where(
                CompanyChannel.session_name == session_name
            )
        )
        return result.scalar_one_or_none()

    async def get_by_phone_number(self, phone_number: str) -> Optional[CompanyChannel]:
        """Find a channel by phone number."""
        result = await self.db.execute(
            select(CompanyChannel).where(
                CompanyChannel.phone_number == phone_number
            )
        )
        return result.scalar_one_or_none()
