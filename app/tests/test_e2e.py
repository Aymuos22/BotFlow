"""
End-to-end style tests (Twilio webhooks).

These tests use the full HTTP client with:
  - Real in-memory SQLite DB
  - Mocked external services (Weaviate, S3, LLM, Twilio HTTP)
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Must match ``CompanyConfig.twilio_whatsapp_number`` after onboard + DB patch in scenario A.
SAMPLE_TWILIO_WHATSAPP_TO = "whatsapp:+14155238886"


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


def _twilio_httpx_mock():
    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.status_code = 201
    mock_response.json.return_value = {"sid": "SM123", "status": "queued"}
    mock_httpx = AsyncMock()
    mock_httpx.__aenter__ = AsyncMock(return_value=mock_httpx)
    mock_httpx.__aexit__ = AsyncMock(return_value=False)
    mock_httpx.post = AsyncMock(return_value=mock_response)
    return mock_httpx


# ──────────────────────────────────────────────────────────────────────────────
# Scenario A: Onboarding → Upload → Index → Webhook → Bot reply
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.api
async def test_e2e_onboard_upload_index_webhook_bot_reply(
    client,
    mock_weaviate_client,
    mock_storage_client,
    mock_llm_client,
    db_session,
):
    """
    Full happy path from company onboarding to receiving a RAG answer.
    """
    from sqlalchemy import select
    from app.models.company_config import CompanyConfig

    onboard_resp = await client.post(
        "/api/v1/onboarding/company/full",
        json={
            "company_name": f"e2e-company-{uuid.uuid4().hex[:8]}",
            "display_name": "E2E Test Company",
            "phone_number": "+911111111111",
            "default_language": "english",
            "supported_languages": ["english"],
        },
    )
    assert onboard_resp.status_code == 201
    company_id = onboard_resp.json()["data"]["company"]["id"]
    company_uuid = uuid.UUID(company_id)

    result = await db_session.execute(
        select(CompanyConfig).where(CompanyConfig.company_id == company_uuid)
    )
    cfg = result.scalar_one()
    cfg.twilio_whatsapp_number = SAMPLE_TWILIO_WHATSAPP_TO
    cfg.twilio_account_sid = "AC" + "1" * 32
    cfg.twilio_auth_token = "e2e-token"
    await db_session.flush()

    mock_storage_client.upload_file.return_value = f"companies/{company_id}/documents/d1/test.txt"
    upload_resp = await client.post(
        f"/api/v1/companies/{company_id}/documents/upload",
        files={"file": ("knowledge.txt", b"Our return policy is 30 days.", "text/plain")},
    )
    assert upload_resp.status_code == 201

    mock_weaviate_client.hybrid_search.return_value = {
        "chunks": ["Our return policy is 30 days."],
        "top_score": 0.92,
        "raw": {},
    }
    mock_llm_client.generate_answer.return_value = "Our return policy is 30 days."
    mock_httpx = _twilio_httpx_mock()

    with patch("httpx.AsyncClient", return_value=mock_httpx):
        webhook_resp = await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(
                to_number=SAMPLE_TWILIO_WHATSAPP_TO,
                from_number="whatsapp:+911111111111",
                body="What is your return policy?",
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert webhook_resp.status_code == 200

    mock_httpx.post.assert_called_once()

    from app.models.message import Message
    msgs = (await db_session.execute(
        select(Message).where(Message.company_id == company_uuid)
    )).scalars().all()
    assert any(m.sender_type == "customer" for m in msgs)
    assert any(m.sender_type == "bot" for m in msgs)


# ──────────────────────────────────────────────────────────────────────────────
# Scenario B: Low-confidence → fallback
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.api
async def test_e2e_low_confidence_returns_fallback(
    client,
    sample_company_id,
    mock_weaviate_client,
    mock_llm_client,
    db_session,
):
    """Low-confidence search → bot sends fallback, LLM not called."""
    mock_weaviate_client.hybrid_search.return_value = {
        "chunks": [],
        "top_score": None,
        "raw": {},
    }
    mock_llm_client.generate_answer.reset_mock()
    mock_httpx = _twilio_httpx_mock()

    with patch("httpx.AsyncClient", return_value=mock_httpx):
        await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(
                to_number=SAMPLE_TWILIO_WHATSAPP_TO,
                from_number="whatsapp:+911234567890",
                body="xyzzy random gibberish query",
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    mock_httpx.post.assert_called_once()
    mock_llm_client.generate_answer.assert_not_called()

    from app.models.message import Message
    from sqlalchemy import select
    msgs = (await db_session.execute(
        select(Message).where(
            Message.company_id == sample_company_id,
            Message.sender_type == "bot",
        )
    )).scalars().all()
    assert any(m.response_type == "fallback" for m in msgs)


# ──────────────────────────────────────────────────────────────────────────────
# Scenario C: Human keyword → handoff
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.api
async def test_e2e_human_keyword_creates_handoff(
    client,
    sample_company_id,
    db_session,
):
    """Sending 'agent please' keyword → handoff created, ack sent."""
    mock_httpx = _twilio_httpx_mock()
    with patch("httpx.AsyncClient", return_value=mock_httpx):
        resp = await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(
                to_number=SAMPLE_TWILIO_WHATSAPP_TO,
                body="Please connect me to a human agent",
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert resp.status_code == 200

    from app.models.handoff import Handoff
    from sqlalchemy import select
    handoffs = (await db_session.execute(
        select(Handoff).where(Handoff.company_id == sample_company_id)
    )).scalars().all()
    assert len(handoffs) >= 1
    mock_httpx.post.assert_called()


# ──────────────────────────────────────────────────────────────────────────────
# Scenario D: Agent reply flow
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.api
async def test_e2e_agent_reply_flow(
    client,
    sample_company_id,
    db_session,
):
    """
    Trigger handoff → agent sends message → verify stored + sent.
    """
    from app.models.conversation import Conversation
    from app.models.base import new_uuid

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919555555555",
        current_mode="agent",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()

    mock_httpx = _twilio_httpx_mock()
    with patch("httpx.AsyncClient", return_value=mock_httpx):
        resp = await client.post(
            f"/api/v1/conversations/{conv.id}/messages/agent",
            json={
                "message_text": "Hi, I am your human agent. How can I help you?",
                "agent_id": "agent-007",
            },
        )
    assert resp.status_code == 201

    from app.models.message import Message
    from sqlalchemy import select
    agent_msgs = (await db_session.execute(
        select(Message).where(
            Message.conversation_id == conv.id,
            Message.sender_type == "agent",
        )
    )).scalars().all()
    assert len(agent_msgs) == 1

    mock_httpx.post.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# Scenario E: Resume bot
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.api
async def test_e2e_resume_bot_after_handoff(
    client,
    sample_company_id,
    mock_weaviate_client,
    mock_llm_client,
    db_session,
):
    """
    After resume-bot, the bot should auto-reply again.
    """
    from app.models.conversation import Conversation
    from app.models.base import new_uuid
    from sqlalchemy import select

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919666666666",
        current_mode="agent",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()

    resp = await client.post(f"/api/v1/conversations/{conv.id}/resume-bot")
    assert resp.status_code == 200

    result = await db_session.execute(
        select(Conversation).where(Conversation.id == conv.id)
    )
    updated = result.scalar_one()
    assert updated.current_mode == "bot"

    mock_weaviate_client.hybrid_search.return_value = {
        "chunks": ["Policy answer here"],
        "top_score": 0.88,
        "raw": {},
    }
    mock_llm_client.generate_answer.return_value = "Policy answer here"
    mock_httpx = _twilio_httpx_mock()

    with patch("httpx.AsyncClient", return_value=mock_httpx):
        webhook_resp = await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(
                to_number=SAMPLE_TWILIO_WHATSAPP_TO,
                from_number="whatsapp:+919666666666",
                body="What is the return policy?",
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert webhook_resp.status_code == 200
    mock_httpx.post.assert_called()
