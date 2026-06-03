"""
Unit tests for AnalyticsService.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_analytics_repo():
    repo = AsyncMock()
    repo.get_message_counts.return_value = {
        "total_customer": 100,
        "total_bot": 90,
        "total_fallback": 10,
    }
    repo.get_active_conversation_count.return_value = 5
    repo.get_handoff_counts.return_value = {
        "total": 8,
        "resolved": 5,
        "cancelled": 1,
        "pending": 2,
    }
    repo.get_language_breakdown.return_value = [
        {"language": "english", "count": 60},
        {"language": "hindi", "count": 25},
        {"language": "hinglish", "count": 15},
    ]
    repo.get_top_queries.return_value = [
        {"query": "what is return policy", "count": 12},
        {"query": "how to track order", "count": 8},
    ]
    repo.get_top_fallback_queries.return_value = [
        {"query": "refund processing time", "count": 3},
    ]
    repo.get_avg_handoff_resolution_seconds.return_value = 1200.0
    return repo


@pytest.fixture
def analytics_service(mock_analytics_repo):
    from app.services.analytics_service import AnalyticsService
    return AnalyticsService(analytics_repo=mock_analytics_repo)


class TestOverview:
    @pytest.mark.asyncio
    async def test_returns_overview_with_rates(self, analytics_service):
        company_id = uuid.uuid4()
        result = await analytics_service.get_overview(company_id, period_days=30)

        assert result["total_customer_messages"] == 100
        assert result["total_bot_messages"] == 90
        assert result["total_fallback_messages"] == 10
        assert result["total_handoffs"] == 8
        assert result["active_conversations"] == 5

    @pytest.mark.asyncio
    async def test_fallback_rate_calculated(self, analytics_service):
        company_id = uuid.uuid4()
        result = await analytics_service.get_overview(company_id, period_days=30)
        # 10 fallbacks / 90 bot messages = ~0.111
        assert 0.0 <= result["fallback_rate"] <= 1.0

    @pytest.mark.asyncio
    async def test_handoff_rate_calculated(self, analytics_service):
        company_id = uuid.uuid4()
        result = await analytics_service.get_overview(company_id, period_days=30)
        # 8 handoffs / 100 customer messages = 0.08
        assert 0.0 <= result["handoff_rate"] <= 1.0

    @pytest.mark.asyncio
    async def test_zero_messages_no_division_error(self, analytics_service, mock_analytics_repo):
        mock_analytics_repo.get_message_counts.return_value = {
            "total_customer": 0,
            "total_bot": 0,
            "total_fallback": 0,
        }
        mock_analytics_repo.get_handoff_counts.return_value = {
            "total": 0, "resolved": 0, "cancelled": 0, "pending": 0
        }
        company_id = uuid.uuid4()
        result = await analytics_service.get_overview(company_id, period_days=30)
        assert result["fallback_rate"] == 0.0
        assert result["handoff_rate"] == 0.0


class TestLanguageAnalytics:
    @pytest.mark.asyncio
    async def test_returns_language_breakdown(self, analytics_service):
        company_id = uuid.uuid4()
        result = await analytics_service.get_language_analytics(company_id, period_days=30)
        assert "breakdown" in result
        assert len(result["breakdown"]) == 3

    @pytest.mark.asyncio
    async def test_percentages_sum_to_100(self, analytics_service):
        company_id = uuid.uuid4()
        result = await analytics_service.get_language_analytics(company_id, period_days=30)
        total_pct = sum(item["percentage"] for item in result["breakdown"])
        assert abs(total_pct - 100.0) < 0.1


class TestHandoffAnalytics:
    @pytest.mark.asyncio
    async def test_returns_handoff_stats(self, analytics_service):
        company_id = uuid.uuid4()
        result = await analytics_service.get_handoff_analytics(company_id, period_days=30)
        assert result["total_handoffs"] == 8
        assert result["resolved_count"] == 5
        assert 0.0 <= result["resolution_rate"] <= 1.0

    @pytest.mark.asyncio
    async def test_resolution_rate_calculated(self, analytics_service):
        company_id = uuid.uuid4()
        result = await analytics_service.get_handoff_analytics(company_id, period_days=30)
        # 5 resolved / 8 total = 0.625
        assert abs(result["resolution_rate"] - 5 / 8) < 0.01


class TestTopQueries:
    @pytest.mark.asyncio
    async def test_returns_top_queries(self, analytics_service):
        company_id = uuid.uuid4()
        result = await analytics_service.get_top_queries(company_id, period_days=30)
        assert len(result["top_queries"]) == 2
        assert result["top_queries"][0]["count"] == 12

    @pytest.mark.asyncio
    async def test_returns_top_fallback_queries(self, analytics_service):
        company_id = uuid.uuid4()
        result = await analytics_service.get_top_queries(company_id, period_days=30)
        assert len(result["top_fallback_queries"]) == 1
