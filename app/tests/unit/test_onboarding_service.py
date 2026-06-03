"""
Unit tests for OnboardingService.

External dependencies (repos, Weaviate client) are replaced with AsyncMocks.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, PreconditionFailedError

_NOW = datetime.now(timezone.utc)


def _company(name="acme", status="draft"):
    c = MagicMock()
    c.id = uuid.uuid4()
    c.name = name
    c.display_name = "Acme Corp"
    c.status = status
    c.created_at = _NOW
    c.updated_at = _NOW
    return c


def _config(company_id=None, *, twilio_ok: bool = False):
    cfg = MagicMock()
    cfg.id = uuid.uuid4()
    cfg.company_id = company_id or uuid.uuid4()
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
    if twilio_ok:
        cfg.twilio_whatsapp_number = "whatsapp:+14155238886"
        cfg.twilio_account_sid = "AC" + "x" * 32
        cfg.twilio_auth_token = "secret"
    else:
        cfg.twilio_whatsapp_number = None
        cfg.twilio_account_sid = None
        cfg.twilio_auth_token = None
    return cfg


def _channel():
    ch = MagicMock()
    ch.id = uuid.uuid4()
    ch.company_id = uuid.uuid4()
    ch.channel_type = "whatsapp"
    ch.phone_number = "+911234567890"
    ch.session_name = "twilio-abc1234567890123456"
    ch.is_primary = True
    ch.status = "pending"
    ch.created_at = _NOW
    return ch


def _onboarding(company_id=None, **kwargs):
    o = MagicMock()
    o.id = uuid.uuid4()
    o.company_id = company_id or uuid.uuid4()
    o.config_saved = kwargs.get("config_saved", False)
    o.weaviate_ready = kwargs.get("weaviate_ready", False)
    o.activated = kwargs.get("activated", False)
    o.last_error = None
    o.updated_at = _NOW
    return o


@pytest.fixture
def repos():
    return {
        "company_repo": AsyncMock(),
        "config_repo": AsyncMock(),
        "channel_repo": AsyncMock(),
        "onboarding_repo": AsyncMock(),
    }


@pytest.fixture
def weaviate_client():
    m = AsyncMock()
    m.create_collection.return_value = True
    return m


@pytest.fixture
def service(repos, weaviate_client):
    from app.services.onboarding_service import OnboardingService

    return OnboardingService(
        company_repo=repos["company_repo"],
        config_repo=repos["config_repo"],
        channel_repo=repos["channel_repo"],
        onboarding_repo=repos["onboarding_repo"],
        weaviate_client=weaviate_client,
    )


@pytest.mark.unit
class TestOnboardingServiceFullOnboard:
    async def test_calls_company_create(self, service, repos):
        from app.schemas.onboarding import FullOnboardingRequest

        company = _company()
        repos["company_repo"].get_by_name.return_value = None
        repos["channel_repo"].get_by_phone_number.return_value = None
        repos["company_repo"].create.return_value = company
        repos["config_repo"].create.return_value = _config(company.id)
        repos["channel_repo"].get_primary_by_company.return_value = None
        repos["channel_repo"].create.return_value = _channel()
        repos["onboarding_repo"].get_by_company.return_value = None
        repos["onboarding_repo"].create.return_value = _onboarding(company.id)
        repos["onboarding_repo"].update.return_value = _onboarding(
            company.id, config_saved=True, weaviate_ready=True
        )

        payload = FullOnboardingRequest(
            company_name="acme",
            display_name="Acme Corp",
            phone_number="+911234567890",
        )
        await service.full_onboard(payload)
        repos["company_repo"].create.assert_called_once()

    async def test_raises_conflict_for_duplicate_name(self, service, repos):
        from app.schemas.onboarding import FullOnboardingRequest

        repos["company_repo"].get_by_name.return_value = _company()
        payload = FullOnboardingRequest(
            company_name="acme",
            display_name="Acme Corp",
            phone_number="+911234567890",
        )
        with pytest.raises(ConflictError):
            await service.full_onboard(payload)

    async def test_weaviate_failure_sets_flag_false(self, service, repos, weaviate_client):
        from app.schemas.onboarding import FullOnboardingRequest

        company = _company()
        repos["company_repo"].get_by_name.return_value = None
        repos["channel_repo"].get_by_phone_number.return_value = None
        repos["company_repo"].create.return_value = company
        repos["config_repo"].create.return_value = _config(company.id)
        repos["channel_repo"].get_primary_by_company.return_value = None
        repos["channel_repo"].create.return_value = _channel()
        repos["onboarding_repo"].get_by_company.return_value = None
        repos["onboarding_repo"].create.return_value = _onboarding(company.id)
        repos["onboarding_repo"].update.return_value = _onboarding(
            company.id, config_saved=True, weaviate_ready=False
        )

        weaviate_client.create_collection.side_effect = Exception("Weaviate down")

        payload = FullOnboardingRequest(
            company_name="acme3",
            display_name="Acme Corp",
            phone_number="+911234567890",
        )
        summary = await service.full_onboard(payload)
        assert summary.onboarding_status.weaviate_ready is False


@pytest.mark.unit
class TestOnboardingServiceActivate:
    async def test_raises_precondition_when_not_ready(self, service, repos):
        company = _company()
        repos["company_repo"].get.return_value = company
        repos["onboarding_repo"].get_by_company.return_value = _onboarding(
            company.id, config_saved=True, weaviate_ready=True
        )
        repos["config_repo"].get_by_company.return_value = _config(company.id, twilio_ok=False)
        with pytest.raises(PreconditionFailedError):
            await service.activate_company(company.id)

    async def test_activates_when_all_gates_pass(self, service, repos):
        company = _company()
        repos["company_repo"].get.return_value = company
        repos["onboarding_repo"].get_by_company.return_value = _onboarding(
            company.id, config_saved=True, weaviate_ready=True
        )
        repos["config_repo"].get_by_company.return_value = _config(company.id, twilio_ok=True)
        repos["company_repo"].update.return_value = company
        repos["onboarding_repo"].update.return_value = MagicMock()

        result = await service.activate_company(company.id)
        assert result.activated is True
