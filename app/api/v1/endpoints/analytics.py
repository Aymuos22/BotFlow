"""
Analytics endpoints.

Routes
------
GET /companies/{company_id}/analytics/overview
GET /companies/{company_id}/analytics/languages
GET /companies/{company_id}/analytics/leads
GET /companies/{company_id}/analytics/fallbacks
GET /companies/{company_id}/analytics/handoffs
GET /companies/{company_id}/analytics/top-queries

All routes accept ?period_days=N (default 30) to scope the time window.
The company must exist; unknown company_id returns 404.

TODO(auth): Restrict to admin/operator role when JWT is available.
"""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.company_repository import CompanyRepository
from app.schemas.analytics import (
    AnalyticsOverview,
    FallbackAnalytics,
    HandoffAnalytics,
    LeadWarmthAnalytics,
    LanguageAnalytics,
    TopQueriesAnalytics,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["analytics"])


def _analytics_svc(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(analytics_repo=AnalyticsRepository(db))


async def _validate_company(company_id: uuid.UUID, db: AsyncSession) -> None:
    repo = CompanyRepository(db)
    company = await repo.get(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found.",
        )


def _period(period_days: int = Query(30, ge=1, le=365, description="Number of days to look back")) -> int:
    return period_days


# ------------------------------------------------------------------ #
# Overview
# ------------------------------------------------------------------ #


@router.get(
    "/companies/{company_id}/analytics/overview",
    response_model=APIResponse[AnalyticsOverview],
    summary="Company overview analytics",
)
async def analytics_overview(
    company_id: uuid.UUID,
    period_days: int = Depends(_period),
    db: AsyncSession = Depends(get_db),
    svc: AnalyticsService = Depends(_analytics_svc),
) -> Any:
    await _validate_company(company_id, db)
    data = await svc.get_overview(company_id, period_days)
    return APIResponse(success=True, data=data)


# ------------------------------------------------------------------ #
# Languages
# ------------------------------------------------------------------ #


@router.get(
    "/companies/{company_id}/analytics/languages",
    response_model=APIResponse[LanguageAnalytics],
    summary="Language usage breakdown",
)
async def analytics_languages(
    company_id: uuid.UUID,
    period_days: int = Depends(_period),
    db: AsyncSession = Depends(get_db),
    svc: AnalyticsService = Depends(_analytics_svc),
) -> Any:
    await _validate_company(company_id, db)
    data = await svc.get_language_analytics(company_id, period_days)
    return APIResponse(success=True, data=data)


# ------------------------------------------------------------------ #
# Leads
# ------------------------------------------------------------------ #


@router.get(
    "/companies/{company_id}/analytics/leads",
    response_model=APIResponse[LeadWarmthAnalytics],
    summary="Lead warmth trend",
)
async def analytics_leads(
    company_id: uuid.UUID,
    period_days: int = Depends(_period),
    db: AsyncSession = Depends(get_db),
    svc: AnalyticsService = Depends(_analytics_svc),
) -> Any:
    await _validate_company(company_id, db)
    data = await svc.get_lead_warmth_analytics(company_id, period_days)
    return APIResponse(success=True, data=data)


# ------------------------------------------------------------------ #
# Fallbacks
# ------------------------------------------------------------------ #


@router.get(
    "/companies/{company_id}/analytics/fallbacks",
    response_model=APIResponse[FallbackAnalytics],
    summary="Fallback analytics",
)
async def analytics_fallbacks(
    company_id: uuid.UUID,
    period_days: int = Depends(_period),
    db: AsyncSession = Depends(get_db),
    svc: AnalyticsService = Depends(_analytics_svc),
) -> Any:
    await _validate_company(company_id, db)
    data = await svc.get_fallback_analytics(company_id, period_days)
    return APIResponse(success=True, data=data)


# ------------------------------------------------------------------ #
# Handoffs
# ------------------------------------------------------------------ #


@router.get(
    "/companies/{company_id}/analytics/handoffs",
    response_model=APIResponse[HandoffAnalytics],
    summary="Handoff analytics",
)
async def analytics_handoffs(
    company_id: uuid.UUID,
    period_days: int = Depends(_period),
    db: AsyncSession = Depends(get_db),
    svc: AnalyticsService = Depends(_analytics_svc),
) -> Any:
    await _validate_company(company_id, db)
    data = await svc.get_handoff_analytics(company_id, period_days)
    return APIResponse(success=True, data=data)


# ------------------------------------------------------------------ #
# Top queries
# ------------------------------------------------------------------ #


@router.get(
    "/companies/{company_id}/analytics/top-queries",
    response_model=APIResponse[TopQueriesAnalytics],
    summary="Top customer queries and fallback-triggering queries",
)
async def analytics_top_queries(
    company_id: uuid.UUID,
    period_days: int = Depends(_period),
    db: AsyncSession = Depends(get_db),
    svc: AnalyticsService = Depends(_analytics_svc),
) -> Any:
    await _validate_company(company_id, db)
    data = await svc.get_top_queries(company_id, period_days)
    return APIResponse(success=True, data=data)
