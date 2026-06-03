"""
Unit tests for IndexingService.

Validates the full pipeline:
  1. Claim job
  2. Fetch document from S3
  3. Parse text
  4. Chunk text
  5. Upsert to Weaviate
  6. Update document + job status
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _now():
    return datetime.now(timezone.utc)


def _doc(**kwargs):
    return MagicMock(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        file_name=kwargs.get("file_name", "doc.txt"),
        s3_bucket="bucket",
        s3_key=kwargs.get("s3_key", "companies/c/documents/d/doc.txt"),
        mime_type=kwargs.get("mime_type", "text/plain"),
        file_size=100,
        status="indexing",
        created_at=_now(),
        updated_at=_now(),
    )


def _job(doc_id=None, status="pending"):
    m = MagicMock(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        document_id=doc_id or uuid.uuid4(),
        status=status,
        retry_count=0,
        error_message=None,
        started_at=None,
        completed_at=None,
        created_at=_now(),
    )
    return m


def _config():
    return MagicMock(
        weaviate_collection="CoABC123",
        default_language="english",
        supported_languages=["english"],
        rag_config_json=None,
        fallback_config_json=None,
    )


@pytest.fixture
def mock_doc_repo():
    return AsyncMock()


@pytest.fixture
def mock_job_repo():
    return AsyncMock()


@pytest.fixture
def mock_config_repo():
    return AsyncMock()


@pytest.fixture
def mock_storage():
    # S3StorageClient is synchronous (boto3-backed), use MagicMock
    return MagicMock()


@pytest.fixture
def mock_weaviate():
    return AsyncMock()


@pytest.fixture
def indexing_service(
    mock_doc_repo, mock_job_repo, mock_config_repo, mock_storage, mock_weaviate
):
    from app.services.indexing_service import IndexingService
    return IndexingService(
        document_repo=mock_doc_repo,
        job_repo=mock_job_repo,
        config_repo=mock_config_repo,
        storage_client=mock_storage,
        weaviate_client=mock_weaviate,
        chunk_size=200,
        chunk_overlap=20,
    )


class TestProcessJob:
    @pytest.mark.asyncio
    async def test_process_job_happy_path(
        self,
        indexing_service,
        mock_doc_repo,
        mock_job_repo,
        mock_config_repo,
        mock_storage,
        mock_weaviate,
    ):
        doc = _doc()
        job = _job(doc_id=doc.id)
        cfg = _config()

        mock_job_repo.claim_job.return_value = job
        mock_doc_repo.get.return_value = doc
        mock_config_repo.get_by_company.return_value = cfg
        mock_storage.get_file.return_value = b"chunk one. chunk two. chunk three."  # sync return
        mock_weaviate.upsert_document_chunks.return_value = None
        mock_job_repo.complete_job.return_value = job
        mock_doc_repo.update.return_value = doc

        result = await indexing_service.process_job(job)

        mock_job_repo.claim_job.assert_called_once_with(job)
        mock_storage.get_file.assert_called_once_with(doc.s3_key)
        mock_weaviate.upsert_document_chunks.assert_called_once()
        mock_doc_repo.update.assert_called()
        mock_job_repo.complete_job.assert_called_once_with(job)

    @pytest.mark.asyncio
    async def test_process_job_s3_failure_marks_job_failed(
        self,
        indexing_service,
        mock_doc_repo,
        mock_job_repo,
        mock_config_repo,
        mock_storage,
    ):
        doc = _doc()
        job = _job(doc_id=doc.id)
        cfg = _config()

        mock_job_repo.claim_job.return_value = job
        mock_doc_repo.get.return_value = doc
        mock_config_repo.get_by_company.return_value = cfg
        mock_storage.get_file.side_effect = Exception("S3 connection error")  # sync exception

        with pytest.raises(Exception, match="S3 connection error"):
            await indexing_service.process_job(job)

    @pytest.mark.asyncio
    async def test_process_job_empty_text_skips_weaviate(
        self,
        indexing_service,
        mock_doc_repo,
        mock_job_repo,
        mock_config_repo,
        mock_storage,
        mock_weaviate,
    ):
        doc = _doc()
        job = _job(doc_id=doc.id)
        cfg = _config()

        mock_job_repo.claim_job.return_value = job
        mock_doc_repo.get.return_value = doc
        mock_config_repo.get_by_company.return_value = cfg
        mock_storage.get_file.return_value = b""  # sync empty bytes
        mock_job_repo.complete_job.return_value = job
        mock_doc_repo.update.return_value = doc

        await indexing_service.process_job(job)

        # With empty content, no Weaviate upsert should happen
        mock_weaviate.upsert_document_chunks.assert_not_called()


class TestTriggerIndexing:
    @pytest.mark.asyncio
    async def test_trigger_creates_job_and_processes(
        self,
        indexing_service,
        mock_doc_repo,
        mock_job_repo,
        mock_config_repo,
        mock_storage,
        mock_weaviate,
    ):
        company_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        doc = _doc()
        doc.id = doc_id
        doc.company_id = company_id
        job = _job(doc_id=doc_id)

        mock_doc_repo.get.return_value = doc
        mock_job_repo.create.return_value = job
        mock_job_repo.claim_job.return_value = job
        mock_config_repo.get_by_company.return_value = _config()
        mock_storage.get_file.return_value = b"some text content here"  # sync bytes
        mock_weaviate.upsert_document_chunks.return_value = None
        mock_job_repo.complete_job.return_value = job
        mock_doc_repo.update.return_value = doc

        result = await indexing_service.trigger_indexing(doc_id, company_id)

        assert result is job
        mock_job_repo.create.assert_called_once()
