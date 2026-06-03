"""
API tests for the Document endpoints.

POST /api/v1/companies/{company_id}/documents/upload
GET  /api/v1/companies/{company_id}/documents
GET  /api/v1/companies/{company_id}/documents/{document_id}
POST /api/v1/companies/{company_id}/documents/{document_id}/index
"""
import uuid
from datetime import datetime, timezone

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


DOC_RESPONSE = {
    "id": str(uuid.uuid4()),
    "company_id": str(uuid.uuid4()),
    "file_name": "test.txt",
    "s3_bucket": "my-bucket",
    "s3_key": "companies/c1/documents/d1/test.txt",
    "mime_type": "text/plain",
    "file_size": 11,
    "status": "uploaded",
    "uploaded_by": None,
    "created_at": _now_iso(),
    "updated_at": _now_iso(),
}

JOB_RESPONSE = {
    "id": str(uuid.uuid4()),
    "company_id": str(uuid.uuid4()),
    "document_id": DOC_RESPONSE["id"],
    "status": "pending",
    "retry_count": 0,
    "error_message": None,
    "started_at": None,
    "completed_at": None,
    "created_at": _now_iso(),
}


# ──────────────────────────────────────────────────────────────────────────────
# Upload
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.api
async def test_upload_document_success(client, sample_company_id, mock_storage_client, mock_indexing_service):
    """Upload a text file and expect 201 with document + job metadata."""
    mock_storage_client.upload_file.return_value = DOC_RESPONSE["s3_key"]
    mock_indexing_service.trigger_indexing.return_value = type(
        "Job", (), {k: v for k, v in JOB_RESPONSE.items()}
    )()

    response = await client.post(
        f"/api/v1/companies/{sample_company_id}/documents/upload",
        files={"file": ("hello.txt", b"Hello World", "text/plain")},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "document" in data
    assert "index_job" in data
    # Status is 'indexed' when mock pipeline succeeds synchronously
    assert data["document"]["status"] in ("uploaded", "indexed")


@pytest.mark.asyncio
@pytest.mark.api
async def test_upload_document_wrong_company_returns_404(client, mock_storage_client):
    """Unknown company_id should return 404."""
    fake_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/companies/{fake_id}/documents/upload",
        files={"file": ("test.txt", b"content", "text/plain")},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.api
async def test_upload_no_file_returns_422(client, sample_company_id):
    """Missing file field should return 422."""
    response = await client.post(
        f"/api/v1/companies/{sample_company_id}/documents/upload",
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.api
async def test_upload_invalid_uuid_company_returns_422(client):
    """Malformed UUID in path should return 422."""
    response = await client.post(
        "/api/v1/companies/not-a-uuid/documents/upload",
        files={"file": ("test.txt", b"data", "text/plain")},
    )
    assert response.status_code == 422


# ──────────────────────────────────────────────────────────────────────────────
# List
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.api
async def test_list_documents_empty(client, sample_company_id):
    """List for a company with no documents should return empty list."""
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/documents"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["documents"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
@pytest.mark.api
async def test_list_documents_after_upload(client, sample_company_id, mock_storage_client, mock_indexing_service):
    """List should return uploaded document."""
    # First upload
    mock_storage_client.upload_file.return_value = "companies/c/documents/d/hello.txt"
    mock_indexing_service.trigger_indexing.return_value = type(
        "Job", (), {k: v for k, v in JOB_RESPONSE.items()}
    )()

    await client.post(
        f"/api/v1/companies/{sample_company_id}/documents/upload",
        files={"file": ("hello.txt", b"Hello!", "text/plain")},
    )

    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/documents"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] >= 1


# ──────────────────────────────────────────────────────────────────────────────
# Get single document
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.api
async def test_get_document_not_found(client, sample_company_id):
    """Getting a non-existent document should return 404."""
    doc_id = uuid.uuid4()
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/documents/{doc_id}"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.api
async def test_get_document_after_upload(client, sample_company_id, mock_storage_client, mock_indexing_service):
    """Get document by id after upload."""
    mock_storage_client.upload_file.return_value = "companies/c/documents/d/a.txt"
    mock_indexing_service.trigger_indexing.return_value = type(
        "Job", (), {k: v for k, v in JOB_RESPONSE.items()}
    )()

    upload_resp = await client.post(
        f"/api/v1/companies/{sample_company_id}/documents/upload",
        files={"file": ("a.txt", b"content", "text/plain")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["data"]["document"]["id"]

    get_resp = await client.get(
        f"/api/v1/companies/{sample_company_id}/documents/{doc_id}"
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == doc_id


# ──────────────────────────────────────────────────────────────────────────────
# Trigger indexing
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.api
async def test_trigger_index_not_found(client, sample_company_id):
    """Indexing a non-existent document should return 404."""
    doc_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/companies/{sample_company_id}/documents/{doc_id}/index"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.api
async def test_trigger_index_success(
    client, sample_company_id, mock_storage_client, mock_indexing_service
):
    """Re-trigger indexing on an existing document."""
    mock_storage_client.upload_file.return_value = "key"
    job_mock = type("Job", (), {k: v for k, v in JOB_RESPONSE.items()})()
    mock_indexing_service.trigger_indexing.return_value = job_mock

    upload_resp = await client.post(
        f"/api/v1/companies/{sample_company_id}/documents/upload",
        files={"file": ("doc.txt", b"doc content", "text/plain")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["data"]["document"]["id"]

    index_resp = await client.post(
        f"/api/v1/companies/{sample_company_id}/documents/{doc_id}/index"
    )
    assert index_resp.status_code == 202
    assert "job" in index_resp.json()["data"]
