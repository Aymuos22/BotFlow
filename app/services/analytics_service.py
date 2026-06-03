"""
AnalyticsService – computes live analytics from the Phase 2 tables.

All methods delegate heavy SQL to ``AnalyticsRepository`` and apply
presentation logic (rates, percentages, zero-guard arithmetic) here.

No external services are called; all data is in the relational DB.
"""
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List

from app.repositories.analytics_repository import AnalyticsRepository


class AnalyticsService:
    def __init__(self, analytics_repo: AnalyticsRepository) -> None:
        self._repo = analytics_repo

    # ------------------------------------------------------------------ #
    # Overview
    # ------------------------------------------------------------------ #

    async def get_overview(
        self, company_id: uuid.UUID, period_days: int = 30
    ) -> Dict[str, Any]:
        msg_counts = await self._repo.get_message_counts(company_id, period_days)
        active_convs = await self._repo.get_active_conversation_count(company_id)
        handoff_counts = await self._repo.get_handoff_counts(company_id, period_days)

        total_customer = msg_counts["total_customer"]
        total_bot = msg_counts["total_bot"]
        total_fallback = msg_counts["total_fallback"]
        total_handoffs = handoff_counts["total"]

        fallback_rate = (total_fallback / total_bot) if total_bot > 0 else 0.0
        handoff_rate = (total_handoffs / total_customer) if total_customer > 0 else 0.0

        return {
            "company_id": company_id,
            "period_days": period_days,
            "total_customer_messages": total_customer,
            "total_bot_messages": total_bot,
            "total_fallback_messages": total_fallback,
            "total_handoffs": total_handoffs,
            "active_conversations": active_convs,
            "fallback_rate": round(fallback_rate, 4),
            "handoff_rate": round(handoff_rate, 4),
        }

    # ------------------------------------------------------------------ #
    # Language breakdown
    # ------------------------------------------------------------------ #

    async def get_language_analytics(
        self, company_id: uuid.UUID, period_days: int = 30
    ) -> Dict[str, Any]:
        raw = await self._repo.get_language_breakdown(company_id, period_days)
        total = sum(r["count"] for r in raw)

        breakdown = [
            {
                "language": r["language"],
                "count": r["count"],
                "percentage": round((r["count"] / total * 100) if total > 0 else 0.0, 2),
            }
            for r in raw
        ]

        return {
            "company_id": company_id,
            "period_days": period_days,
            "breakdown": breakdown,
        }

    # ------------------------------------------------------------------ #
    # Lead warmth trend
    # ------------------------------------------------------------------ #

    async def get_lead_warmth_analytics(
        self, company_id: uuid.UUID, period_days: int = 30
    ) -> Dict[str, Any]:
        raw = await self._repo.get_lead_warmth_daily_counts(company_id, period_days)
        by_date = {
            r["date"]: {
                "date": r["date"],
                "hot": 0,
                "warm": 0,
                "cold": 0,
            }
            for r in raw
        }

        today = date.today()
        start = today - timedelta(days=period_days - 1)
        for offset in range(period_days):
            day = (start + timedelta(days=offset)).isoformat()
            by_date.setdefault(day, {"date": day, "hot": 0, "warm": 0, "cold": 0})

        totals = {"hot": 0, "warm": 0, "cold": 0}
        for r in raw:
            warmth = str(r["lead_warmth"])
            if warmth not in totals:
                continue
            count = int(r["count"])
            by_date[r["date"]][warmth] = count
            totals[warmth] += count

        return {
            "company_id": company_id,
            "period_days": period_days,
            "series": [by_date[d] for d in sorted(by_date)],
            "totals": totals,
        }

    # ------------------------------------------------------------------ #
    # Fallback analytics
    # ------------------------------------------------------------------ #

    async def get_fallback_analytics(
        self, company_id: uuid.UUID, period_days: int = 30
    ) -> Dict[str, Any]:
        msg_counts = await self._repo.get_message_counts(company_id, period_days)
        top_fallback_queries = await self._repo.get_top_fallback_queries(
            company_id, period_days
        )

        total_bot = msg_counts["total_bot"]
        total_fallback = msg_counts["total_fallback"]
        fallback_rate = (total_fallback / total_bot) if total_bot > 0 else 0.0

        return {
            "company_id": company_id,
            "period_days": period_days,
            "total_fallbacks": total_fallback,
            "fallback_rate": round(fallback_rate, 4),
            "top_fallback_queries": top_fallback_queries,
        }

    # ------------------------------------------------------------------ #
    # Handoff analytics
    # ------------------------------------------------------------------ #

    async def get_handoff_analytics(
        self, company_id: uuid.UUID, period_days: int = 30
    ) -> Dict[str, Any]:
        counts = await self._repo.get_handoff_counts(company_id, period_days)
        avg_secs = await self._repo.get_avg_handoff_resolution_seconds(
            company_id, period_days
        )

        total = counts["total"]
        resolved = counts["resolved"]
        resolution_rate = (resolved / total) if total > 0 else 0.0

        return {
            "company_id": company_id,
            "period_days": period_days,
            "total_handoffs": total,
            "resolved_count": resolved,
            "cancelled_count": counts["cancelled"],
            "pending_count": counts["pending"],
            "resolution_rate": round(resolution_rate, 4),
            "avg_resolution_seconds": avg_secs,
        }

    # ------------------------------------------------------------------ #
    # Top queries
    # ------------------------------------------------------------------ #

    async def get_top_queries(
        self, company_id: uuid.UUID, period_days: int = 30, limit: int = 20
    ) -> Dict[str, Any]:
        top_queries = await self._repo.get_top_queries(
            company_id, period_days, limit=limit
        )
        top_fallback = await self._repo.get_top_fallback_queries(
            company_id, period_days, limit=limit
        )
        lang_raw = await self._repo.get_language_breakdown(company_id, period_days)
        lang_counts = {r["language"]: r["count"] for r in lang_raw}

        return {
            "company_id": company_id,
            "period_days": period_days,
            "top_queries": top_queries,
            "top_fallback_queries": top_fallback,
            "language_counts": lang_counts,
        }
