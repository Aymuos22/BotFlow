"""
Webhook tests for human escalation paths (Twilio).

Covers:
- Human-keyword in message → handoff triggered
- Low-confidence RAG + company escalation config → handoff triggered
- Low-confidence without escalation config → simple fallback (no handoff)
- Conversation already in agent mode → no RAG, message stored
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
# Human keyword → handoff
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.api
async def test_human_keyword_triggers_handoff(
    client,
    sample_company_id,
    sample_twilio_to,
    db_session,
):
    """Saying 'agent please' should create a handoff and switch conv to agent mode."""
    from sqlalchemy import select
    from app.models.handoff import Handoff
    from app.models.conversation import Conversation

    mock_httpx = _twilio_httpx_mock()
    with patch("httpx.AsyncClient", return_value=mock_httpx):
        response = await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(
                to_number=sample_twilio_to,
                body="agent please, I need help from a real person",
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert response.status_code == 200

    result = await db_session.execute(
        select(Handoff).where(Handoff.company_id == sample_company_id)
    )
    handoffs = result.scalars().all()
    assert len(handoffs) >= 1
    assert handoffs[0].requested_by == "customer"

    result = await db_session.execute(
        select(Conversation).where(Conversation.company_id == sample_company_id)
    )
    convs = result.scalars().all()
    assert any(c.current_mode == "agent" for c in convs)


@pytest.mark.asyncio
@pytest.mark.api
async def test_human_keyword_sends_acknowledgement(
    client,
    sample_company_id,
    sample_twilio_to,
):
    """Handoff acknowledgement must be sent via Twilio outbound API."""
    mock_httpx = _twilio_httpx_mock()
    with patch("httpx.AsyncClient", return_value=mock_httpx):
        await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(
                to_number=sample_twilio_to,
                body="talk to human please",
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    mock_httpx.post.assert_called()


@pytest.mark.asyncio
@pytest.mark.api
async def test_human_keyword_no_rag_runs(
    client,
    sample_twilio_to,
    mock_weaviate_client,
):
    """When handoff is triggered by keyword, Weaviate search must NOT run."""
    mock_weaviate_client.hybrid_search.reset_mock()

    mock_httpx = _twilio_httpx_mock()
    with patch("httpx.AsyncClient", return_value=mock_httpx):
        await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(
                to_number=sample_twilio_to,
                body="agent please",
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    mock_weaviate_client.hybrid_search.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# Low-confidence → handoff (with escalation config enabled)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.api
async def test_low_confidence_with_escalation_config_triggers_handoff(
    client,
    sample_company_id,
    sample_twilio_to,
    mock_weaviate_client,
    db_session,
):
    """Low score + company config handoff_on_low_confidence=true → handoff."""
    from sqlalchemy import select
    from app.models.company_config import CompanyConfig
    from app.models.handoff import Handoff

    result = await db_session.execute(
        select(CompanyConfig).where(CompanyConfig.company_id == sample_company_id)
    )
    cfg = result.scalar_one()
    cfg.handoff_config_json = {
        "handoff_on_low_confidence": True,
        "low_confidence_handoff_threshold": 0.5,
    }
    await db_session.flush()

    mock_weaviate_client.hybrid_search.return_value = {
        "chunks": ["weakly relevant chunk"],
        "top_score": 0.1,
        "raw": {},
    }
    mock_httpx = _twilio_httpx_mock()
    with patch("httpx.AsyncClient", return_value=mock_httpx):
        await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(
                to_number=sample_twilio_to,
                body="some obscure question with no good answer",
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    result = await db_session.execute(
        select(Handoff).where(Handoff.company_id == sample_company_id)
    )
    handoffs = result.scalars().all()
    low_conf_handoffs = [h for h in handoffs if h.reason and "low_confidence" in h.reason]
    assert len(low_conf_handoffs) >= 1


@pytest.mark.asyncio
@pytest.mark.api
async def test_low_confidence_without_escalation_returns_fallback_no_handoff(
    client,
    sample_company_id,
    sample_twilio_to,
    mock_weaviate_client,
    db_session,
):
    """Low score + handoff_on_low_confidence=false → fallback message, no handoff."""
    from sqlalchemy import select
    from app.models.company_config import CompanyConfig
    from app.models.handoff import Handoff

    result = await db_session.execute(
        select(CompanyConfig).where(CompanyConfig.company_id == sample_company_id)
    )
    cfg = result.scalar_one()
    cfg.handoff_config_json = {"handoff_on_low_confidence": False}
    await db_session.flush()

    mock_weaviate_client.hybrid_search.return_value = {
        "chunks": [],
        "top_score": None,
        "raw": {},
    }
    mock_httpx = _twilio_httpx_mock()
    with patch("httpx.AsyncClient", return_value=mock_httpx):
        await client.post(
            "/api/v1/webhooks/twilio/messages",
            data=_twilio_form(
                to_number=sample_twilio_to,
                body="completely random query xyz abc 123",
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    result = await db_session.execute(
        select(Handoff).where(Handoff.company_id == sample_company_id)
    )
    handoffs = result.scalars().all()
    assert len(handoffs) == 0
    mock_httpx.post.assert_called()
