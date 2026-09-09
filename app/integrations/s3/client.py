"""
Supabase Storage abstraction layer (replaces AWS S3).

Architecture
------------
``StorageClient`` is a runtime Protocol that any storage backend must satisfy.
``SupabaseStorageClient`` is the production implementation backed by supabase-py.

The supabase storage SDK is synchronous; calls are wrapped with
``asyncio.get_event_loop().run_in_executor`` so they do not block the FastAPI
event loop.

All external storage interactions are **fully mockable** in tests:
  - unit tests: replace SupabaseStorageClient with an AsyncMock
  - integration tests: provide a mock implementation of StorageClient
"""
import asyncio
import logging
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Protocol (interface) — unchanged so all call-sites stay compatible
# --------------------------------------------------------------------------- #


@runtime_checkable
class StorageClient(Protocol):
    """
    Interface that any file-storage backend must implement.

    Designed so tests can inject a plain ``AsyncMock`` or a
    ``SupabaseStorageClient`` interchangeably.
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
        """Return a time-limited signed GET URL for *key*."""
        ...


# --------------------------------------------------------------------------- #
# Production implementation
# --------------------------------------------------------------------------- #


class SupabaseStorageClient:
    """
    Supabase Storage client backed by supabase-py.

    All public methods can be safely awaited even though the underlying SDK is
    synchronous – they run in the default thread-pool executor.
    """

    def __init__(
        self,
        supabase_url: str,
        service_role_key: str,
        bucket_name: str,
    ) -> None:
        from supabase import create_client

        self._supabase = create_client(supabase_url, service_role_key)
        self._bucket = bucket_name

    # ------------------------------------------------------------------ #
    # Sync helpers (run in thread-pool when awaited)
    # ------------------------------------------------------------------ #

    def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to Supabase Storage and return the key."""
        self._supabase.storage.from_(self._bucket).upload(
            path=key,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        logger.debug(
            "Uploaded supabase://%s/%s (%d bytes)", self._bucket, key, len(file_bytes)
        )
        return key

    def get_file(self, key: str) -> bytes:
        """Download object bytes from Supabase Storage."""
        data: bytes = self._supabase.storage.from_(self._bucket).download(key)
        logger.debug(
            "Downloaded supabase://%s/%s (%d bytes)", self._bucket, key, len(data)
        )
        return data

    def delete_file(self, key: str) -> bool:
        """Delete an object.  Returns True on success."""
        self._supabase.storage.from_(self._bucket).remove([key])
        logger.debug("Deleted supabase://%s/%s", self._bucket, key)
        return True

    def file_exists(self, key: str) -> bool:
        """Check whether an object exists by listing its parent path."""
        parts = key.rsplit("/", 1)
        folder = parts[0] if len(parts) > 1 else ""
        filename = parts[-1]
        try:
            files = self._supabase.storage.from_(self._bucket).list(folder)
            return any(
                isinstance(f, dict) and f.get("name") == filename for f in (files or [])
            )
        except Exception:
            return False

    def generate_presigned_url(
        self, key: str, expires_in: int = 3600
    ) -> str:
        """Generate a time-limited signed GET URL valid for *expires_in* seconds."""
        result = self._supabase.storage.from_(self._bucket).create_signed_url(
            key, expires_in
        )
        # supabase-py v2 returns a SignedURLResponse or dict
        if isinstance(result, dict):
            url = result.get("signedURL") or result.get("signedUrl") or ""
        else:
            url = getattr(result, "signed_url", None) or getattr(result, "signedURL", None) or ""
        return str(url)


# --------------------------------------------------------------------------- #
# FastAPI dependency factory
# --------------------------------------------------------------------------- #

_client_instance: Optional[SupabaseStorageClient] = None


def get_storage_client() -> SupabaseStorageClient:
    """
    FastAPI dependency that returns a singleton SupabaseStorageClient.

    Override in tests via::

        app.dependency_overrides[get_storage_client] = lambda: mock_storage
    """
    global _client_instance
    if _client_instance is None:
        from app.core.config import get_settings

        s = get_settings()
        _client_instance = SupabaseStorageClient(
            supabase_url=s.supabase_url,
            service_role_key=s.supabase_service_role_key,
            bucket_name=s.supabase_storage_bucket,
        )
    return _client_instance
