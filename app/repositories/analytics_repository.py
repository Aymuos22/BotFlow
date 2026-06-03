"""
AnalyticsRepository – complex aggregate queries for the analytics APIs.

All queries target existing Phase 2 tables:
  - messages (sender_type, response_type, language, created_at)
  - conversations (status, detected_language)
  - retrieval_logs (fallback_triggered, query_text)
  - handoffs (status, resolved_at, created_at)

No external dependencies; pure SQLAlchemy selects.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import case, cast, Float, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.handoff import Handoff
from app.models.message import Message
from app.models.retrieval_log import RetrievalLog


class AnalyticsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _since(self, period_days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=period_days)

    # ------------------------------------------------------------------ #
    # Message counters
    # ------------------------------------------------------------------ #

    async def get_message_counts(
        self, company_id: uuid.UUID, period_days: int
    ) -> Dict[str, int]:
        since = self._since(period_days)
        result = await self.db.execute(
            select(
                func.count().label("total"),
                func.sum(
                    case((Message.sender_type == "bot", 1), else_=0)
                ).label("bot"),
                func.sum(
                    case(
                        (
                            (Message.sender_type == "bot")
                            & (Message.response_type == "fallback"),
                            1,
                        ),
                        else_=0,
                    )
                ).label("fallback"),
                func.sum(
                    case((Message.sender_type == "customer", 1), else_=0)
                ).label("customer"),
            ).where(
                Message.company_id == company_id,
                Message.created_at >= since,
            )
        )
        row = result.one()
        return {
            "total_customer": int(row.customer or 0),
            "total_bot": int(row.bot or 0),
            "total_fallback": int(row.fallback or 0),
        }

    # ------------------------------------------------------------------ #
    # Conversation counters
    # ------------------------------------------------------------------ #

    async def get_active_conversation_count(
        self, company_id: uuid.UUID
    ) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Conversation)
            .where(
                Conversation.company_id == company_id,
                Conversation.status == "active",
            )
        )
        return result.scalar_one()

    async def get_lead_warmth_daily_counts(
        self, company_id: uuid.UUID, period_days: int
    ) -> List[Dict[str, Any]]:
        since = self._since(period_days)
        day_expr = func.date(Conversation.created_at).label("day")
        result = await self.db.execute(
            select(
                day_expr,
                Conversation.lead_warmth,
                func.count().label("cnt"),
            )
            .where(
                Conversation.company_id == company_id,
                Conversation.created_at >= since,
                Conversation.lead_warmth.in_(["hot", "warm", "cold"]),
            )
            .group_by(day_expr, Conversation.lead_warmth)
            .order_by(day_expr.asc())
        )
        rows = result.all()
        return [
            {
                "date": str(r.day),
                "lead_warmth": r.lead_warmth,
                "count": int(r.cnt or 0),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # Handoff counters
    # ------------------------------------------------------------------ #

    async def get_handoff_counts(
        self, company_id: uuid.UUID, period_days: int
    ) -> Dict[str, int]:
        since = self._since(period_days)
        result = await self.db.execute(
            select(
                func.count().label("total"),
                func.sum(
                    case((Handoff.status == "resolved", 1), else_=0)
                ).label("resolved"),
                func.sum(
                    case((Handoff.status == "cancelled", 1), else_=0)
                ).label("cancelled"),
                func.sum(
                    case(
                        (Handoff.status.notin_(["resolved", "cancelled"]), 1),
                        else_=0,
                    )
                ).label("pending"),
            ).where(
                Handoff.company_id == company_id,
                Handoff.created_at >= since,
            )
        )
        row = result.one()
        return {
            "total": int(row.total or 0),
            "resolved": int(row.resolved or 0),
            "cancelled": int(row.cancelled or 0),
            "pending": int(row.pending or 0),
        }

    # ------------------------------------------------------------------ #
    # Language breakdown
    # ------------------------------------------------------------------ #

    async def get_language_breakdown(
        self, company_id: uuid.UUID, period_days: int
    ) -> List[Dict[str, Any]]:
        since = self._since(period_days)
        result = await self.db.execute(
            select(
                Message.language,
                func.count().label("cnt"),
            )
            .where(
                Message.company_id == company_id,
                Message.sender_type == "customer",
                Message.language.isnot(None),
                Message.created_at >= since,
            )
            .group_by(Message.language)
            .order_by(func.count().desc())
        )
        rows = result.all()
        return [{"language": r.language, "count": r.cnt} for r in rows]

    # ------------------------------------------------------------------ #
    # Top queries
    # ------------------------------------------------------------------ #

    async def get_top_queries(
        self, company_id: uuid.UUID, period_days: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        since = self._since(period_days)
        result = await self.db.execute(
            select(
                func.lower(func.trim(Message.message_text)).label("query"),
                func.count().label("cnt"),
            )
            .where(
                Message.company_id == company_id,
                Message.sender_type == "customer",
                Message.created_at >= since,
            )
            .group_by(func.lower(func.trim(Message.message_text)))
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = result.all()
        return [{"query": r.query, "count": r.cnt} for r in rows]

    async def get_top_fallback_queries(
        self, company_id: uuid.UUID, period_days: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        since = self._since(period_days)
        result = await self.db.execute(
            select(
                func.lower(func.trim(RetrievalLog.query_text)).label("query"),
                func.count().label("cnt"),
            )
            .where(
                RetrievalLog.company_id == company_id,
                RetrievalLog.fallback_triggered == True,  # noqa: E712
                RetrievalLog.created_at >= since,
            )
            .group_by(func.lower(func.trim(RetrievalLog.query_text)))
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = result.all()
        return [{"query": r.query, "count": r.cnt} for r in rows]

    # ------------------------------------------------------------------ #
    # Average handoff resolution time
    # ------------------------------------------------------------------ #

    async def get_avg_handoff_resolution_seconds(
        self, company_id: uuid.UUID, period_days: int
    ) -> Optional[float]:
        since = self._since(period_days)
        result = await self.db.execute(
            select(Handoff.created_at, Handoff.resolved_at)
            .where(
                Handoff.company_id == company_id,
                Handoff.status == "resolved",
                Handoff.resolved_at.isnot(None),
                Handoff.created_at >= since,
            )
        )
        rows = result.all()
        if not rows:
            return None

        total_seconds = 0.0
        count = 0
        for row in rows:
            if row.resolved_at and row.created_at:
                try:
                    created = row.created_at
                    resolved = row.resolved_at
                    # Ensure timezone-aware if needed
                    delta = (resolved - created).total_seconds()
                    total_seconds += delta
                    count += 1
                except Exception:
                    pass

        return total_seconds / count if count > 0 else None
