"""
MetricsAggregationService – pre-aggregates daily metrics for a company.

Intended to be called once per day per company (e.g. from a cron job or
an admin API endpoint).

It reads live data from Phase 2 tables and writes a single
``DailyCompanyMetrics`` row for the given date.  Subsequent calls for
the same (company, date) pair will update the existing row (upsert).

No background worker daemon is required – the aggregation is triggered
explicitly and stores state in the relational DB.
"""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.daily_metrics_repository import DailyMetricsRepository

logger = logging.getLogger(__name__)


class MetricsAggregationService:
    def __init__(
        self,
        analytics_repo: AnalyticsRepository,
        daily_metrics_repo: DailyMetricsRepository,
    ) -> None:
        self._analytics = analytics_repo
        self._daily = daily_metrics_repo

    async def aggregate_for_date(
        self,
        company_id: uuid.UUID,
        target_date: Optional[date] = None,
    ) -> None:
        """
        Compute and persist daily metrics for *company_id* on *target_date*.

        If *target_date* is None, yesterday (UTC) is used.  This avoids
        aggregating partial-day data for today.
        """
        if target_date is None:
            target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        logger.info(
            "Aggregating daily metrics",
            extra={"company_id": str(company_id), "date": str(target_date)},
        )

        # 1-day window for message/handoff counts
        period_days = 1

        msg_counts = await self._analytics.get_message_counts(company_id, period_days)
        handoff_counts = await self._analytics.get_handoff_counts(company_id, period_days)
        active_convs = await self._analytics.get_active_conversation_count(company_id)
        lang_raw = await self._analytics.get_language_breakdown(company_id, period_days)

        lang_map = {r["language"]: r["count"] for r in lang_raw}

        await self._daily.upsert(
            company_id=company_id,
            metric_date=target_date,
            data={
                "total_messages": msg_counts["total_customer"] + msg_counts["total_bot"],
                "bot_messages": msg_counts["total_bot"],
                "fallback_messages": msg_counts["total_fallback"],
                "handoff_count": handoff_counts["total"],
                "active_conversations": active_convs,
                "english_count": lang_map.get("english", 0),
                "hindi_count": lang_map.get("hindi", 0),
                "hinglish_count": lang_map.get("hinglish", 0),
            },
        )
        logger.info(
            "Daily metrics aggregated",
            extra={"company_id": str(company_id), "date": str(target_date)},
        )
