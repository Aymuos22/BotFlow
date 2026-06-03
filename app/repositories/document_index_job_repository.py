"""
Repository for the DocumentIndexJob model.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_index_job import DocumentIndexJob
from app.repositories.base import BaseRepository


class DocumentIndexJobRepository(BaseRepository[DocumentIndexJob]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(DocumentIndexJob, db)

    async def get_latest_for_document(
        self, document_id: uuid.UUID
    ) -> Optional[DocumentIndexJob]:
        """Return the most recently created job for *document_id*."""
        result = await self.db.execute(
            select(DocumentIndexJob)
            .where(DocumentIndexJob.document_id == document_id)
            .order_by(DocumentIndexJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_pending(self, limit: int = 20) -> List[DocumentIndexJob]:
        """Return up to *limit* jobs in ``pending`` status (oldest first)."""
        result = await self.db.execute(
            select(DocumentIndexJob)
            .where(DocumentIndexJob.status == "pending")
            .order_by(DocumentIndexJob.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def claim_job(self, job: DocumentIndexJob) -> DocumentIndexJob:
        """
        Atomically mark a job as ``processing``.

        Sets ``started_at`` to now and increments ``retry_count``.
        """
        updates = {
            "status": "processing",
            "started_at": datetime.now(timezone.utc),
            "retry_count": job.retry_count + 1,
        }
        return await self.update(job, updates)

    async def complete_job(self, job: DocumentIndexJob) -> DocumentIndexJob:
        """Mark a job as ``completed``."""
        return await self.update(
            job,
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc),
                "error_message": None,
            },
        )

    async def fail_job(
        self, job: DocumentIndexJob, error_message: str
    ) -> DocumentIndexJob:
        """Mark a job as ``failed`` with an error message."""
        return await self.update(
            job,
            {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc),
                "error_message": error_message,
            },
        )
