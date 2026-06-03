"""
Portal API — per-company WhatsApp inbox (threads, lead labels, agent replies).

All routes require the same auth as other portal company routes
(``require_portal_company_access``).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.portal_auth import require_portal_company_access
from app.core.database import get_db
from app.core.response import APIResponse
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.conversation import (
    InboxConversationItem,
    MessageRead,
    PortalInboxPatchRequest,
    PortalInboxSendRequest,
    SheetPreviewRow,
)
from app.services.conversation_service import ConversationService
from app.services.google_sheets_sync_service import GoogleSheetsSyncService
from app.services.whatsapp_outbound import (
    company_can_send_whatsapp,
    send_company_whatsapp_text_best_effort,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal", tags=["Portal Inbox"])


def _inbox_lead_warmth_ok(v: Optional[str]) -> bool:
    if v is None:
        return True
    return v in ("hot", "warm", "cold")


@router.get(
    "/companies/{company_id}/inbox/conversations",
    response_model=APIResponse[List[InboxConversationItem]],
    summary="List WhatsApp conversation threads (inbox)",
)
async def portal_inbox_list_conversations(
    company_id: uuid.UUID,
    inquiry: Optional[str] = Query(
        None, description="Filter: open | complete (omit for all)"
    ),
    limit: int = Query(40, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000),
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    if inquiry is not None and inquiry not in ("open", "complete"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="inquiry must be 'open' or 'complete'",
        )
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)
    rows = await conv_repo.list_for_inbox(
        company_id, limit=limit, offset=offset, inquiry_filter=inquiry
    )
    ids = [c.id for c in rows]
    previews = await msg_repo.last_message_text_by_conversation_ids(company_id, ids)
    data: list[InboxConversationItem] = []
    for c in rows:
        base = {
            "id": c.id,
            "company_id": c.company_id,
            "customer_phone": c.customer_phone,
            "current_mode": c.current_mode,
            "status": c.status,
            "detected_language": c.detected_language,
            "assigned_agent_id": c.assigned_agent_id,
            "last_message_at": c.last_message_at,
            "lead_warmth": c.lead_warmth,
            "lead_warmth_locked": bool(
                getattr(c, "lead_warmth_locked", False)
            ),
            "inquiry_complete": bool(
                getattr(c, "inquiry_complete", False)
            ),
            "inquiry_completed_at": getattr(c, "inquiry_completed_at", None),
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "last_message_preview": previews.get(c.id),
        }
        data.append(InboxConversationItem.model_validate(base))
    return APIResponse(success=True, data=data)


@router.get(
    "/companies/{company_id}/sheet-preview",
    response_model=APIResponse[List[SheetPreviewRow]],
    summary="Preview the exact Leads rows synced to Google Sheets",
)
async def portal_sheet_preview(
    company_id: uuid.UUID,
    inquiry: Optional[str] = Query(
        None, description="Filter: open | complete (omit for all)"
    ),
    limit: int = Query(200, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000),
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    if inquiry is not None and inquiry not in ("open", "complete"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="inquiry must be 'open' or 'complete'",
        )
    rows = await GoogleSheetsSyncService(db).preview_rows(
        company_id,
        limit=limit,
        offset=offset,
        inquiry_filter=inquiry,
    )
    return APIResponse(
        success=True,
        data=[SheetPreviewRow.model_validate(row) for row in rows],
    )


@router.get(
    "/companies/{company_id}/inbox/conversations/{conversation_id}/messages",
    response_model=APIResponse[List[MessageRead]],
    summary="Messages in a thread (oldest to newest, capped)",
)
async def portal_inbox_get_messages(
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    limit: int = Query(200, ge=1, le=500),
    since: Optional[str] = Query(
        None,
        description=(
            "ISO-8601 UTC timestamp. When set, returns only messages strictly "
            "after this time (for incremental polling). Ignored when fetching "
            "the full thread."
        ),
    ),
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get(conversation_id)
    if not conv or conv.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    since_dt: Optional[datetime] = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 'since' timestamp; use ISO-8601 format e.g. 2026-05-01T12:00:00Z",
            )

    msg_repo = MessageRepository(db)
    if since_dt is not None:
        rows = await msg_repo.list_messages_since(conversation_id, since_dt)
    else:
        rows = await msg_repo.list_chronological_for_conversation(
            conversation_id, limit=limit
        )
    return APIResponse(
        success=True, data=[MessageRead.model_validate(m) for m in rows]
    )


@router.get(
    "/companies/{company_id}/inbox/conversations/{conversation_id}/poll",
    response_model=APIResponse[dict],
    summary="Lightweight poll: returns last_message_at and unread count since a timestamp",
)
async def portal_inbox_poll_conversation(
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    since: Optional[str] = Query(
        None,
        description="ISO-8601 UTC timestamp of the last message the UI has loaded",
    ),
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get(conversation_id)
    if not conv or conv.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    since_dt: Optional[datetime] = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 'since' timestamp.",
            )

    new_count = 0
    if since_dt is not None:
        msg_repo = MessageRepository(db)
        rows = await msg_repo.list_messages_since(conversation_id, since_dt)
        new_count = len(rows)

    return APIResponse(
        success=True,
        data={
            "conversation_id": str(conversation_id),
            "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
            "new_messages_since": new_count,
            "has_new_messages": new_count > 0,
        },
    )


@router.post(
    "/companies/{company_id}/inbox/conversations/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[MessageRead],
    summary="Send WhatsApp to customer (agent) from the inbox",
)
async def portal_inbox_send_message(
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: PortalInboxSendRequest,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get(conversation_id)
    if not conv or conv.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    conv_svc = ConversationService(
        conversation_repo=conv_repo, message_repo=MessageRepository(db)
    )
    msg = await conv_svc.append_message(
        conversation_id=conv.id,
        company_id=company_id,
        sender_type="agent",
        message_text=body.message_text,
        response_type="manual",
    )
    # Human is engaging — keep bot from auto-replying.
    if conv.current_mode != "agent":
        await conv_repo.update(conv, {"current_mode": "agent"})
        conv.current_mode = "agent"

    config_repo = CompanyConfigRepository(db)
    config = await config_repo.get_by_company(company_id)
    if config and company_can_send_whatsapp(config):
        await send_company_whatsapp_text_best_effort(
            config=config,
            to_number=conv.customer_phone,
            text=body.message_text,
            log_context={"portal_inbox": str(conversation_id)},
        )
    return APIResponse(success=True, data=MessageRead.model_validate(msg))


@router.patch(
    "/companies/{company_id}/inbox/conversations/{conversation_id}",
    response_model=APIResponse[InboxConversationItem],
    summary="Set lead temperature and/or mark inquiry complete",
)
async def portal_inbox_patch_conversation(
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: PortalInboxPatchRequest,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get(conversation_id)
    if not conv or conv.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    patch = body.model_dump(exclude_unset=True)
    updates: dict = {}
    if "lead_warmth" in patch:
        v = patch["lead_warmth"]
        if v is not None and not _inbox_lead_warmth_ok(v):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="lead_warmth must be 'hot', 'warm', 'cold', or null",
            )
        updates["lead_warmth"] = v
        # Manual set/clear stops AI from overwriting until set again.
        updates["lead_warmth_locked"] = v is not None
    if "inquiry_complete" in patch:
        ic = patch["inquiry_complete"]
        updates["inquiry_complete"] = ic
        if ic:
            updates["inquiry_completed_at"] = datetime.now(timezone.utc)
        else:
            updates["inquiry_completed_at"] = None

    if updates:
        await conv_repo.update(conv, updates)
        for k, v in updates.items():
            setattr(conv, k, v)
        await GoogleSheetsSyncService(db).sync_conversation_best_effort(conv)

    msg_repo = MessageRepository(db)
    prev = await msg_repo.last_message_text_by_conversation_ids(company_id, [conv.id])
    base = {
        "id": conv.id,
        "company_id": conv.company_id,
        "customer_phone": conv.customer_phone,
        "current_mode": conv.current_mode,
        "status": conv.status,
        "detected_language": conv.detected_language,
        "assigned_agent_id": conv.assigned_agent_id,
        "last_message_at": conv.last_message_at,
        "lead_warmth": conv.lead_warmth,
        "lead_warmth_locked": bool(
            getattr(conv, "lead_warmth_locked", False)
        ),
        "inquiry_complete": bool(getattr(conv, "inquiry_complete", False)),
        "inquiry_completed_at": getattr(conv, "inquiry_completed_at", None),
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "last_message_preview": prev.get(conv.id),
    }
    return APIResponse(success=True, data=InboxConversationItem.model_validate(base))
