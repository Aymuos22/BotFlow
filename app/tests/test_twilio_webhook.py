"""
API tests for the Twilio WhatsApp webhook endpoint.

POST /api/v1/webhooks/twilio/messages
"""

import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _twilio_form(
    *,
    to_number: str,
    from_number: str = "whatsapp:+911234567890",
    body: str = "Hello!",
    message_sid: str | None = None,
):
    return {
        "MessageSid": message_sid or f"SM{uuid.uuid4().hex[:30]}",
        "From": from_number,
        "To": to_number,
        "Body": body,
        "NumMedia": "0",
    }


@pytest.mark.asyncio
@pytest.mark.api
async def test_twilio_webhook_routes_by_to_and_sends_reply(
    client,
    db_session,
    mock_weaviate_client,
    mock_llm_client,
):
    """
    When a company has twilio_whatsapp_number set, inbound webhook To routes to that company
    and a reply is sent using that company's Twilio credentials.
    """
    from app.models.base import new_uuid
    from app.models.company import Company
    from app.models.company_config import CompanyConfig

    company_id = new_uuid()
    to_wa = "whatsapp:+14155238886"
    cfg = CompanyConfig(
        company_id=company_id,
        weaviate_collection=f"Co{company_id.hex[:20]}",
        whatsapp_provider="twilio",
        twilio_whatsapp_number=to_wa,
        twilio_account_sid="AC" + "1" * 32,
    )
    cfg.twilio_auth_token = "test-auth-token"
    db_session.add(Company(id=company_id, name="tco", display_name="TCO", status="active"))
    db_session.add(cfg)
    await db_session.commit()

    # Patch httpx.AsyncClient used inside TwilioClient to avoid real network calls.
    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.status_code = 201
    mock_response.json.return_value = {"sid": "SM123", "status": "queued"}
    mock_response.text = '{"sid":"SM123","status":"queued"}'

    mock_httpx_client = AsyncMock()
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock(return_value=False)
    mock_httpx_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        resp = await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(to_number=to_wa, body="Hi"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")


@pytest.mark.asyncio
@pytest.mark.api
async def test_twilio_webhook_signature_validation_blocks_invalid_signature(
    client,
    db_session,
):
    """
    With TWILIO_VALIDATE_SIGNATURE enabled, an invalid X-Twilio-Signature should be ACKed
    (200) but ignored (no outbound call attempt).
    """
    from app.core import config as app_config
    from app.models.base import new_uuid
    from app.models.company import Company
    from app.models.company_config import CompanyConfig

    s = app_config.settings
    old_validate = s.twilio_validate_signature
    try:
        s.twilio_validate_signature = True

        company_id = new_uuid()
        to_wa = "whatsapp:+14155238886"
        cfg = CompanyConfig(
            company_id=company_id,
            weaviate_collection=f"Co{company_id.hex[:20]}",
            whatsapp_provider="twilio",
            twilio_whatsapp_number=to_wa,
            twilio_account_sid="AC" + "2" * 32,
        )
        cfg.twilio_auth_token = "tenant-token"
        db_session.add(
            Company(id=company_id, name="tco2", display_name="TCO2", status="active")
        )
        db_session.add(cfg)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(to_number=to_wa, body="Hi"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Twilio-Signature": "definitely-wrong",
            },
        )
        assert resp.status_code == 200
    finally:
        s.twilio_validate_signature = old_validate


@pytest.mark.asyncio
@pytest.mark.api
async def test_twilio_webhook_signature_validation_accepts_valid_signature(
    client,
    db_session,
):
    """
    With TWILIO_VALIDATE_SIGNATURE enabled, a valid X-Twilio-Signature should allow processing.
    """
    from app.core import config as app_config
    from app.integrations.twilio.signature import compute_twilio_signature
    from app.models.base import new_uuid
    from app.models.company import Company
    from app.models.company_config import CompanyConfig

    s = app_config.settings
    old_validate = s.twilio_validate_signature
    try:
        s.twilio_validate_signature = True

        company_id = new_uuid()
        to_wa = "whatsapp:+14155238886"
        cfg = CompanyConfig(
            company_id=company_id,
            weaviate_collection=f"Co{company_id.hex[:20]}",
            whatsapp_provider="twilio",
            twilio_whatsapp_number=to_wa,
            twilio_account_sid="AC" + "3" * 32,
        )
        cfg.twilio_auth_token = "tenant-token"
        db_session.add(
            Company(id=company_id, name="tco3", display_name="TCO3", status="active")
        )
        db_session.add(cfg)
        await db_session.commit()

        form = _twilio_form(to_number=to_wa, body="Hi")
        url = "http://test/api/v1/webhooks/twilio/messages"
        sig = compute_twilio_signature(
            url=url,
            params={k: str(v) for k, v in form.items()},
            auth_token="tenant-token",
        )

        resp = await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Twilio-Signature": sig,
            },
        )
        assert resp.status_code == 200
    finally:
        s.twilio_validate_signature = old_validate

