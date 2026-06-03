"""
HandoffService – orchestrates human escalation within a conversation.

Trigger scenarios
-----------------
1. **Keyword-triggered**: Customer message contains a human-request phrase.
2. **Low-confidence-triggered**: RAG score is below a company-configured
   threshold AND ``handoff_on_low_confidence`` is enabled in config.

State transitions
-----------------
- ``request_handoff``:
    - If an active handoff already exists for the conversation → return it
      (idempotent).
    - Otherwise create a new ``Handoff`` (status=``requested``) and set
      ``conversation.current_mode = "agent"``.

- ``assign_handoff(handoff, agent_id)``:
    - Status must be ``requested`` or ``assigned`` (re-assignment allowed).
    - Sets ``status = "assigned"`` and ``assigned_agent_id``.

- ``resolve_handoff(handoff)``:
    - Sets ``status = "resolved"`` and ``resolved_at = now()``.
    - Does NOT resume the bot automatically – operator must call resume_bot.

- ``resume_bot(conversation)``:
    - Sets ``conversation.current_mode = "bot"``.
    - The next customer message will trigger RAG again.

Design note
-----------
Routing a ``ValidationError`` from assigning a resolved handoff keeps the
API layer thin – exceptions are mapped to HTTP status codes in the router.
"""
import logging
import uuid
from datetime import datetime, timezone

from app.core.exceptions import ValidationError
from app.models.conversation import Conversation
from app.models.handoff import Handoff
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.handoff_repository import HandoffRepository
from app.repositories.message_repository import MessageRepository
from app.services.whatsapp_outbound import (
    company_can_send_whatsapp,
    send_company_whatsapp_text_best_effort,
)

logger = logging.getLogger(__name__)

# Statuses that indicate an active handoff (not yet closed)
_ACTIVE_STATUSES = {"requested", "assigned", "active"}


class HandoffService:
    def __init__(
        self,
        handoff_repo: HandoffRepository,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        company_config_repo: CompanyConfigRepository,
        company_repo: CompanyRepository,
    ) -> None:
        self._handoff_repo = handoff_repo
        self._conv_repo = conversation_repo
        self._msg_repo = message_repo
        self._config_repo = company_config_repo
        self._company_repo = company_repo

    # ------------------------------------------------------------------ #
    # Request
    # ------------------------------------------------------------------ #

    async def request_handoff(
        self,
        company_id: uuid.UUID,
        conversation: Conversation,
        reason: str,
        requested_by: str = "customer",
    ) -> Handoff:
        """
        Trigger a handoff for *conversation*, idempotently.

        Returns an existing active handoff if one already exists,
        or creates a new one and switches the conversation to agent mode.
        """
        existing = await self._handoff_repo.get_active_for_conversation(
            conversation.id
        )
        if existing is not None:
            logger.info(
                "Handoff already active; returning existing",
                extra={"handoff_id": str(existing.id), "conv": str(conversation.id)},
            )
            return existing

        handoff = await self._handoff_repo.create(
            {
                "company_id": company_id,
                "conversation_id": conversation.id,
                "requested_by": requested_by,
                "reason": reason,
                "status": "requested",
            }
        )

        # Switch conversation to agent mode
        await self._conv_repo.update(conversation, {"current_mode": "agent"})

        logger.info(
            "Handoff created",
            extra={
                "handoff_id": str(handoff.id),
                "company_id": str(company_id),
                "reason": reason,
            },
        )
        await self._notify_staff_whatsapp_new_handoff(
            company_id=company_id,
            conversation=conversation,
            handoff=handoff,
            reason=reason,
        )
        return handoff

    async def _notify_staff_whatsapp_new_handoff(
        self,
        *,
        company_id: uuid.UUID,
        conversation: Conversation,
        handoff: Handoff,
        reason: str,
    ) -> None:
        """
        Best-effort WhatsApp alert to the company's supervisor number.

        Never raises: failures are logged only; handoff creation already succeeded.
        """
        try:
            cfg = await self._config_repo.get_by_company(company_id)
            if not cfg:
                return
            to_raw = (getattr(cfg, "handoff_staff_notify_whatsapp", None) or "").strip()
            if not to_raw:
                return

            if not company_can_send_whatsapp(cfg):
                logger.warning(
                    "Handoff staff WhatsApp notify skipped: WhatsApp provider not configured",
                    extra={"company_id": str(company_id)},
                )
                return

            company = await self._company_repo.get(company_id)
            label = company.display_name if company else str(company_id)
            customer = getattr(conversation, "customer_phone", None) or "unknown"
            body = (
                f"[{label}] Customer wants to talk to a human agent.\n"
                f"Customer WhatsApp: {customer}\n"
                f"Details: {reason}\n"
                f"Conversation: {conversation.id}\n"
                f"Handoff: {handoff.id}"
            )

            await send_company_whatsapp_text_best_effort(
                config=cfg,
                to_number=to_raw,
                text=body,
                log_context={
                    "company_id": str(company_id),
                    "conversation_id": str(conversation.id),
                },
            )
        except Exception:
            logger.exception(
                "Failed to send handoff staff WhatsApp notification (handoff still created)",
                extra={
                    "company_id": str(company_id),
                    "conversation_id": str(conversation.id),
                },
            )

    # ------------------------------------------------------------------ #
    # Assign
    # ------------------------------------------------------------------ #

    async def assign_handoff(
        self, handoff: Handoff, agent_id: str
    ) -> Handoff:
        """
        Assign *agent_id* to the handoff.

        Raises ``ValidationError`` if the handoff is already resolved/cancelled.
        """
        if handoff.status in ("resolved", "cancelled"):
            raise ValidationError(
                f"Cannot assign a handoff with status '{handoff.status}'."
            )

        return await self._handoff_repo.update(
            handoff,
            {
                "assigned_agent_id": agent_id,
                "status": "assigned",
            },
        )

    # ------------------------------------------------------------------ #
    # Resolve
    # ------------------------------------------------------------------ #

    async def resolve_handoff(self, handoff: Handoff) -> Handoff:
        """
        Mark the handoff as resolved.

        Does NOT automatically resume the bot.
        """
        return await self._handoff_repo.update(
            handoff,
            {
                "status": "resolved",
                "resolved_at": datetime.now(timezone.utc),
            },
        )

    # ------------------------------------------------------------------ #
    # Resume bot
    # ------------------------------------------------------------------ #

    async def resume_bot(self, conversation: Conversation) -> Conversation:
        """
        Switch *conversation* back to bot mode.

        Future incoming messages will again trigger RAG.
        """
        return await self._conv_repo.update(
            conversation, {"current_mode": "bot"}
        )
