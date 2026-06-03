"""
API tests for the AiSensy WhatsApp webhook endpoint.

POST /api/v1/webhooks/aisensy/messages
"""

import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
@pytest.mark.api
async def test_aisensy_webhook_routes_flat_json_and_sends_reply(
    client,
    db_session,
    mock_weaviate_client,
    mock_llm_client,
):
    from app.models.base import new_uuid
    from app.models.company import Company
    from app.models.company_config import CompanyConfig

    company_id = new_uuid()
    biz = "whatsapp:+918888888888"
    cfg = CompanyConfig(
        company_id=company_id,
        weaviate_collection=f"Co{company_id.hex[:20]}",
        whatsapp_provider="aisensy",
        aisensy_whatsapp_number=biz,
        aisensy_project_id="test-project",
    )
    cfg.aisensy_api_key = "test-aisensy-key"
    db_session.add(Company(id=company_id, name="aco", display_name="ACO", status="active"))
    db_session.add(cfg)
    await db_session.commit()

    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_response.text = '{"success":true}'

    mock_httpx_client = AsyncMock()
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock(return_value=False)
    mock_httpx_client.post = AsyncMock(return_value=mock_response)

    payload = {
        "messageId": f"mid-{uuid.uuid4().hex[:12]}",
        "from": "919876543210",
        "to": "918888888888",
        "message": "Hi from customer",
    }

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        resp = await client.post(
            "/api/v1/webhooks/aisensy/messages",
            json=payload,
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
