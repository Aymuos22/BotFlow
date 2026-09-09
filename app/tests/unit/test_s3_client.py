"""
Unit tests for SupabaseStorageClient using unittest.mock.

All tests patch supabase.create_client so no real Supabase credentials
are needed.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.integrations.s3.client import SupabaseStorageClient


BUCKET = "test-bucket"
SUPABASE_URL = "https://test.supabase.co"
SERVICE_ROLE_KEY = "fake-service-role-key"


def _make_client(mock_supabase_client: MagicMock) -> SupabaseStorageClient:
    """Create a SupabaseStorageClient with a patched supabase create_client."""
    with patch("app.integrations.s3.client.create_client", return_value=mock_supabase_client):
        return SupabaseStorageClient(
            supabase_url=SUPABASE_URL,
            service_role_key=SERVICE_ROLE_KEY,
            bucket_name=BUCKET,
        )


@pytest.fixture
def mock_supabase():
    """Return a fully mocked supabase client."""
    client = MagicMock()
    storage_bucket = MagicMock()
    client.storage.from_.return_value = storage_bucket
    return client, storage_bucket


class TestSupabaseStorageClientUpload:
    def test_upload_file_returns_key(self, mock_supabase):
        supabase_mock, bucket_mock = mock_supabase
        client = _make_client(supabase_mock)
        key = client.upload_file(b"hello world", "test/file.txt", "text/plain")
        assert key == "test/file.txt"
        bucket_mock.upload.assert_called_once()

    def test_upload_calls_correct_bucket(self, mock_supabase):
        supabase_mock, bucket_mock = mock_supabase
        client = _make_client(supabase_mock)
        client.upload_file(b"data", "docs/report.pdf", "application/pdf")
        supabase_mock.storage.from_.assert_called_with(BUCKET)


class TestSupabaseStorageClientGetFile:
    def test_get_file_returns_bytes(self, mock_supabase):
        supabase_mock, bucket_mock = mock_supabase
        bucket_mock.download.return_value = b"file content"
        client = _make_client(supabase_mock)
        data = client.get_file("docs/file.txt")
        assert data == b"file content"
        bucket_mock.download.assert_called_once_with("docs/file.txt")


class TestSupabaseStorageClientDelete:
    def test_delete_returns_true(self, mock_supabase):
        supabase_mock, bucket_mock = mock_supabase
        client = _make_client(supabase_mock)
        result = client.delete_file("to_delete.txt")
        assert result is True
        bucket_mock.remove.assert_called_once_with(["to_delete.txt"])


class TestSupabaseStorageClientExists:
    def test_file_exists_when_found_in_list(self, mock_supabase):
        supabase_mock, bucket_mock = mock_supabase
        bucket_mock.list.return_value = [{"name": "file.txt"}, {"name": "other.txt"}]
        client = _make_client(supabase_mock)
        assert client.file_exists("folder/file.txt") is True

    def test_file_not_exists_when_absent_from_list(self, mock_supabase):
        supabase_mock, bucket_mock = mock_supabase
        bucket_mock.list.return_value = [{"name": "other.txt"}]
        client = _make_client(supabase_mock)
        assert client.file_exists("folder/missing.txt") is False

    def test_file_not_exists_on_exception(self, mock_supabase):
        supabase_mock, bucket_mock = mock_supabase
        bucket_mock.list.side_effect = Exception("network error")
        client = _make_client(supabase_mock)
        assert client.file_exists("folder/file.txt") is False


class TestSupabaseStorageClientPresignedUrl:
    def test_presigned_url_from_dict_signedURL(self, mock_supabase):
        supabase_mock, bucket_mock = mock_supabase
        bucket_mock.create_signed_url.return_value = {
            "signedURL": "https://supabase.co/signed/url"
        }
        client = _make_client(supabase_mock)
        url = client.generate_presigned_url("doc.txt")
        assert url == "https://supabase.co/signed/url"

    def test_presigned_url_from_dict_signedUrl(self, mock_supabase):
        supabase_mock, bucket_mock = mock_supabase
        bucket_mock.create_signed_url.return_value = {
            "signedUrl": "https://supabase.co/signed/url2"
        }
        client = _make_client(supabase_mock)
        url = client.generate_presigned_url("doc.txt")
        assert url == "https://supabase.co/signed/url2"

    def test_presigned_url_custom_expiry(self, mock_supabase):
        supabase_mock, bucket_mock = mock_supabase
        bucket_mock.create_signed_url.return_value = {"signedURL": "https://x.co/url"}
        client = _make_client(supabase_mock)
        client.generate_presigned_url("doc.txt", expires_in=7200)
        bucket_mock.create_signed_url.assert_called_once_with("doc.txt", 7200)
