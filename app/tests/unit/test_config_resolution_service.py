"""
Unit tests for ConfigResolutionService.

Verifies that company config can be resolved both by company_id
and by channel session_name (reverse lookup via company_channels).
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError

_NOW = datetime.now(timezone.utc)


def _company(name="acme"):
    c = MagicMock()
    c.id = uuid.uuid4()
    c.name = name
    c.display_name = "Acme"
    c.status = "active"
    return c


def _config(company_id):
    cfg = MagicMock()
    cfg.id = uuid.uuid4()
    cfg.company_id = company_id
    cfg.weaviate_collection = "CoABC123"
    cfg.whatsapp_provider = "twilio"
    cfg.default_language = "english"
    cfg.supported_languages = ["english"]
    cfg.system_prompt = None
    cfg.rag_config_json = None
    cfg.fallback_config_json = None
    cfg.handoff_config_json = None
    cfg.business_hours_json = None
    cfg.is_active = True
    cfg.created_at = _NOW
    cfg.updated_at = _NOW
    return cfg


def _channel(company_id, session_name="twilio-abc123"):
    ch = MagicMock()
    ch.id = uuid.uuid4()
    ch.company_id = company_id
    ch.session_name = session_name
    ch.channel_type = "whatsapp"
    ch.phone_number = "+911234567890"
    return ch


@pytest.fixture
def repos():
    return {
        "company_repo": AsyncMock(),
        "config_repo": AsyncMock(),
        "channel_repo": AsyncMock(),
    }


@pytest.fixture
def resolution_service(repos):
    from app.services.config_resolution_service import ConfigResolutionService

    return ConfigResolutionService(
        company_repo=repos["company_repo"],
        config_repo=repos["config_repo"],
        channel_repo=repos["channel_repo"],
    )


@pytest.mark.unit
class TestResolveByCompanyId:
    async def test_returns_config_for_valid_company(self, resolution_service, repos):
        company = _company()
        repos["company_repo"].get.return_value = company
        repos["config_repo"].get_by_company.return_value = _config(company.id)

        result = await resolution_service.resolve_by_company_id(company.id)
        assert result is not None
        assert result.company_id == company.id

    async def test_raises_not_found_for_missing_company(self, resolution_service, repos):
        repos["company_repo"].get.return_value = None
        with pytest.raises(NotFoundError):
            await resolution_service.resolve_by_company_id(uuid.uuid4())

    async def test_raises_not_found_for_missing_config(self, resolution_service, repos):
        company = _company()
        repos["company_repo"].get.return_value = company
        repos["config_repo"].get_by_company.return_value = None
        with pytest.raises(NotFoundError):
            await resolution_service.resolve_by_company_id(company.id)


@pytest.mark.unit
class TestResolveBySessionName:
    async def test_returns_config_for_valid_session(self, resolution_service, repos):
        company = _company()
        session_name = "twilio-abc123"
        channel = _channel(company.id, session_name)
        config = _config(company.id)

        repos["channel_repo"].get_by_session_name.return_value = channel
        repos["company_repo"].get.return_value = company
        repos["config_repo"].get_by_company.return_value = config

        result = await resolution_service.resolve_by_session_name(session_name)
        assert result is not None
        assert result.company_id == company.id
        assert result.whatsapp_provider == "twilio"

    async def test_raises_not_found_for_unknown_session(self, resolution_service, repos):
        repos["channel_repo"].get_by_session_name.return_value = None
        with pytest.raises(NotFoundError):
            await resolution_service.resolve_by_session_name("twilio-unknown")

    async def test_raises_not_found_when_config_missing(self, resolution_service, repos):
        company = _company()
        channel = _channel(company.id, "twilio-abc")
        repos["channel_repo"].get_by_session_name.return_value = channel
        repos["company_repo"].get.return_value = company
        repos["config_repo"].get_by_company.return_value = None
        with pytest.raises(NotFoundError):
            await resolution_service.resolve_by_session_name("twilio-abc")
