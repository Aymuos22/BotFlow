"""
Repository for the Conversation model.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Conversation, db)

    async def get_by_company_and_phone(
        self, company_id: uuid.UUID, customer_phone: str
    ) -> Optional[Conversation]:
        """
        Retrieve an active conversation for a (company, phone) pair.

        Returns the most recent active conversation or None.
        """
        result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.company_id == company_id,
                Conversation.customer_phone == customer_phone,
                Conversation.status == "active",
            )
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_inbox(
        self,
        company_id: uuid.UUID,
        *,
        limit: int = 40,
        offset: int = 0,
        inquiry_filter: Optional[str] = None,
    ) -> List[Conversation]:
        """
        Conversations for the company inbox, most recently active first.
        Only active (non-closed) conversations are returned.

        inquiry_filter: None (all) | "open" (inquiry_complete is false) |
            "complete" (inquiry_complete is true)
        """
        stmt = select(Conversation).where(
            Conversation.company_id == company_id,
            Conversation.status == "active",
        )
        if inquiry_filter == "open":
            stmt = stmt.where(Conversation.inquiry_complete.is_(False))
        elif inquiry_filter == "complete":
            stmt = stmt.where(Conversation.inquiry_complete.is_(True))
        stmt = (
            stmt.order_by(
                desc(Conversation.last_message_at),
                desc(Conversation.updated_at),
            )
            .limit(min(limit, 200))
            .offset(max(offset, 0))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_for_inbox(
        self, company_id: uuid.UUID, inquiry_filter: Optional[str] = None
    ) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Conversation).where(
            Conversation.company_id == company_id,
            Conversation.status == "active",
        )
        if inquiry_filter == "open":
            stmt = stmt.where(Conversation.inquiry_complete.is_(False))
        elif inquiry_filter == "complete":
            stmt = stmt.where(Conversation.inquiry_complete.is_(True))
        r = await self.db.execute(stmt)
        return int(r.scalar_one() or 0)

    async def touch_last_message_at(
        self, conversation_id: uuid.UUID, ts: datetime
    ) -> None:
        """Update ``last_message_at`` without needing an ORM-loaded object."""
        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(last_message_at=ts)
        )
        await self.db.flush()
