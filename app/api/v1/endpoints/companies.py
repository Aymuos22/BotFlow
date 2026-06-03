"""
Company management API endpoints.

GET  /api/v1/companies/{company_id}/readiness
POST /api/v1/companies/{company_id}/activate
GET  /api/v1/companies/{company_id}/config
PUT  /api/v1/companies/{company_id}/config
PATCH /api/v1/companies/{company_id}/status
POST /api/v1/companies/{company_id}/weaviate/ensure-collection
"""
import logging
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.response import APIResponse
from app.integrations.weaviate.client import WeaviateClient, get_weaviate_client
from app.repositories.company_channel_repository import CompanyChannelRepository
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.onboarding_status_repository import OnboardingStatusRepository
from app.schemas.company import CompanyRead, CompanyStatusUpdate
from app.schemas.company_config import CompanyConfigRead, CompanyConfigUpdate
from app.schemas.onboarding import ActivationResponse, ReadinessResponse
from app.schemas.whatsapp_admin import (
    WhatsAppChangeNumberRequest,
    WhatsAppChangeNumberResponse,
)
from app.services.company_service import CompanyService
from app.services.onboarding_service import OnboardingService
from app.utils.naming import rotate_twilio_channel_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/companies", tags=["Companies"])


def _get_company_service(db: AsyncSession = Depends(get_db)) -> CompanyService:
    return CompanyService(company_repo=CompanyRepository(db))


def _get_onboarding_service(
    db: AsyncSession = Depends(get_db),
    weaviate_client: WeaviateClient = Depends(get_weaviate_client),
) -> OnboardingService:
    return OnboardingService(
        company_repo=CompanyRepository(db),
        config_repo=CompanyConfigRepository(db),
        channel_repo=CompanyChannelRepository(db),
        onboarding_repo=OnboardingStatusRepository(db),
        weaviate_client=weaviate_client,
    )


@router.get(
    "/{company_id}/readiness",
    response_model=APIResponse[ReadinessResponse],
    summary="Get onboarding readiness status",
)
async def get_readiness(
    company_id: UUID,
    service: OnboardingService = Depends(_get_onboarding_service),
) -> APIResponse[ReadinessResponse]:
    """Return current onboarding readiness and blocking reasons."""
    readiness = await service.get_readiness(company_id)
    return APIResponse(success=True, data=readiness)


@router.post(
    "/{company_id}/activate",
    response_model=APIResponse[ActivationResponse],
    summary="Activate a fully onboarded company",
)
async def activate_company(
    company_id: UUID,
    service: OnboardingService = Depends(_get_onboarding_service),
) -> APIResponse[ActivationResponse]:
    """
    Activate a company.

    Requires config_saved, weaviate_ready, and Twilio credentials on CompanyConfig.
    """
    result = await service.activate_company(company_id)
    return APIResponse(success=True, data=result)


