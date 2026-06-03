"""
Repository for the OnboardingStatus domain model.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.onboarding_status import OnboardingStatus
from app.repositories.base import BaseRepository


class OnboardingStatusRepository(BaseRepository[OnboardingStatus]):
    """Async repository for OnboardingStatus records."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(OnboardingStatus, db)

    async def get_by_company(self, company_id: UUID) -> Optional[OnboardingStatus]:
        """Return the onboarding status record for a company (one-to-one)."""
        result = await self.db.execute(
            select(OnboardingStatus).where(
                OnboardingStatus.company_id == company_id
            )
        )
        return result.scalar_one_or_none()
