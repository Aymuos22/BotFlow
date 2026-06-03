"""
API tests for company management endpoints.

Covers:
  GET  /api/v1/companies/{id}/readiness
  POST /api/v1/companies/{id}/activate
  GET  /api/v1/companies/{id}/config
  PUT  /api/v1/companies/{id}/config
  PATCH /api/v1/companies/{id}/status
"""
import uuid as uuid_lib

import pytest
from sqlalchemy import select

from app.models.company_config import CompanyConfig

ONBOARD_BASE = "/api/v1/onboarding/company/full"


async def _onboard(client, payload) -> dict:
    """Helper: onboard a company and return the summary dict."""
    r = await client.post(ONBOARD_BASE, json=payload)
    assert r.status_code == 201, r.text
    return r.json()["data"]


@pytest.mark.api
class TestReadinessEndpoint:
    """GET /api/v1/companies/{id}/readiness"""

    async def test_returns_200_for_existing_company(
        self, client, valid_onboarding_payload
    ):
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        r = await client.get(f"/api/v1/companies/{company_id}/readiness")
        assert r.status_code == 200

    async def test_response_structure(self, client, valid_onboarding_payload):
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        data = (await client.get(f"/api/v1/companies/{company_id}/readiness")).json()["data"]
        assert "company_id" in data
        assert "onboarding_status" in data
        assert "is_ready_to_activate" in data
        assert "blocking_reasons" in data

    async def test_returns_404_for_unknown_company(self, client):
        r = await client.get("/api/v1/companies/00000000-0000-0000-0000-000000000000/readiness")
        assert r.status_code == 404

    async def test_twilio_not_configured_blocks_activation(
        self, client, valid_onboarding_payload
    ):
        """After onboarding, Twilio credentials are unset → not ready."""
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        data = (await client.get(f"/api/v1/companies/{company_id}/readiness")).json()["data"]
        assert data["onboarding_status"]["twilio_configured"] is False
        assert data["is_ready_to_activate"] is False
        assert len(data["blocking_reasons"]) > 0


@pytest.mark.api
class TestActivationEndpoint:
    """POST /api/v1/companies/{id}/activate"""

    async def test_activation_fails_when_not_ready(
        self, client, valid_onboarding_payload
    ):
        """Company cannot be activated until all gates pass."""
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        r = await client.post(f"/api/v1/companies/{company_id}/activate")
        assert r.status_code == 412  # precondition failed

    async def test_activation_returns_404_for_unknown_company(self, client):
        r = await client.post(
            "/api/v1/companies/00000000-0000-0000-0000-000000000000/activate"
        )
        assert r.status_code == 404

    async def test_activation_response_structure(
        self, client, valid_onboarding_payload, db_session
    ):
        """Force all gates to pass via DB update and verify activation works."""
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        company_uuid = uuid_lib.UUID(company_id)

        result = await db_session.execute(
            select(CompanyConfig).where(CompanyConfig.company_id == company_uuid)
        )
        cfg = result.scalar_one()
        cfg.twilio_whatsapp_number = "whatsapp:+14155238886"
        cfg.twilio_account_sid = "AC" + "1" * 32
        cfg.twilio_auth_token = "tenant-token"
        await db_session.flush()

        r = await client.post(f"/api/v1/companies/{company_id}/activate")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["activated"] is True
        assert data["company_id"] == company_id


@pytest.mark.api
class TestCompanyConfigEndpoints:
    """GET and PUT /api/v1/companies/{id}/config"""

    async def test_get_config_returns_200(self, client, valid_onboarding_payload):
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        r = await client.get(f"/api/v1/companies/{company_id}/config")
        assert r.status_code == 200

    async def test_get_config_body(self, client, valid_onboarding_payload):
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        data = (await client.get(f"/api/v1/companies/{company_id}/config")).json()["data"]
        assert data["company_id"] == company_id
        assert "weaviate_collection" in data
        assert "whatsapp_provider" in data
        assert data["whatsapp_provider"] == "twilio"
        assert "default_language" in data

    async def test_get_config_returns_404_for_unknown_company(self, client):
        r = await client.get(
            "/api/v1/companies/00000000-0000-0000-0000-000000000000/config"
        )
        assert r.status_code == 404

    async def test_put_config_updates_language(self, client, valid_onboarding_payload):
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        r = await client.put(
            f"/api/v1/companies/{company_id}/config",
            json={
                "default_language": "hindi",
                "supported_languages": ["hindi", "english"],
            },
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["default_language"] == "hindi"
        assert "hindi" in data["supported_languages"]

    async def test_put_config_invalid_language_returns_422(
        self, client, valid_onboarding_payload
    ):
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        r = await client.put(
            f"/api/v1/companies/{company_id}/config",
            json={"supported_languages": ["martian"]},
        )
        assert r.status_code == 422

    async def test_put_config_default_must_be_in_supported(
        self, client, valid_onboarding_payload
    ):
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        r = await client.put(
            f"/api/v1/companies/{company_id}/config",
            json={
                "default_language": "hindi",
                "supported_languages": ["english"],
            },
        )
        assert r.status_code == 422

    async def test_put_config_returns_404_for_unknown_company(self, client):
        r = await client.put(
            "/api/v1/companies/00000000-0000-0000-0000-000000000000/config",
            json={"default_language": "english"},
        )
        assert r.status_code == 404


@pytest.mark.api
class TestCompanyStatusEndpoint:
    """PATCH /api/v1/companies/{id}/status"""

    async def test_patch_status_to_inactive(self, client, valid_onboarding_payload):
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        r = await client.patch(
            f"/api/v1/companies/{company_id}/status",
            json={"status": "inactive"},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "inactive"

    async def test_patch_status_invalid_value_returns_422(
        self, client, valid_onboarding_payload
    ):
        summary = await _onboard(client, valid_onboarding_payload)
        company_id = summary["company"]["id"]
        r = await client.patch(
            f"/api/v1/companies/{company_id}/status",
            json={"status": "flying"},
        )
        assert r.status_code == 422

    async def test_patch_status_returns_404_for_unknown(self, client):
        r = await client.patch(
            "/api/v1/companies/00000000-0000-0000-0000-000000000000/status",
            json={"status": "inactive"},
        )
        assert r.status_code == 404
