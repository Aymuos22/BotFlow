"""
API v1 router.

Aggregates all endpoint routers under the /api/v1 prefix.
Each domain gets its own sub-router for clean separation.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    agents,
    analytics,
    companies,
    documents,
    handoffs,
    health,
    meta,
    onboarding,
    portal,
    portal_inbox,
    products,
    webhooks,
    whatsapp_campaigns,
)

router = APIRouter(prefix="/api/v1")

# Health (also available at root /health via main.py include)
router.include_router(health.router)
router.include_router(meta.router)

# Phase 1 domain endpoints
router.include_router(onboarding.router)
router.include_router(companies.router)

# Phase 2 domain endpoints
router.include_router(documents.router, prefix="/companies")
router.include_router(webhooks.router, prefix="/webhooks")

# Phase 3 domain endpoints
router.include_router(handoffs.router)
router.include_router(agents.router)
router.include_router(analytics.router)

# Phase 4 domain endpoints
router.include_router(products.router)

# Portal (HTTP API for first-party tools)
router.include_router(portal.router)
router.include_router(portal_inbox.router)
router.include_router(whatsapp_campaigns.router)
