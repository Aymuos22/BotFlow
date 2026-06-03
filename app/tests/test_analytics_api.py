"""
API tests for the Analytics endpoints.

GET /api/v1/companies/{company_id}/analytics/overview
GET /api/v1/companies/{company_id}/analytics/languages
GET /api/v1/companies/{company_id}/analytics/fallbacks
GET /api/v1/companies/{company_id}/analytics/handoffs
GET /api/v1/companies/{company_id}/analytics/top-queries
"""
import uuid

import pytest


@pytest.mark.asyncio
@pytest.mark.api
async def test_analytics_overview_returns_200(client, sample_company_id):
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/analytics/overview"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "total_customer_messages" in data
    assert "fallback_rate" in data
    assert "handoff_rate" in data


@pytest.mark.asyncio
@pytest.mark.api
async def test_analytics_overview_zero_for_empty_company(client, sample_company_id):
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/analytics/overview"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_customer_messages"] == 0
    assert data["fallback_rate"] == 0.0


@pytest.mark.asyncio
@pytest.mark.api
async def test_analytics_overview_unknown_company_404(client):
    response = await client.get(
        f"/api/v1/companies/{uuid.uuid4()}/analytics/overview"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.api
async def test_analytics_languages_returns_200(client, sample_company_id):
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/analytics/languages"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "breakdown" in data
    assert isinstance(data["breakdown"], list)


@pytest.mark.asyncio
@pytest.mark.api
async def test_analytics_fallbacks_returns_200(client, sample_company_id):
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/analytics/fallbacks"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "total_fallbacks" in data
    assert "fallback_rate" in data


@pytest.mark.asyncio
@pytest.mark.api
async def test_analytics_handoffs_returns_200(client, sample_company_id):
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/analytics/handoffs"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "total_handoffs" in data
    assert "resolution_rate" in data


@pytest.mark.asyncio
@pytest.mark.api
async def test_analytics_top_queries_returns_200(client, sample_company_id):
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/analytics/top-queries"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "top_queries" in data
    assert "language_counts" in data


@pytest.mark.asyncio
@pytest.mark.api
async def test_analytics_period_days_param(client, sample_company_id):
    """period_days query param should be accepted."""
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/analytics/overview?period_days=7"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["period_days"] == 7


@pytest.mark.asyncio
@pytest.mark.api
async def test_analytics_invalid_period_returns_422(client, sample_company_id):
    """period_days must be a positive integer."""
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/analytics/overview?period_days=-1"
    )
    assert response.status_code == 422
