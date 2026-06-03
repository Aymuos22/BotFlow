"""Portal APIs for WhatsApp campaigns and follow-up rules."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.portal_auth import require_portal_company_access
from app.core.database import get_db
from app.core.response import APIResponse
from app.schemas.whatsapp_campaign import (
    CampaignActionRequest,
    CampaignCreateRequest,
    CampaignDetail,
    CampaignPreviewResponse,
    CampaignRecipientRead,
    CampaignRead,
    FollowupRuleCreateRequest,
    FollowupRuleRead,
    FollowupRuleUpdateRequest,
    MetaTemplateCreateRequest,
    OutboxJobRead,
    QuickSendRequest,
    QuickSendResponse,
    TemplateRead,
)
from app.services.whatsapp_campaign_service import WhatsAppCampaignService

router = APIRouter(prefix="/portal", tags=["WhatsApp Campaigns"])


@router.post(
    "/companies/{company_id}/campaigns/preview",
    response_model=APIResponse[CampaignPreviewResponse],
)
async def preview_campaign_upload(
    company_id: uuid.UUID,
    file: UploadFile = File(...),
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    return APIResponse(success=True, data=await WhatsAppCampaignService(db).preview_upload(file))


@router.get("/companies/{company_id}/campaigns", response_model=APIResponse[list[CampaignRead]])
async def list_campaigns(
    company_id: uuid.UUID,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    rows = await WhatsAppCampaignService(db).list_campaigns(company_id)
    return APIResponse(success=True, data=[CampaignRead.model_validate(r) for r in rows])


@router.post(
    "/companies/{company_id}/campaigns/quick-send",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[QuickSendResponse],
)
async def quick_send_campaign(
    company_id: uuid.UUID,
    body: QuickSendRequest,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    """
    One-shot bulk send.

    1. Submits your message as a Meta template (or reuses an already-approved one).
    2. Creates a campaign with all provided recipients.
    3. If the template is already APPROVED → starts immediately.
       Otherwise campaign sits in ``pending_template`` status and the outbox
       worker auto-starts it once Meta approves (~minutes to a few hours).
    """
    try:
        campaign, template_status = await WhatsAppCampaignService(db).create_campaign_with_template(
            company_id, body
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if template_status == "APPROVED":
        msg = f"Template already approved. Campaign started — {campaign.queued_count} messages queued."
    else:
        msg = (
            f"Template '{body.template_name}' submitted to Meta for review. "
            f"Campaign will auto-start once approved (usually within minutes to a few hours). "
            f"Campaign ID: {campaign.id}"
        )
    return APIResponse(
        success=True,
        data=QuickSendResponse(
            campaign_id=campaign.id,
            campaign_status=campaign.status,
            template_name=body.template_name,
            template_status=template_status,
            message=msg,
        ),
    )


@router.post(
    "/companies/{company_id}/campaigns",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[CampaignRead],
)
async def create_campaign(
    company_id: uuid.UUID,
    body: CampaignCreateRequest,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    row = await WhatsAppCampaignService(db).create_campaign(company_id, body)
    return APIResponse(success=True, data=CampaignRead.model_validate(row))


@router.get("/companies/{company_id}/campaigns/{campaign_id}", response_model=APIResponse[CampaignDetail])
async def get_campaign(
    company_id: uuid.UUID,
    campaign_id: uuid.UUID,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    try:
        campaign, recipients, counts = await WhatsAppCampaignService(db).campaign_detail(company_id, campaign_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Campaign not found")
    data = CampaignDetail.model_validate(campaign)
    data.recipients = [CampaignRecipientRead.model_validate(r) for r in recipients]
    data.outbox_counts = counts
    return APIResponse(success=True, data=data)


@router.post("/companies/{company_id}/campaigns/{campaign_id}/action", response_model=APIResponse[CampaignRead])
async def campaign_action(
    company_id: uuid.UUID,
    campaign_id: uuid.UUID,
    body: CampaignActionRequest,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await WhatsAppCampaignService(db).campaign_action(company_id, campaign_id, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return APIResponse(success=True, data=CampaignRead.model_validate(row))


@router.get("/companies/{company_id}/outbox-jobs", response_model=APIResponse[list[OutboxJobRead]])
async def list_outbox_jobs(
    company_id: uuid.UUID,
    campaign_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    rows = await WhatsAppCampaignService(db).list_jobs(company_id, campaign_id=campaign_id, status=status_filter)
    return APIResponse(success=True, data=[OutboxJobRead.model_validate(r) for r in rows])


@router.get("/companies/{company_id}/meta-templates", response_model=APIResponse[list[TemplateRead]])
async def list_templates(
    company_id: uuid.UUID,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    rows = await WhatsAppCampaignService(db).list_templates(company_id)
    return APIResponse(success=True, data=[TemplateRead.model_validate(r) for r in rows])


@router.post(
    "/companies/{company_id}/meta-templates",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[dict[str, Any]],
)
async def submit_meta_template(
    company_id: uuid.UUID,
    body: MetaTemplateCreateRequest,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new Meta message template via Business Management API.

    Meta reviews new/edited templates; use GET meta-templates after approval.
    """
    try:
        data = await WhatsAppCampaignService(db).create_meta_template(company_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return APIResponse(success=True, data=data)


@router.get("/companies/{company_id}/followup-rules", response_model=APIResponse[list[FollowupRuleRead]])
async def list_followup_rules(
    company_id: uuid.UUID,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    rows = await WhatsAppCampaignService(db).followups.list_for_company(company_id)
    return APIResponse(success=True, data=[FollowupRuleRead.model_validate(r) for r in rows])


@router.post(
    "/companies/{company_id}/followup-rules",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[FollowupRuleRead],
)
async def create_followup_rule(
    company_id: uuid.UUID,
    body: FollowupRuleCreateRequest,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    row = await WhatsAppCampaignService(db).create_followup_rule(company_id, body)
    return APIResponse(success=True, data=FollowupRuleRead.model_validate(row))


@router.patch("/companies/{company_id}/followup-rules/{rule_id}", response_model=APIResponse[FollowupRuleRead])
async def update_followup_rule(
    company_id: uuid.UUID,
    rule_id: uuid.UUID,
    body: FollowupRuleUpdateRequest,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await WhatsAppCampaignService(db).update_followup_rule(company_id, rule_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return APIResponse(success=True, data=FollowupRuleRead.model_validate(row))


@router.delete("/companies/{company_id}/followup-rules/{rule_id}", response_model=APIResponse[dict])
async def delete_followup_rule(
    company_id: uuid.UUID,
    rule_id: uuid.UUID,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
):
    try:
        await WhatsAppCampaignService(db).delete_followup_rule(company_id, rule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return APIResponse(success=True, data={"deleted": True})
