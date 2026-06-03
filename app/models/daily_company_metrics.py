"""
DailyCompanyMetrics ORM model.

Pre-aggregated daily counters per company.

Populated by ``MetricsAggregationService.aggregate_for_date(company_id, date)``.
Analytics APIs can query this table for historical efficiency, and fall back
to live SQL for today's data.

Unique constraint: (company_id, metric_date) – one row per company per day.
"""
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class DailyCompanyMetrics(Base, TimestampMixin):
    """
    One daily snapshot of aggregated activity for a company.
    """

    __tablename__ = "daily_company_metrics"

    __table_args__ = (
        UniqueConstraint(
            "company_id", "metric_date", name="uq_daily_metrics_company_date"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True, comment="Calendar date (UTC) this row covers"
    )

    # ------------------------------------------------------------------ #
    # Message counters
    # ------------------------------------------------------------------ #
    total_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bot_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ------------------------------------------------------------------ #
    # Handoff counters
    # ------------------------------------------------------------------ #
    handoff_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ------------------------------------------------------------------ #
    # Conversation counters
    # ------------------------------------------------------------------ #
    active_conversations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # ------------------------------------------------------------------ #
    # Performance
    # ------------------------------------------------------------------ #
    avg_bot_response_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Average milliseconds from customer message to bot reply",
    )

    # ------------------------------------------------------------------ #
    # Language breakdown
    # ------------------------------------------------------------------ #
    english_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hindi_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hinglish_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"<DailyCompanyMetrics company={self.company_id} "
            f"date={self.metric_date} messages={self.total_messages}>"
        )
