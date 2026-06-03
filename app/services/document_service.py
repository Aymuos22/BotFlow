"""
DocumentService – orchestrates file upload and document metadata storage.

Responsibilities
----------------
1. Validate that the company exists.
2. Generate a deterministic S3 key (tenant-safe).
3. Upload raw bytes to S3 via the StorageClient abstraction.
4. Persist document metadata in Supabase (documents table).
5. Create a ``pending`` DocumentIndexJob for background processing.

The raw file bytes are NEVER stored in the database.
"""
import logging
import uuid
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.integrations.s3.client import StorageClient
from app.models.document import Document
from app.models.document_index_job import DocumentIndexJob
from app.repositories.company_repository import CompanyRepository
from app.repositories.document_index_job_repository import DocumentIndexJobRepository
from app.repositories.document_repository import DocumentRepository
from app.utils.s3_keys import build_document_s3_key

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(
        self,
        document_repo: DocumentRepository,
        job_repo: DocumentIndexJobRepository,
        storage_client: StorageClient,
        company_repo: CompanyRepository | None = None,
    ) -> None:
        self._doc_repo = document_repo
        self._job_repo = job_repo
        self._storage = storage_client
        self._company_repo = company_repo

    # ------------------------------------------------------------------ #
    # Upload
    # ------------------------------------------------------------------ #

    async def upload_document(
        self,
        company_id: uuid.UUID,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        uploaded_by: str | None = None,
    ) -> Tuple[Document, DocumentIndexJob]:
        """
        Upload a file to S3 and save metadata to DB.

        Args:
            company_id:  Owning company.
            file_bytes:  Raw file content.
            file_name:   Original filename (will be sanitized for S3 key).
            mime_type:   MIME type of the file.
            uploaded_by: Optional identifier of the uploader.

        Returns:
            (Document, DocumentIndexJob) tuple.

        Raises:
            NotFoundError: If the company does not exist.
        """
        # Validate company exists (optional: only if repo is injected)
        if self._company_repo is not None:
            company = await self._company_repo.get(company_id)
            if company is None:
                raise NotFoundError("Company", company_id)

        # Generate document id up-front so we can include it in the S3 key
        doc_id = uuid.uuid4()
        s3_key = build_document_s3_key(company_id, doc_id, file_name)
        from app.core.config import get_settings
        bucket = get_settings().s3_bucket_name

        # Upload to S3
        self._storage.upload_file(file_bytes, s3_key, mime_type)
        logger.info(
            "Document uploaded to S3",
            extra={"company_id": str(company_id), "s3_key": s3_key},
        )

        # Persist metadata
        doc = await self._doc_repo.create(
            {
                "id": doc_id,
                "company_id": company_id,
                "file_name": file_name,
                "s3_bucket": bucket,
                "s3_key": s3_key,
                "mime_type": mime_type,
                "file_size": len(file_bytes),
                "status": "uploaded",
                "uploaded_by": uploaded_by,
            }
        )

        # Create indexing job
        job = await self._job_repo.create(
            {
                "company_id": company_id,
                "document_id": doc.id,
                "status": "pending",
                "retry_count": 0,
            }
        )

        return doc, job

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #

    async def get_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> Document:
        """
        Retrieve a single document by id, scoped to company.

        Raises:
            NotFoundError: If the document does not exist for this company.
        """
        doc = await self._doc_repo.get_by_company_and_id(company_id, document_id)
        if doc is None:
            raise NotFoundError("Document", document_id)
        return doc

    async def list_documents(
        self, company_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[Document]:
        """Return all documents for *company_id*, newest first."""
        return await self._doc_repo.list_by_company(
            company_id, limit=limit, offset=offset
        )

    async def count_documents(self, company_id: uuid.UUID) -> int:
        return await self._doc_repo.count_by_company(company_id)
