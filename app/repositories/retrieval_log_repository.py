"""
Repository for the RetrievalLog model.

Retrieval logs are append-only – no update or delete operations are exposed.
"""
import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval_log import RetrievalLog
from app.repositories.base import BaseRepository


class RetrievalLogRepository(BaseRepository[RetrievalLog]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RetrievalLog, db)

    async def list_by_company(
        self, company_id: uuid.UUID, limit: int = 100
    ) -> List[RetrievalLog]:
        result = await self.db.execute(
            select(RetrievalLog)
            .where(RetrievalLog.company_id == company_id)
            .order_by(RetrievalLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_conversation(
        self, conversation_id: uuid.UUID, limit: int = 50
    ) -> List[RetrievalLog]:
        result = await self.db.execute(
            select(RetrievalLog)
            .where(RetrievalLog.conversation_id == conversation_id)
            .order_by(RetrievalLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
