"""
Unit tests for DocumentService.

All external dependencies (S3, Weaviate, DB) are mocked.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.document import DocumentRead, DocumentIndexJobRead


def _now():
    return datetime.now(timezone.utc)


def _doc(doc_id=None, company_id=None, **kwargs):
    return MagicMock(
        id=doc_id or uuid.uuid4(),
        company_id=company_id or uuid.uuid4(),
        file_name=kwargs.get("file_name", "test.pdf"),
        s3_bucket=kwargs.get("s3_bucket", "my-bucket"),
        s3_key=kwargs.get("s3_key", "companies/c1/documents/d1/test.pdf"),
        mime_type=kwargs.get("mime_type", "application/pdf"),
        file_size=kwargs.get("file_size", 1024),
        status=kwargs.get("status", "uploaded"),
        uploaded_by=kwargs.get("uploaded_by", None),
        created_at=_now(),
        updated_at=_now(),
    )


def _job(job_id=None, doc_id=None, **kwargs):
    return MagicMock(
        id=job_id or uuid.uuid4(),
        company_id=uuid.uuid4(),
        document_id=doc_id or uuid.uuid4(),
        status=kwargs.get("status", "pending"),
        retry_count=0,
        error_message=None,
        started_at=None,
        completed_at=None,
        created_at=_now(),
    )


@pytest.fixture
def mock_doc_repo():
    return AsyncMock()


@pytest.fixture
def mock_job_repo():
    return AsyncMock()


@pytest.fixture
def mock_storage():
    # SupabaseStorageClient methods are synchronous (supabase-py), so MagicMock is correct here
    return MagicMock()


@pytest.fixture
def doc_service(mock_doc_repo, mock_job_repo, mock_storage):
    from app.services.document_service import DocumentService
    return DocumentService(
        document_repo=mock_doc_repo,
        job_repo=mock_job_repo,
        storage_client=mock_storage,
    )


class TestDocumentServiceUpload:
    @pytest.mark.asyncio
    async def test_upload_stores_metadata_and_creates_job(
        self, doc_service, mock_doc_repo, mock_job_repo, mock_storage
    ):
        company_id = uuid.uuid4()
        file_bytes = b"hello document"
        file_name = "report.pdf"
        mime_type = "application/pdf"

        doc = _doc(company_id=company_id, file_name=file_name, mime_type=mime_type)
        job = _job(doc_id=doc.id)

        mock_doc_repo.create.return_value = doc
        mock_job_repo.create.return_value = job
        mock_storage.upload_file.return_value = doc.s3_key

        result_doc, result_job = await doc_service.upload_document(
            company_id=company_id,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
        )

        assert result_doc is doc
        assert result_job is job
        mock_storage.upload_file.assert_called_once()
        mock_doc_repo.create.assert_called_once()
        mock_job_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_uses_correct_s3_key_format(
        self, doc_service, mock_doc_repo, mock_job_repo, mock_storage
    ):
        company_id = uuid.uuid4()
        mock_doc_repo.create.return_value = _doc(company_id=company_id)
        mock_job_repo.create.return_value = _job()
        mock_storage.upload_file.return_value = "some-key"

        await doc_service.upload_document(
            company_id=company_id,
            file_bytes=b"data",
            file_name="My Report.pdf",
            mime_type="application/pdf",
        )

        call_args = mock_storage.upload_file.call_args
        key = call_args[0][1] if call_args[0] else call_args[1].get("key", "")
        assert "companies/" in key
        assert "documents/" in key


class TestDocumentServiceGet:
    @pytest.mark.asyncio
    async def test_get_document_returns_document(
        self, doc_service, mock_doc_repo
    ):
        company_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        doc = _doc(doc_id=doc_id, company_id=company_id)
        mock_doc_repo.get_by_company_and_id.return_value = doc

        result = await doc_service.get_document(company_id, doc_id)
        assert result is doc

    @pytest.mark.asyncio
    async def test_get_document_not_found_raises(
        self, doc_service, mock_doc_repo
    ):
        from app.core.exceptions import NotFoundError
        mock_doc_repo.get_by_company_and_id.return_value = None

        with pytest.raises(NotFoundError):
            await doc_service.get_document(uuid.uuid4(), uuid.uuid4())


class TestDocumentServiceList:
    @pytest.mark.asyncio
    async def test_list_documents_returns_list(
        self, doc_service, mock_doc_repo
    ):
        company_id = uuid.uuid4()
        docs = [_doc(company_id=company_id) for _ in range(3)]
        mock_doc_repo.list_by_company.return_value = docs

        result = await doc_service.list_documents(company_id)
        assert len(result) == 3
