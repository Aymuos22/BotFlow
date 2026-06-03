"""
Handoff and conversation-mode management endpoints.

Routes
------
POST /conversations/{conversation_id}/handoff         → trigger handoff
GET  /companies/{company_id}/handoffs                 → list handoffs
POST /handoffs/{handoff_id}/assign                    → assign agent
POST /handoffs/{handoff_id}/resolve                   → resolve handoff
POST /conversations/{conversation_id}/resume-bot      → resume bot mode

TODO(auth): All routes require operator/admin role; add auth decorator when
JWT middleware is available.  See AGENTS.md for future auth scaffold.
"""
import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.core.response import APIResponse
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.handoff_repository import HandoffRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.handoff import (
    HandoffAssignRequest,
    HandoffCreate,
    HandoffRead,
    HandoffResolveRequest,
)
from app.services.handoff_service import HandoffService

router = APIRouter(tags=["handoffs"])


# ------------------------------------------------------------------ #
# Dependency helpers
# ------------------------------------------------------------------ #


def _handoff_svc(db: AsyncSession = Depends(get_db)) -> HandoffService:
    return HandoffService(
        handoff_repo=HandoffRepository(db),
        conversation_repo=ConversationRepository(db),
        message_repo=MessageRepository(db),
        company_config_repo=CompanyConfigRepository(db),
        company_repo=CompanyRepository(db),
    )


# ------------------------------------------------------------------ #
# Request handoff
# ------------------------------------------------------------------ #


@router.post(
    "/conversations/{conversation_id}/handoff",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[HandoffRead],
    summary="Request a human-agent handoff for a conversation",
)
async def request_handoff(
    conversation_id: uuid.UUID,
    body: HandoffCreate,
    db: AsyncSession = Depends(get_db),
    svc: HandoffService = Depends(_handoff_svc),
) -> Any:
    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )

    handoff = await svc.request_handoff(
        company_id=conv.company_id,
        conversation=conv,
        reason=body.reason or "manual_request",
        requested_by=body.requested_by,
    )
    return APIResponse(success=True, data=HandoffRead.model_validate(handoff))


# ------------------------------------------------------------------ #
# List handoffs
# ------------------------------------------------------------------ #


@router.get(
    "/companies/{company_id}/handoffs",
    response_model=APIResponse[List[HandoffRead]],
    summary="List all handoffs for a company",
)
async def list_handoffs(
    company_id: uuid.UUID,
    status_filter: str = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> Any:
    repo = HandoffRepository(db)
    handoffs = await repo.list_by_company(
        company_id, status=status_filter, limit=limit
    )
    return APIResponse(
        success=True,
        data=[HandoffRead.model_validate(h) for h in handoffs],
    )


# ------------------------------------------------------------------ #
# Assign
# ------------------------------------------------------------------ #


@router.post(
    "/handoffs/{handoff_id}/assign",
    response_model=APIResponse[HandoffRead],
    summary="Assign a handoff to an agent",
)
async def assign_handoff(
    handoff_id: uuid.UUID,
    body: HandoffAssignRequest,
    db: AsyncSession = Depends(get_db),
    svc: HandoffService = Depends(_handoff_svc),
) -> Any:
    repo = HandoffRepository(db)
    handoff = await repo.get(handoff_id)
    if handoff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Handoff {handoff_id} not found.",
        )

    try:
        updated = await svc.assign_handoff(handoff, body.agent_id)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return APIResponse(success=True, data=HandoffRead.model_validate(updated))


# ------------------------------------------------------------------ #
# Resolve
# ------------------------------------------------------------------ #


@router.post(
    "/handoffs/{handoff_id}/resolve",
    response_model=APIResponse[HandoffRead],
    summary="Resolve a handoff",
)
async def resolve_handoff(
    handoff_id: uuid.UUID,
    body: HandoffResolveRequest,
    db: AsyncSession = Depends(get_db),
    svc: HandoffService = Depends(_handoff_svc),
) -> Any:
    repo = HandoffRepository(db)
    handoff = await repo.get(handoff_id)
    if handoff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Handoff {handoff_id} not found.",
        )

    resolved = await svc.resolve_handoff(handoff)
    return APIResponse(success=True, data=HandoffRead.model_validate(resolved))


# ------------------------------------------------------------------ #
# Resume bot
# ------------------------------------------------------------------ #


@router.post(
    "/conversations/{conversation_id}/resume-bot",
    response_model=APIResponse[dict],
    summary="Resume bot auto-reply for a conversation",
)
async def resume_bot(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    svc: HandoffService = Depends(_handoff_svc),
) -> Any:
    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )

    await svc.resume_bot(conv)
    return APIResponse(
        success=True,
        data={"conversation_id": str(conversation_id), "current_mode": "bot"},
    )
