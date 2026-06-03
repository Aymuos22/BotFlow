"""
Agent messaging endpoints.

Routes
------
GET  /agents/{agent_id}/conversations
    → List conversations assigned to this agent (via handoffs).

POST /conversations/{conversation_id}/messages/agent
    → Agent sends a message; stored in DB and delivered via the company's WhatsApp provider.

TODO(auth): Endpoints should verify that the requesting user matches
{agent_id} once JWT middleware is available.  A role-note comment is
included where the check would go.
"""
import logging
import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import APIResponse
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.handoff_repository import HandoffRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.conversation import ConversationRead, MessageRead
from app.schemas.handoff import AgentMessageRequest
from app.services.conversation_service import ConversationService
from app.services.whatsapp_outbound import (
    company_can_send_whatsapp,
    send_company_whatsapp_text_best_effort,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agents"])


def _conv_svc(db: AsyncSession = Depends(get_db)) -> ConversationService:
    return ConversationService(
        conversation_repo=ConversationRepository(db),
        message_repo=MessageRepository(db),
    )


# ------------------------------------------------------------------ #
# List agent conversations
# ------------------------------------------------------------------ #


@router.get(
    "/agents/{agent_id}/conversations",
    response_model=APIResponse[List[ConversationRead]],
    summary="List conversations assigned to a specific agent",
)
async def get_agent_conversations(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    # TODO(auth): verify requesting user == agent_id
    handoff_repo = HandoffRepository(db)
    handoffs = await handoff_repo.list_by_agent(agent_id)

    if not handoffs:
        return APIResponse(success=True, data=[])

    conv_repo = ConversationRepository(db)
    convs = []
    seen_ids: set = set()
    for h in handoffs:
        if h.conversation_id not in seen_ids:
            conv = await conv_repo.get(h.conversation_id)
            if conv:
                convs.append(conv)
                seen_ids.add(h.conversation_id)

    return APIResponse(
        success=True,
        data=[ConversationRead.model_validate(c) for c in convs],
    )


# ------------------------------------------------------------------ #
# Agent send message
# ------------------------------------------------------------------ #


@router.post(
    "/conversations/{conversation_id}/messages/agent",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[MessageRead],
    summary="Send a message as a human agent",
)
async def agent_send_message(
    conversation_id: uuid.UUID,
    body: AgentMessageRequest,
    db: AsyncSession = Depends(get_db),
    conv_svc: ConversationService = Depends(_conv_svc),
) -> Any:
    # TODO(auth): verify body.agent_id matches authenticated user

    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )

    msg = await conv_svc.append_message(
        conversation_id=conv.id,
        company_id=conv.company_id,
        sender_type="agent",
        message_text=body.message_text,
        response_type="manual",
    )

    config_repo = CompanyConfigRepository(db)
    config = await config_repo.get_by_company(conv.company_id)

    if config and company_can_send_whatsapp(config):
        await send_company_whatsapp_text_best_effort(
            config=config,
            to_number=conv.customer_phone,
            text=body.message_text,
            log_context={"conv": str(conv.id)},
        )

    return APIResponse(success=True, data=MessageRead.model_validate(msg))
