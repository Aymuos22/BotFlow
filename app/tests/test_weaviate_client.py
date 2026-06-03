"""
Unit tests for the Weaviate HTTP client wrapper.

Uses ``unittest.mock.patch`` to mock ``httpx.AsyncClient``.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.weaviate.client import WeaviateClient
from app.core.exceptions import ExternalServiceError


BASE_URL = "http://weaviate-test:8080"
COLLECTION = "CoTestCollection"


@pytest.fixture
def weaviate_client():
    return WeaviateClient(url=BASE_URL, api_key="weaviate-key")


def _mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_error = status_code >= 400
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


def _patch_async_client(mock_response):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.delete = AsyncMock(return_value=mock_response)
    return patch("httpx.AsyncClient", return_value=mock_client), mock_client


@pytest.mark.unit
class TestWeaviateCreateCollection:
    """WeaviateClient.create_collection"""

    async def test_posts_to_schema_endpoint(self, weaviate_client):
        resp = _mock_response(200, {"class": COLLECTION})
        ctx, mock_client = _patch_async_client(resp)
        with ctx:
            result = await weaviate_client.create_collection(COLLECTION)
        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert call_url == f"{BASE_URL}/v1/schema"
        assert result is True

    async def test_sends_api_key_header(self, weaviate_client):
        resp = _mock_response(200, {"class": COLLECTION})
        ctx, mock_client = _patch_async_client(resp)
        with ctx:
            await weaviate_client.create_collection(COLLECTION)
        headers = mock_client.post.call_args[1].get("headers", {})
        assert headers.get("Authorization") == "Bearer weaviate-key"

    async def test_raises_on_5xx(self, weaviate_client):
        resp = _mock_response(500, {"error": "server error"})
        ctx, _ = _patch_async_client(resp)
        with ctx:
            with pytest.raises(ExternalServiceError):
                await weaviate_client.create_collection(COLLECTION)

    async def test_collection_name_in_payload(self, weaviate_client):
        resp = _mock_response(200, {"class": COLLECTION})
        ctx, mock_client = _patch_async_client(resp)
        with ctx:
            await weaviate_client.create_collection(COLLECTION)
        body = mock_client.post.call_args[1].get("json", {})
        assert body["class"] == COLLECTION
        assert "properties" in body and len(body["properties"]) >= 1
        names = {p["name"] for p in body["properties"]}
        assert "chunk_text" in names


@pytest.mark.unit
class TestWeaviateCollectionExists:
    """WeaviateClient.collection_exists"""

    async def test_returns_true_when_200(self, weaviate_client):
        resp = _mock_response(200, {"class": COLLECTION})
        ctx, _ = _patch_async_client(resp)
        with ctx:
            assert await weaviate_client.collection_exists(COLLECTION) is True

    async def test_returns_false_when_404(self, weaviate_client):
        resp = _mock_response(404, {"error": "not found"})
        ctx, _ = _patch_async_client(resp)
        with ctx:
            assert await weaviate_client.collection_exists(COLLECTION) is False

    async def test_raises_on_5xx(self, weaviate_client):
        resp = _mock_response(500, {"error": "server"})
        ctx, _ = _patch_async_client(resp)
        with ctx:
            with pytest.raises(ExternalServiceError):
                await weaviate_client.collection_exists(COLLECTION)


@pytest.mark.unit
class TestWeaviateDeleteCollection:
    """WeaviateClient.delete_collection"""

    async def test_deletes_correct_url(self, weaviate_client):
        resp = _mock_response(200, {})
        ctx, mock_client = _patch_async_client(resp)
        with ctx:
            result = await weaviate_client.delete_collection(COLLECTION)
        call_url = mock_client.delete.call_args[0][0]
        assert call_url == f"{BASE_URL}/v1/schema/{COLLECTION}"
        assert result is True

    async def test_raises_on_error(self, weaviate_client):
        resp = _mock_response(422, {"error": "locked"})
        ctx, _ = _patch_async_client(resp)
        with ctx:
            with pytest.raises(ExternalServiceError):
                await weaviate_client.delete_collection(COLLECTION)
