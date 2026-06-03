"""
Repository for the Document model.
"""
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Document, db)

    async def list_by_company(
        self, company_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[Document]:
        """Return all documents owned by *company_id*, newest first."""
        result = await self.db.execute(
            select(Document)
            .where(Document.company_id == company_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_company(self, company_id: uuid.UUID) -> int:
        from sqlalchemy import func, select as sa_select
        result = await self.db.execute(
            sa_select(func.count()).select_from(Document).where(
                Document.company_id == company_id
            )
        )
        return result.scalar_one()

    async def get_by_company_and_id(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> Optional[Document]:
        """Fetch a document by its id, scoped to a company (prevents cross-tenant access)."""
        result = await self.db.execute(
            select(Document).where(
                Document.company_id == company_id,
                Document.id == document_id,
            )
        )
        return result.scalar_one_or_none()