@router.get(
    "/{company_id}/config",
    response_model=APIResponse[CompanyConfigRead],
    summary="Get company configuration",
)
async def get_config(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[CompanyConfigRead]:
    """Return the runtime configuration for a company."""
    config_repo = CompanyConfigRepository(db)
    company_repo = CompanyRepository(db)

    company = await company_repo.get(company_id)
    if not company:
        raise NotFoundError("Company", str(company_id))

    config = await config_repo.get_by_company(company_id)
    if not config:
        raise NotFoundError("CompanyConfig", str(company_id))

    return APIResponse(success=True, data=CompanyConfigRead.model_validate(config))


@router.put(
    "/{company_id}/config",
    response_model=APIResponse[CompanyConfigRead],
    summary="Update company configuration",
)
async def update_config(
    company_id: UUID,
    payload: CompanyConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[CompanyConfigRead]:
    """
    Update mutable fields of a company's runtime configuration.

    Language settings, prompts, and JSON config blobs can be updated.
    Integration identifiers (weaviate_collection) are immutable after creation.
    """
    config_repo = CompanyConfigRepository(db)
    company_repo = CompanyRepository(db)

    company = await company_repo.get(company_id)
    if not company:
        raise NotFoundError("Company", str(company_id))

    config = await config_repo.get_by_company(company_id)
    if not config:
        raise NotFoundError("CompanyConfig", str(company_id))

    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        return APIResponse(
            success=True,
            data=CompanyConfigRead.model_validate(config),
            message="No fields to update.",
        )

    merged_default = update_data.get("default_language", config.default_language)
    merged_supported = update_data.get(
        "supported_languages", list(config.supported_languages or [])
    )
    if merged_default not in merged_supported:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="default_language must be one of supported_languages",
        )

    updated = await config_repo.update(config, update_data)
    logger.info(
        "Company config updated",
        extra={"company_id": str(company_id), "fields": list(update_data.keys())},
    )
    return APIResponse(
        success=True,
        data=CompanyConfigRead.model_validate(updated),
        message="Configuration updated.",
    )


@router.post(
    "/{company_id}/whatsapp/change-number",
    response_model=APIResponse[WhatsAppChangeNumberResponse],
    summary="Change company's WhatsApp channel phone number",
)
async def change_whatsapp_number(
    company_id: UUID,
    payload: WhatsAppChangeNumberRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Change the primary WhatsApp phone number for a company (channel row).

    Rotates the internal channel key. Configure Twilio in the portal if your
    sender number or Twilio setup changes.
    """
    company_repo = CompanyRepository(db)
    config_repo = CompanyConfigRepository(db)
    channel_repo = CompanyChannelRepository(db)

    company = await company_repo.get(company_id)
    if not company:
        raise NotFoundError("Company", str(company_id))

    cfg = await config_repo.get_by_company(company_id)
    if not cfg:
        raise NotFoundError("CompanyConfig", str(company_id))

    primary = await channel_repo.get_primary_by_company(company_id, "whatsapp")
    if not primary:
        raise NotFoundError("CompanyChannel", f"primary whatsapp for {company_id}")

    new_phone = payload.phone_number.strip()
    existing_channel = await channel_repo.get_by_phone_number(new_phone)
    if existing_channel and existing_channel.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"WhatsApp phone number '{new_phone}' is already registered to another company.",
        )

    old_phone = primary.phone_number
    old_key = primary.session_name

    new_key = rotate_twilio_channel_key(company_id, suffix="numchg")

    await channel_repo.update(
        primary,
        {"phone_number": new_phone, "session_name": new_key, "status": "pending"},
    )

    data = WhatsAppChangeNumberResponse(
        company_id=str(company_id),
        old_phone_number=old_phone,
        new_phone_number=new_phone,
        old_channel_key=old_key,
        new_channel_key=new_key,
    )
    return APIResponse(
        success=True,
        data=data,
        message="WhatsApp channel number updated.",
    )


@router.patch(
    "/{company_id}/status",
    response_model=APIResponse[CompanyRead],
    summary="Update company lifecycle status",
)
async def update_status(
    company_id: UUID,
    payload: CompanyStatusUpdate,
    service: CompanyService = Depends(_get_company_service),
) -> APIResponse[CompanyRead]:
    """
    Update a company's lifecycle status (e.g. active → inactive).

    Valid transitions: draft | active | inactive | suspended
    """
    updated = await service.update_company_status(company_id, payload)
    return APIResponse(
        success=True,
        data=updated,
        message=f"Company status updated to '{payload.status}'.",
    )


@router.post(
    "/{company_id}/weaviate/ensure-collection",
    response_model=APIResponse[Dict[str, Any]],
    summary="Create Weaviate collection if it does not exist",
)
async def ensure_weaviate_collection(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    weaviate_client: WeaviateClient = Depends(get_weaviate_client),
) -> Any:
    """
    Idempotent: creates the company's Weaviate vector collection when it is
    missing.  Also marks ``onboarding_status.weaviate_ready = True``
    so the readiness gate is satisfied.
    """
    config_repo = CompanyConfigRepository(db)
    company_repo = CompanyRepository(db)
    onboarding_repo = OnboardingStatusRepository(db)

    company = await company_repo.get(company_id)
    if not company:
        raise NotFoundError("Company", str(company_id))

    config = await config_repo.get_by_company(company_id)
    if not config:
        raise NotFoundError("CompanyConfig", str(company_id))

    collection = config.weaviate_collection
    already_existed = False
    created = False
    try:
        already_existed = await weaviate_client.collection_exists(collection)
        if not already_existed:
            await weaviate_client.create_collection(collection)
            created = True
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Weaviate error: {exc}",
        )

    onboarding = await onboarding_repo.get_by_company(company_id)
    if onboarding and not onboarding.weaviate_ready:
        await onboarding_repo.update(onboarding, {"weaviate_ready": True})
        await db.commit()

    # Avoid LogRecord conflict: ``created`` is reserved on logging records.
    logger.info(
        "Weaviate collection ensured",
        extra={
            "company_id": str(company_id),
            "collection": collection,
            "collection_created": created,
            "already_existed": already_existed,
        },
    )
    return APIResponse(
        success=True,
        data={
            "collection_name": collection,
            "created": created,
            "already_existed": already_existed,
        },
        message="Collection created." if created else "Collection already exists.",
    )
