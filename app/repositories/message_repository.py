"""
Repository for the Message model.
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Message, db)

    # Tiebreaker: when two messages share the same created_at (customer msg +
    # bot reply saved in the same instant) put customer before bot/agent.
    # Used in ASC-ordered queries; for DESC + reverse queries the values are
    # inverted so that after reversal customer still precedes bot/agent.
    _SENDER_ORDER_ASC = case(
        (Message.sender_type == "customer", 0),
        else_=1,
    )
    _SENDER_ORDER_DESC = case(
        (Message.sender_type == "customer", 1),
        else_=0,
    )

    async def list_by_conversation(
        self, conversation_id: uuid.UUID, limit: int = 50
    ) -> List[Message]:
        """Return up to *limit* messages oldest-first (legacy ordering)."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), self._SENDER_ORDER_ASC.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_chronological_for_conversation(
        self, conversation_id: uuid.UUID, limit: int = 200
    ) -> List[Message]:
        """Return the most recent *limit* messages in chronological order (oldest of those first)."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at), self._SENDER_ORDER_DESC.asc())
            .limit(min(limit, 500))
        )
        rows = list(result.scalars().all())
        return list(reversed(rows))

    async def list_recent_for_conversation(
        self, conversation_id: uuid.UUID, limit: int = 30
    ) -> List[Message]:
        """Return the *limit* most recent messages in chronological order."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at), self._SENDER_ORDER_DESC.asc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        return list(reversed(rows))

    async def last_message_text_by_conversation_ids(
        self, company_id: uuid.UUID, conversation_ids: List[uuid.UUID]
    ) -> Dict[uuid.UUID, str]:
        """
        For each conversation id, the text of the latest message in that thread.
        """
        if not conversation_ids:
            return {}
        sub = (
            select(
                Message.conversation_id.label("cid"),
                func.max(Message.created_at).label("mx"),
            )
            .where(
                Message.company_id == company_id,
                Message.conversation_id.in_(conversation_ids),
            )
            .group_by(Message.conversation_id)
        ).subquery()
        q = select(Message).join(
            sub,
            and_(
                Message.conversation_id == sub.c.cid,
                Message.created_at == sub.c.mx,
            ),
        )
        r = await self.db.execute(q)
        rows = list(r.scalars().all())
        out: Dict[uuid.UUID, str] = {}
        for m in rows:
            cid = m.conversation_id
            if cid not in out:
                out[cid] = (m.message_text or "")[:500]
        return out

    async def get_by_external_id(self, external_message_id: str) -> Optional[Message]:
        """Find a message by external provider id (e.g. Twilio MessageSid)."""
        result = await self.db.execute(
            select(Message).where(Message.external_message_id == external_message_id)
        )
        return result.scalar_one_or_none()

    async def list_messages_since(
        self,
        conversation_id: uuid.UUID,
        since: datetime,
    ) -> List[Message]:
        """Return all messages strictly after *since* in chronological order.

        Used by the portal inbox for incremental polling: pass the ``created_at``
        of the last message the UI already has to receive only new messages.
        """
        result = await self.db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.created_at > since,
            )
            .order_by(Message.created_at.asc(), self._SENDER_ORDER_ASC.asc())
        )
        return list(result.scalars().all())

    async def list_recent_customer_messages(
        self,
        conversation_id: uuid.UUID,
        limit: int = 20,
        since: Optional[datetime] = None,
    ) -> List[Message]:
        """
        Return recent *customer* messages for bot-detection analysis.

        Args:
            conversation_id: Conversation to query.
            limit:           Max rows to fetch (newest first then reversed).
            since:           If set, only return messages after this timestamp.
        """
        query = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.sender_type == "customer",
            )
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        if since is not None:
            query = query.where(Message.created_at >= since)
        result = await self.db.execute(query)
        rows = list(result.scalars().all())
        return list(reversed(rows))
