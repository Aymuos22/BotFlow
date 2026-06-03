"""
ConversationService – manages WhatsApp conversation threads.

Responsibilities
----------------
- create_or_get_conversation: idempotently return the active conversation
  for a (company, phone) pair, creating one if it doesn't exist.
- append_message: store a message and update last_message_at on the conversation.
- refresh_reply_language_after_customer_message: update stored language when
  the customer message is a strong language signal (short/ambiguous keeps prior).
- update_last_message_at: touch the conversation timestamp.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.services.google_sheets_sync_service import GoogleSheetsSyncService
from app.services.language_service import detect_language, is_strong_language_signal

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
    ) -> None:
        self._conv_repo = conversation_repo
        self._msg_repo = message_repo

    async def create_or_get_conversation(
        self, company_id: uuid.UUID, customer_phone: str
    ) -> Conversation:
        """
        Return the active conversation for (company_id, customer_phone).

        Creates a new ``active`` conversation if none exists.  A partial unique
        index (company_id, customer_phone) WHERE status='active' prevents
        duplicate conversations from concurrent webhook events — if INSERT
        races and hits the constraint we fall back to SELECT.
        """
        existing = await self._conv_repo.get_by_company_and_phone(
            company_id, customer_phone
        )
        if existing is not None:
            return existing

        try:
            conv = await self._conv_repo.create(
                {
                    "company_id": company_id,
                    "customer_phone": customer_phone,
                    "current_mode": "bot",
                    "status": "active",
                }
            )
        except IntegrityError:
            # Concurrent request already created the conversation — roll back
            # the failed insert and fetch the one that won the race.
            await self._conv_repo.db.rollback()
            existing = await self._conv_repo.get_by_company_and_phone(
                company_id, customer_phone
            )
            if existing is not None:
                return existing
            raise

        logger.info(
            "New conversation created",
            extra={
                "conversation_id": str(conv.id),
                "company_id": str(company_id),
                "customer_phone": customer_phone,
            },
        )
        return conv

    async def append_message(
        self,
        conversation_id: uuid.UUID,
        company_id: uuid.UUID,
        sender_type: str,
        message_text: str,
        normalized_text: Optional[str] = None,
        language: Optional[str] = None,
        response_type: Optional[str] = None,
        external_message_id: Optional[str] = None,
    ) -> Message:
        """
        Persist a message and touch conversation.last_message_at.

        Args:
            conversation_id: Owning conversation.
            company_id:      Owning company (for direct lookup by company).
            sender_type:     ``customer`` | ``bot`` | ``agent`` | ``system``.
            message_text:    Raw message text.
            normalized_text: Optional pre-normalized query text.
            language:        Detected language of this message.
            response_type:   ``rag`` | ``fallback`` | ``handoff`` | ``manual``.
            external_message_id: External id for deduplication (e.g. Twilio MessageSid).

        Returns:
            Newly created Message.
        """
        msg = await self._msg_repo.create(
            {
                "conversation_id": conversation_id,
                "company_id": company_id,
                "sender_type": sender_type,
                "message_text": message_text,
                "normalized_text": normalized_text,
                "language": language,
                "response_type": response_type,
                "external_message_id": external_message_id,
            }
        )

        # Touch last_message_at on the conversation using a direct SQL update
        await self._conv_repo.touch_last_message_at(
            conversation_id, datetime.now(timezone.utc)
        )
        conversation = await self._conv_repo.get(conversation_id)
        await GoogleSheetsSyncService(self._msg_repo.db).sync_message_best_effort(
            message=msg,
            conversation=conversation,
        )

        return msg

    async def refresh_reply_language_after_customer_message(
        self, conversation: Conversation, message_text: str
    ) -> None:
        """
        Update ``conversation.detected_language`` to the last *decisive* user
        language. Weak signals (e.g. "ok", "thanks") do not overwrite the
        stored value so replies stay in the language they were using.
        """
        detected = detect_language(message_text)
        if not is_strong_language_signal(message_text, detected):
            return
        await self._conv_repo.update(
            conversation, {"detected_language": detected}
        )
        conversation.detected_language = detected
