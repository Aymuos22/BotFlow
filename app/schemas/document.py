"""
Pydantic schemas for the Document domain.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentRead(BaseModel):
    """Full document representation returned by read endpoints."""
    id: uuid.UUID
    company_id: uuid.UUID
    file_name: str
    s3_bucket: str
    s3_key: str
    mime_type: str
    file_size: Optional[int]
    status: str
    uploaded_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentIndexJobRead(BaseModel):
    """Document index job representation."""
    id: uuid.UUID
    company_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    retry_count: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    """Response returned after a successful file upload."""
    document: DocumentRead
    index_job: DocumentIndexJobRead
    message: str = "Document uploaded and indexing started."


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    documents: List[DocumentRead]
    total: int
