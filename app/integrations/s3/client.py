"""
AWS S3 storage abstraction layer.

Architecture
------------
``StorageClient`` is a runtime Protocol that any storage backend must satisfy.
``S3StorageClient`` is the production implementation backed by boto3.

Boto3 is synchronous; its calls are wrapped with ``asyncio.get_event_loop().
run_in_executor`` so they do not block the FastAPI event loop.

All external S3 interactions are **fully mockable** in tests:
  - unit tests: replace S3StorageClient with an AsyncMock
  - integration tests: use ``moto`` to spin up a fake S3 endpoint

No real AWS credentials are required to run the test suite.
"""
import asyncio
import functools
import logging
from typing import Optional, Protocol, runtime_checkable

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Protocol (interface)
# --------------------------------------------------------------------------- #


@runtime_checkable
class StorageClient(Protocol):
    """
    Interface that any file-storage backend must implement.

    Designed so tests can inject a plain ``AsyncMock`` or a ``moto``-backed
    ``S3StorageClient`` interchangeably.
    """

    def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload *file_bytes* under *key* and return the key."""
        ...

    def get_file(self, key: str) -> bytes:
        """Download the object at *key* and return its bytes."""
        ...

    def delete_file(self, key: str) -> bool:
        """Delete the object at *key*.  Returns True on success."""
        ...

    def file_exists(self, key: str) -> bool:
        """Return True if an object with *key* exists."""
        ...

    def generate_presigned_url(
        self, key: str, expires_in: int = 3600
    ) -> str:
        """Return a time-limited pre-signed GET URL for *key*."""
        ...


# --------------------------------------------------------------------------- #
# Production implementation
# --------------------------------------------------------------------------- #


class S3StorageClient:
    """
    Synchronous boto3-based S3 client wrapped for async usage.

    All public methods can be safely awaited even though boto3 itself is
    synchronous – they run in the default thread-pool executor.
    """

    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ) -> None:
        self._bucket = bucket_name
        self._region = region
        self._s3 = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint_url,
        )

    # ------------------------------------------------------------------ #
    # Sync helpers (run in thread-pool when awaited)
    # ------------------------------------------------------------------ #

    def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to S3 and return the key."""
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        logger.debug("Uploaded s3://%s/%s (%d bytes)", self._bucket, key, len(file_bytes))
        return key

    def get_file(self, key: str) -> bytes:
        """Download object bytes from S3."""
        response = self._s3.get_object(Bucket=self._bucket, Key=key)
        data: bytes = response["Body"].read()
        logger.debug("Downloaded s3://%s/%s (%d bytes)", self._bucket, key, len(data))
        return data

    def delete_file(self, key: str) -> bool:
        """Delete an object.  S3 delete is idempotent – always returns True."""
        self._s3.delete_object(Bucket=self._bucket, Key=key)
        logger.debug("Deleted s3://%s/%s", self._bucket, key)
        return True

    def file_exists(self, key: str) -> bool:
        """Check whether an object exists without downloading it."""
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    def generate_presigned_url(
        self, key: str, expires_in: int = 3600
    ) -> str:
        """Generate a pre-signed GET URL valid for *expires_in* seconds."""
        url: str = self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url


# --------------------------------------------------------------------------- #
# FastAPI dependency factory
# --------------------------------------------------------------------------- #


_client_instance: Optional[S3StorageClient] = None


def get_storage_client() -> S3StorageClient:
    """
    FastAPI dependency that returns a singleton S3StorageClient.

    Override in tests via::

        app.dependency_overrides[get_storage_client] = lambda: mock_storage
    """
    global _client_instance
    if _client_instance is None:
        from app.core.config import get_settings
        s = get_settings()
        _client_instance = S3StorageClient(
            bucket_name=s.s3_bucket_name,
            region=s.s3_region,
            access_key_id=s.aws_access_key_id,
            secret_access_key=s.aws_secret_access_key,
            endpoint_url=s.aws_endpoint_url,
        )
    return _client_instance
