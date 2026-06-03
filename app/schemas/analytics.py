"""
Pydantic schemas for the Analytics domain.
"""
import uuid
from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel


class AnalyticsOverview(BaseModel):
    company_id: uuid.UUID
    period_days: int
    total_customer_messages: int
    total_bot_messages: int
    total_fallback_messages: int
    total_handoffs: int
    active_conversations: int
    fallback_rate: float
    handoff_rate: float


class LanguageBreakdown(BaseModel):
    language: str
    count: int
    percentage: float


class LanguageAnalytics(BaseModel):
    company_id: uuid.UUID
    period_days: int
    breakdown: List[LanguageBreakdown]


class LeadWarmthDailyPoint(BaseModel):
    date: date
    hot: int
    warm: int
    cold: int


class LeadWarmthAnalytics(BaseModel):
    company_id: uuid.UUID
    period_days: int
    series: List[LeadWarmthDailyPoint]
    totals: Dict[str, int]


class FallbackAnalytics(BaseModel):
    company_id: uuid.UUID
    period_days: int
    total_fallbacks: int
    fallback_rate: float
    top_fallback_queries: List[Dict[str, object]]


class HandoffAnalytics(BaseModel):
    company_id: uuid.UUID
    period_days: int
    total_handoffs: int
    resolved_count: int
    cancelled_count: int
    pending_count: int
    resolution_rate: float
    avg_resolution_seconds: Optional[float]


class TopQuery(BaseModel):
    query: str
    count: int
    last_seen: Optional[str] = None


class TopQueriesAnalytics(BaseModel):
    company_id: uuid.UUID
    period_days: int
    top_queries: List[TopQuery]
    top_fallback_queries: List[TopQuery]
    language_counts: Dict[str, int]
