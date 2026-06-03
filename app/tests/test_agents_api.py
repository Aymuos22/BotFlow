"""
API tests for Agent endpoints.

GET  /api/v1/agents/{agent_id}/conversations
POST /api/v1/conversations/{conversation_id}/messages/agent
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
@pytest.mark.api
async def test_agent_conversations_empty(client):
    """Agent with no conversations returns empty list."""
    response = await client.get("/api/v1/agents/agent-007/conversations")
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
@pytest.mark.api
async def test_agent_conversations_returns_assigned(
    client, sample_company_id, db_session
):
    """Agent should see conversations they are assigned to via handoffs."""
    from app.models.conversation import Conversation
    from app.models.handoff import Handoff
    from app.models.base import new_uuid

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919111111111",
        current_mode="agent",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()

    handoff = Handoff(
        id=new_uuid(),
        company_id=sample_company_id,
        conversation_id=conv.id,
        requested_by="customer",
        reason="test",
        status="assigned",
        assigned_agent_id="agent-007",
    )
    db_session.add(handoff)
    await db_session.flush()

    response = await client.get("/api/v1/agents/agent-007/conversations")
    assert response.status_code == 200
    data = response.json()["data"]
    assert any(c["id"] == str(conv.id) for c in data)


@pytest.mark.asyncio
@pytest.mark.api
async def test_agent_send_message_success(
    client, sample_company_id, db_session
):
    """Agent can send a message in an agent-mode conversation."""
    from app.models.conversation import Conversation
    from app.models.base import new_uuid

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919222222222",
        current_mode="agent",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()

    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.status_code = 201
    mock_response.json.return_value = {"sid": "SM123", "status": "queued"}
    mock_httpx = AsyncMock()
    mock_httpx.__aenter__ = AsyncMock(return_value=mock_httpx)
    mock_httpx.__aexit__ = AsyncMock(return_value=False)
    mock_httpx.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_httpx):
        response = await client.post(
            f"/api/v1/conversations/{conv.id}/messages/agent",
            json={"message_text": "Hi, this is your support agent!", "agent_id": "agent-007"},
        )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["sender_type"] == "agent"
    assert data["message_text"] == "Hi, this is your support agent!"


@pytest.mark.asyncio
@pytest.mark.api
async def test_agent_message_stored_in_db(
    client, sample_company_id, db_session
):
    """Agent message should persist in the messages table."""
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.base import new_uuid
    from sqlalchemy import select

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919333333333",
        current_mode="agent",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()

    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.status_code = 201
    mock_response.json.return_value = {}
    mock_httpx = AsyncMock()
    mock_httpx.__aenter__ = AsyncMock(return_value=mock_httpx)
    mock_httpx.__aexit__ = AsyncMock(return_value=False)
    mock_httpx.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_httpx):
        await client.post(
            f"/api/v1/conversations/{conv.id}/messages/agent",
            json={"message_text": "Agent message here.", "agent_id": "agent-007"},
        )

    result = await db_session.execute(
        select(Message).where(
            Message.conversation_id == conv.id,
            Message.sender_type == "agent",
        )
    )
    msgs = result.scalars().all()
    assert len(msgs) >= 1
    assert msgs[0].message_text == "Agent message here."


@pytest.mark.asyncio
@pytest.mark.api
async def test_agent_message_sends_via_twilio(
    client, sample_company_id, db_session
):
    """Sending an agent message must call Twilio (httpx POST to Twilio API)."""
    from app.models.conversation import Conversation
    from app.models.base import new_uuid

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919444444444",
        current_mode="agent",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()

    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.status_code = 201
    mock_response.json.return_value = {}
    mock_httpx = AsyncMock()
    mock_httpx.__aenter__ = AsyncMock(return_value=mock_httpx)
    mock_httpx.__aexit__ = AsyncMock(return_value=False)
    mock_httpx.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_httpx):
        await client.post(
            f"/api/v1/conversations/{conv.id}/messages/agent",
            json={"message_text": "Hello from agent.", "agent_id": "agent-007"},
        )

    mock_httpx.post.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.api
async def test_agent_message_to_unknown_conversation_returns_404(client):
    response = await client.post(
        f"/api/v1/conversations/{uuid.uuid4()}/messages/agent",
        json={"message_text": "Hello.", "agent_id": "agent-007"},
    )
    assert response.status_code == 404
