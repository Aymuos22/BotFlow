"""
Document management endpoints.

Routes
------
POST /companies/{company_id}/documents/upload
    Upload a file → store in Supabase Storage → save metadata → create indexing job.

GET  /companies/{company_id}/documents
    List all documents for a company.

GET  /companies/{company_id}/documents/{document_id}
    Retrieve metadata for one document.

POST /companies/{company_id}/documents/{document_id}/index
    Re-trigger indexing for a document (e.g. after initial failure).
"""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.response import APIResponse
from app.integrations.s3.client import SupabaseStorageClient, get_storage_client
from app.integrations.weaviate.client import WeaviateClient, get_weaviate_client
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.document_index_job_repository import DocumentIndexJobRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import (
    DocumentIndexJobRead,
    DocumentListResponse,
    DocumentRead,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService
from app.services.indexing_service import IndexingService
from app.core.config import get_settings
from app.integrations.embeddings.client import get_embedding_client

router = APIRouter(tags=["documents"])


# ------------------------------------------------------------------ #
# Dependency factories
# ------------------------------------------------------------------ #


def _doc_service(
    db: AsyncSession = Depends(get_db),
    storage: SupabaseStorageClient = Depends(get_storage_client),
) -> DocumentService:
    return DocumentService(
        document_repo=DocumentRepository(db),
        job_repo=DocumentIndexJobRepository(db),
        storage_client=storage,
        company_repo=CompanyRepository(db),
    )


def _indexing_service(
    db: AsyncSession = Depends(get_db),
    storage: SupabaseStorageClient = Depends(get_storage_client),
    weaviate: WeaviateClient = Depends(get_weaviate_client),
) -> IndexingService:
    s = get_settings()
    return IndexingService(
        document_repo=DocumentRepository(db),
        job_repo=DocumentIndexJobRepository(db),
        config_repo=CompanyConfigRepository(db),
        storage_client=storage,
        weaviate_client=weaviate,
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
        embedding_client=get_embedding_client(),
    )


# ------------------------------------------------------------------ #
# Upload
# ------------------------------------------------------------------ #


@router.post(
    "/{company_id}/documents/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[DocumentUploadResponse],
    summary="Upload a document to S3 and schedule indexing",
)
async def upload_document(
    company_id: uuid.UUID,
    file: UploadFile = File(...),
    doc_svc: DocumentService = Depends(_doc_service),
    idx_svc: IndexingService = Depends(_indexing_service),
) -> Any:
    file_bytes = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    file_name = file.filename or "upload"

    try:
        doc, job = await doc_svc.upload_document(
            company_id=company_id,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found.",
        )

    # Trigger indexing immediately (synchronous for Phase 2)
    job = await idx_svc.trigger_indexing(doc.id, company_id)

    return APIResponse(
        success=True,
        data=DocumentUploadResponse(
            document=DocumentRead.model_validate(doc),
            index_job=DocumentIndexJobRead.model_validate(job),
        ),
    )


# ------------------------------------------------------------------ #
# List
# ------------------------------------------------------------------ #


@router.get(
    "/{company_id}/documents",
    response_model=APIResponse[DocumentListResponse],
    summary="List all documents for a company",
)
async def list_documents(
    company_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    doc_svc: DocumentService = Depends(_doc_service),
) -> Any:
    docs = await doc_svc.list_documents(company_id, limit=limit, offset=offset)
    total = await doc_svc.count_documents(company_id)
    return APIResponse(
        success=True,
        data=DocumentListResponse(
            documents=[DocumentRead.model_validate(d) for d in docs],
            total=total,
        ),
    )


# ------------------------------------------------------------------ #
# Get single
# ------------------------------------------------------------------ #


@router.get(
    "/{company_id}/documents/{document_id}",
    response_model=APIResponse[DocumentRead],
    summary="Get document metadata by id",
)
async def get_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    doc_svc: DocumentService = Depends(_doc_service),
) -> Any:
    try:
        doc = await doc_svc.get_document(company_id, document_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )
    return APIResponse(success=True, data=DocumentRead.model_validate(doc))


# ------------------------------------------------------------------ #
# Re-trigger indexing
# ------------------------------------------------------------------ #


@router.post(
    "/{company_id}/documents/{document_id}/index",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=APIResponse[dict],
    summary="Re-trigger indexing for a document",
)
async def trigger_index(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    doc_svc: DocumentService = Depends(_doc_service),
    idx_svc: IndexingService = Depends(_indexing_service),
) -> Any:
    try:
        await doc_svc.get_document(company_id, document_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )

    job = await idx_svc.trigger_indexing(document_id, company_id)
    return APIResponse(
        success=True,
        data={"job": DocumentIndexJobRead.model_validate(job)},
    )
