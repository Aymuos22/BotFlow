"""
API tests for POST /api/v1/onboarding/company/full.

Covers:
  - Happy path: full onboarding creates all records
  - Duplicate company name → 409
  - Invalid phone number → 422
  - Unsupported language → 422
  - Weaviate failure is non-fatal
  - Idempotent collection / channel key naming
"""
import pytest

BASE = "/api/v1/onboarding/company/full"


@pytest.mark.api
class TestFullOnboarding:
    """POST /api/v1/onboarding/company/full"""

    async def test_happy_path_returns_201(self, client, valid_onboarding_payload):
        response = await client.post(BASE, json=valid_onboarding_payload)
        assert response.status_code == 201

    async def test_happy_path_response_structure(self, client, valid_onboarding_payload):
        response = await client.post(BASE, json=valid_onboarding_payload)
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        payload = data["data"]
        assert "company" in payload
        assert "config" in payload
        assert "channel" in payload
        assert "onboarding_status" in payload
        assert "next_steps" in payload

    async def test_company_row_created(self, client, valid_onboarding_payload):
        response = await client.post(BASE, json=valid_onboarding_payload)
        data = response.json()["data"]
        assert data["company"]["name"] == valid_onboarding_payload["company_name"]
        assert data["company"]["display_name"] == valid_onboarding_payload["display_name"]
        assert data["company"]["status"] == "draft"

    async def test_config_row_created(self, client, valid_onboarding_payload):
        response = await client.post(BASE, json=valid_onboarding_payload)
        data = response.json()["data"]
        config = data["config"]
        assert config["default_language"] == "english"
        assert isinstance(config["weaviate_collection"], str)
        assert len(config["weaviate_collection"]) > 0
        assert config["whatsapp_provider"] == "twilio"

    async def test_channel_row_created(self, client, valid_onboarding_payload):
        response = await client.post(BASE, json=valid_onboarding_payload)
        data = response.json()["data"]
        channel = data["channel"]
        assert channel["phone_number"] == valid_onboarding_payload["phone_number"]
        assert channel["channel_type"] == "whatsapp"
        assert channel["is_primary"] is True

    async def test_collection_name_starts_with_co(self, client, valid_onboarding_payload):
        """Weaviate collection name must satisfy naming rules (starts uppercase 'Co')."""
        response = await client.post(BASE, json=valid_onboarding_payload)
        data = response.json()["data"]
        assert data["config"]["weaviate_collection"].startswith("Co")

    async def test_channel_key_starts_with_twilio(self, client, valid_onboarding_payload):
        """Primary WhatsApp channel key uses the twilio- prefix."""
        response = await client.post(BASE, json=valid_onboarding_payload)
        data = response.json()["data"]
        assert data["channel"]["session_name"].startswith("twilio-")

    async def test_weaviate_client_create_collection_called(
        self, client, valid_onboarding_payload, mock_weaviate_client
    ):
        await client.post(BASE, json=valid_onboarding_payload)
        mock_weaviate_client.create_collection.assert_called_once()

    async def test_onboarding_status_twilio_not_configured_initially(
        self, client, valid_onboarding_payload
    ):
        response = await client.post(BASE, json=valid_onboarding_payload)
        data = response.json()["data"]
        assert data["onboarding_status"]["twilio_configured"] is False

    async def test_onboarding_status_weaviate_flag_set_on_success(
        self, client, valid_onboarding_payload
    ):
        response = await client.post(BASE, json=valid_onboarding_payload)
        data = response.json()["data"]
        assert data["onboarding_status"]["weaviate_ready"] is True

    async def test_next_steps_are_present(self, client, valid_onboarding_payload):
        response = await client.post(BASE, json=valid_onboarding_payload)
        data = response.json()["data"]
        assert isinstance(data["next_steps"], list)
        assert len(data["next_steps"]) > 0

    async def test_duplicate_company_name_returns_409(
        self, client, valid_onboarding_payload
    ):
        await client.post(BASE, json=valid_onboarding_payload)
        response2 = await client.post(BASE, json=valid_onboarding_payload)
        assert response2.status_code == 409

    async def test_invalid_phone_number_returns_422(
        self, client, valid_onboarding_payload
    ):
        payload = {**valid_onboarding_payload, "phone_number": "not-a-phone"}
        response = await client.post(BASE, json=payload)
        assert response.status_code == 422

    async def test_unsupported_language_returns_422(
        self, client, valid_onboarding_payload
    ):
        payload = {
            **valid_onboarding_payload,
            "supported_languages": ["klingon"],
        }
        response = await client.post(BASE, json=payload)
        assert response.status_code == 422

    async def test_default_language_must_be_in_supported(
        self, client, valid_onboarding_payload
    ):
        payload = {
            **valid_onboarding_payload,
            "company_name": "bad-default-lang-co",
            "default_language": "hindi",
            "supported_languages": ["english"],
        }
        response = await client.post(BASE, json=payload)
        assert response.status_code == 422

    async def test_missing_company_name_returns_422(self, client):
        response = await client.post(BASE, json={"phone_number": "+911234567890"})
        assert response.status_code == 422

    async def test_weaviate_failure_is_non_fatal(
        self, client, valid_onboarding_payload, mock_weaviate_client
    ):
        """If Weaviate errors, onboarding still returns success with flag=False."""
        mock_weaviate_client.create_collection.side_effect = Exception("Weaviate down")
        response = await client.post(BASE, json=valid_onboarding_payload)
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["onboarding_status"]["weaviate_ready"] is False

    async def test_onboarding_status_config_saved_is_true(
        self, client, valid_onboarding_payload
    ):
        response = await client.post(BASE, json=valid_onboarding_payload)
        data = response.json()["data"]
        assert data["onboarding_status"]["config_saved"] is True

    async def test_hindi_language_supported(self, client, valid_onboarding_payload):
        payload = {
            **valid_onboarding_payload,
            "company_name": "hindi-company",
            "default_language": "hindi",
            "supported_languages": ["hindi", "english"],
        }
        response = await client.post(BASE, json=payload)
        assert response.status_code == 201

    async def test_hinglish_language_supported(self, client, valid_onboarding_payload):
        payload = {
            **valid_onboarding_payload,
            "company_name": "hinglish-company",
            "default_language": "hinglish",
            "supported_languages": ["hinglish"],
        }
        response = await client.post(BASE, json=payload)
        assert response.status_code == 201
