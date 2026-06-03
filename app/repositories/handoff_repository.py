"""
Repository for the Handoff model.
"""
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.handoff import Handoff
from app.repositories.base import BaseRepository


class HandoffRepository(BaseRepository[Handoff]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Handoff, db)

    async def list_by_company(
        self,
        company_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Handoff]:
        stmt = (
            select(Handoff)
            .where(Handoff.company_id == company_id)
            .order_by(Handoff.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Handoff.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_for_conversation(
        self, conversation_id: uuid.UUID
    ) -> Optional[Handoff]:
        """
        Return the latest non-resolved, non-cancelled handoff for a conversation.
        Used to detect duplicate handoff requests.
        """
        result = await self.db.execute(
            select(Handoff)
            .where(
                Handoff.conversation_id == conversation_id,
                Handoff.status.notin_(["resolved", "cancelled"]),
            )
            .order_by(Handoff.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_agent(
        self, agent_id: str, limit: int = 50
    ) -> List[Handoff]:
        """Return handoffs assigned to a specific agent."""
        result = await self.db.execute(
            select(Handoff)
            .where(
                Handoff.assigned_agent_id == agent_id,
                Handoff.status.notin_(["resolved", "cancelled"]),
            )
            .order_by(Handoff.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
