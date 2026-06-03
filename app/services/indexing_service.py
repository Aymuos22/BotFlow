"""
IndexingService – DB-backed document indexing pipeline.

Pipeline
--------
1. ``trigger_indexing(doc_id, company_id)``
   Creates a DocumentIndexJob and immediately processes it synchronously.
   (No background worker daemon is needed in Phase 2; the job model is
   designed so a worker could poll ``list_pending`` in a later phase.)

2. ``process_job(job)``
   a. Claim the job (status → processing, retry_count++)
   b. Fetch document metadata from DB
   c. Fetch company config to resolve Weaviate collection name
   d. Download raw bytes from S3
   e. Parse text (txt / pdf via text_processing utils)
   f. Chunk text with configured chunk_size / overlap
   g. Upsert chunks into the company's Weaviate collection
   h. Update document.status → ``indexed``
   i. Mark job as completed

Retries
-------
If step (d)-(h) raises, the caller is responsible for calling
``job_repo.fail_job()``.  ``trigger_indexing`` does this automatically.
``retry_count`` is incremented on each claim.
"""
import logging
import uuid
from typing import TYPE_CHECKING, List, Optional

from app.core.exceptions import NotFoundError
from app.integrations.s3.client import StorageClient
from app.integrations.weaviate.client import WeaviateClient
from app.models.document import Document
from app.models.document_index_job import DocumentIndexJob
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.document_index_job_repository import DocumentIndexJobRepository
from app.repositories.document_repository import DocumentRepository
from app.utils.text_processing import chunk_text, parse_document

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.integrations.embeddings.client import EmbeddingClientProtocol


class IndexingService:
    def __init__(
        self,
        document_repo: DocumentRepository,
        job_repo: DocumentIndexJobRepository,
        config_repo: CompanyConfigRepository,
        storage_client: StorageClient,
        weaviate_client: WeaviateClient,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        embedding_client: Optional["EmbeddingClientProtocol"] = None,
    ) -> None:
        self._doc_repo = document_repo
        self._job_repo = job_repo
        self._config_repo = config_repo
        self._storage = storage_client
        self._weaviate = weaviate_client
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._embedding = embedding_client

    async def trigger_indexing(
        self, document_id: uuid.UUID, company_id: uuid.UUID
    ) -> DocumentIndexJob:
        """
        Create a job and run it synchronously.

        Returns the completed (or failed) DocumentIndexJob.
        """
        job = await self._job_repo.create(
            {
                "company_id": company_id,
                "document_id": document_id,
                "status": "pending",
                "retry_count": 0,
            }
        )

        try:
            await self.process_job(job)
        except Exception as exc:
            logger.error(
                "Indexing job failed",
                extra={"job_id": str(job.id), "error": str(exc)},
            )
            await self._job_repo.fail_job(job, str(exc))
            # Update document status to failed as well
            try:
                doc = await self._doc_repo.get(document_id)
                if doc:
                    await self._doc_repo.update(doc, {"status": "failed"})
            except Exception:
                pass

        return job

    async def process_job(self, job: DocumentIndexJob) -> None:
        """
        Execute one indexing job end-to-end.

        Raises on any error so the caller can handle retry / fail logic.
        """
        # Step 1: Claim the job
        job = await self._job_repo.claim_job(job)
        logger.info(
            "Starting indexing job",
            extra={"job_id": str(job.id), "document_id": str(job.document_id)},
        )

        # Step 2: Fetch document
        doc = await self._doc_repo.get(job.document_id)
        if doc is None:
            raise NotFoundError("Document", job.document_id)

        # Step 3: Update document status → indexing
        await self._doc_repo.update(doc, {"status": "indexing"})

        # Step 4: Fetch company config for Weaviate collection name
        config = await self._config_repo.get_by_company(job.company_id)
        if config is None:
            raise ValueError(f"No config found for company {job.company_id}")
        collection_name = config.weaviate_collection

        # Step 5: Download file from S3
        raw_bytes = self._storage.get_file(doc.s3_key)

        # Step 6: Parse text
        text = parse_document(raw_bytes, doc.mime_type)

        # Step 7: Chunk text
        chunks = chunk_text(text, self._chunk_size, self._chunk_overlap)
        logger.debug(
            "Chunked document",
            extra={"document_id": str(doc.id), "chunk_count": len(chunks)},
        )

        # Step 8: Upsert to Weaviate (skip if no chunks)
        if chunks:
            vectors: Optional[List[List[float]]] = None
            if self._embedding is not None:
                try:
                    vectors = await self._embedding.embed_documents(chunks)
                    if len(vectors) != len(chunks):
                        vectors = None
                    elif any(not v for v in vectors):
                        vectors = None
                except Exception as exc:
                    logger.warning(
                        "Chunk embedding failed; indexing BM25-only",
                        extra={"document_id": str(doc.id), "error": str(exc)},
                    )
                    vectors = None
            await self._weaviate.upsert_document_chunks(
                collection_name=collection_name,
                document_id=str(doc.id),
                company_id=str(doc.company_id),
                file_name=doc.file_name,
                s3_key=doc.s3_key,
                chunks=chunks,
                vectors=vectors,
            )

        # Step 9: Update document and job status
        await self._doc_repo.update(doc, {"status": "indexed"})
        await self._job_repo.complete_job(job)

        logger.info(
            "Indexing job completed",
            extra={
                "job_id": str(job.id),
                "chunk_count": len(chunks),
                "collection": collection_name,
            },
        )
