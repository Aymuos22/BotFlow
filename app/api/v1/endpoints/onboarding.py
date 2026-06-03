"""
Onboarding API endpoints.

POST /api/v1/onboarding/company/full  – one-click company onboarding
"""
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.portal_auth import verify_onboarding_admin
from app.core.database import get_db
from app.core.response import APIResponse
from app.integrations.weaviate.client import WeaviateClient, get_weaviate_client
from app.repositories.company_channel_repository import CompanyChannelRepository
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.onboarding_status_repository import OnboardingStatusRepository
from app.schemas.onboarding import FullOnboardingRequest, OnboardingSummary
from app.services.onboarding_service import OnboardingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


def _get_onboarding_service(
    db: AsyncSession = Depends(get_db),
    weaviate_client: WeaviateClient = Depends(get_weaviate_client),
) -> OnboardingService:
    """Dependency factory for OnboardingService."""
    return OnboardingService(
        company_repo=CompanyRepository(db),
        config_repo=CompanyConfigRepository(db),
        channel_repo=CompanyChannelRepository(db),
        onboarding_repo=OnboardingStatusRepository(db),
        weaviate_client=weaviate_client,
    )


@router.post(
    "/company/full",
    response_model=APIResponse[OnboardingSummary],
    status_code=status.HTTP_201_CREATED,
    summary="Full one-click company onboarding",
    description=(
        "Creates company, config, channel, and Weaviate collection "
        "in a single call. Weaviate failures are non-fatal; "
        "the onboarding_status flags reflect the outcome."
    ),
)
async def full_onboard(
    payload: FullOnboardingRequest,
    _: None = Depends(verify_onboarding_admin),
    service: OnboardingService = Depends(_get_onboarding_service),
) -> APIResponse[OnboardingSummary]:
    """
    Execute full company onboarding.

    Returns an OnboardingSummary with the created resources and
    next_steps for the admin to follow.
    """
    summary = await service.full_onboard(payload)
    return APIResponse(
        success=True,
        message="Company onboarded successfully.",
        data=summary,
    )
