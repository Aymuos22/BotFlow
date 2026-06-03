"""
Unit tests for the S3StorageClient using moto (AWS mock).

All tests run against a moto-mocked S3; no real AWS credentials needed.
"""
import io
import uuid
import pytest
import boto3
from moto import mock_aws

from app.integrations.s3.client import S3StorageClient


BUCKET = "test-bucket"
REGION = "us-east-1"


def _make_client() -> S3StorageClient:
    return S3StorageClient(
        bucket_name=BUCKET,
        region=REGION,
        access_key_id="fake-key",
        secret_access_key="fake-secret",
    )


def _create_bucket():
    """Create the moto-mocked S3 bucket."""
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket=BUCKET)


@mock_aws
class TestS3StorageClientUpload:
    def test_upload_file_returns_key(self):
        _create_bucket()
        client = _make_client()
        key = client.upload_file(b"hello world", "test/file.txt", "text/plain")
        assert key == "test/file.txt"

    def test_uploaded_file_retrievable(self):
        _create_bucket()
        client = _make_client()
        data = b"important document content"
        client.upload_file(data, "docs/report.pdf", "application/pdf")
        fetched = client.get_file("docs/report.pdf")
        assert fetched == data

    def test_upload_overwrites_existing_key(self):
        _create_bucket()
        client = _make_client()
        client.upload_file(b"v1", "key.txt", "text/plain")
        client.upload_file(b"v2", "key.txt", "text/plain")
        assert client.get_file("key.txt") == b"v2"


@mock_aws
class TestS3StorageClientDelete:
    def test_delete_existing_file_returns_true(self):
        _create_bucket()
        client = _make_client()
        client.upload_file(b"data", "to_delete.txt", "text/plain")
        result = client.delete_file("to_delete.txt")
        assert result is True

    def test_deleted_file_no_longer_exists(self):
        _create_bucket()
        client = _make_client()
        client.upload_file(b"data", "temp.txt", "text/plain")
        client.delete_file("temp.txt")
        assert client.file_exists("temp.txt") is False

    def test_delete_nonexistent_key_returns_true(self):
        # S3 delete is idempotent
        _create_bucket()
        client = _make_client()
        result = client.delete_file("nonexistent.txt")
        assert result is True


@mock_aws
class TestS3StorageClientExists:
    def test_file_exists_after_upload(self):
        _create_bucket()
        client = _make_client()
        client.upload_file(b"x", "exists.txt", "text/plain")
        assert client.file_exists("exists.txt") is True

    def test_file_not_exists_when_not_uploaded(self):
        _create_bucket()
        client = _make_client()
        assert client.file_exists("not_there.txt") is False


@mock_aws
class TestS3StorageClientPresignedUrl:
    def test_presigned_url_is_string(self):
        _create_bucket()
        client = _make_client()
        client.upload_file(b"data", "doc.txt", "text/plain")
        url = client.generate_presigned_url("doc.txt")
        assert isinstance(url, str)
        assert "doc.txt" in url or "X-Amz" in url

    def test_presigned_url_custom_expiry(self):
        _create_bucket()
        client = _make_client()
        client.upload_file(b"data", "doc.txt", "text/plain")
        url = client.generate_presigned_url("doc.txt", expires_in=3600)
        assert isinstance(url, str)


@mock_aws
class TestS3StorageClientGetFile:
    def test_get_nonexistent_key_raises(self):
        _create_bucket()
        client = _make_client()
        with pytest.raises(Exception):
            client.get_file("does_not_exist.txt")
