"""
Tests for the health-check endpoint.

GET /health
GET /api/v1/health

These are integration-free tests – no DB, no mocks required.
"""
import pytest


@pytest.mark.api
class TestHealthEndpoint:
    """Health endpoint must always return 200 with a structured body."""

    async def test_root_health_returns_200(self, client):
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_root_health_body_structure(self, client):
        response = await client.get("/health")
        data = response.json()
        assert data["success"] is True
        assert "status" in data["data"]
        assert data["data"]["status"] == "ok"

    async def test_root_health_includes_version(self, client):
        response = await client.get("/health")
        data = response.json()
        assert "version" in data["data"]

    async def test_versioned_health_returns_200(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_versioned_health_body_structure(self, client):
        response = await client.get("/api/v1/health")
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "ok"

    async def test_unknown_route_returns_404(self, client):
        response = await client.get("/nonexistent-route")
        assert response.status_code == 404
