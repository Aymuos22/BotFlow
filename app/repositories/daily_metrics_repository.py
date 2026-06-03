"""
Repository for DailyCompanyMetrics.
"""
import uuid
from datetime import date
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_company_metrics import DailyCompanyMetrics
from app.repositories.base import BaseRepository


class DailyMetricsRepository(BaseRepository[DailyCompanyMetrics]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(DailyCompanyMetrics, db)

    async def get_for_date(
        self, company_id: uuid.UUID, metric_date: date
    ) -> Optional[DailyCompanyMetrics]:
        result = await self.db.execute(
            select(DailyCompanyMetrics).where(
                DailyCompanyMetrics.company_id == company_id,
                DailyCompanyMetrics.metric_date == metric_date,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_company(
        self,
        company_id: uuid.UUID,
        since: Optional[date] = None,
        limit: int = 90,
    ) -> List[DailyCompanyMetrics]:
        stmt = (
            select(DailyCompanyMetrics)
            .where(DailyCompanyMetrics.company_id == company_id)
            .order_by(DailyCompanyMetrics.metric_date.desc())
            .limit(limit)
        )
        if since:
            stmt = stmt.where(DailyCompanyMetrics.metric_date >= since)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self, company_id: uuid.UUID, metric_date: date, data: dict
    ) -> DailyCompanyMetrics:
        """
        Insert or update the daily metrics row for (company_id, metric_date).
        """
        existing = await self.get_for_date(company_id, metric_date)
        if existing:
            return await self.update(existing, data)
        data["company_id"] = company_id
        data["metric_date"] = metric_date
        return await self.create(data)
