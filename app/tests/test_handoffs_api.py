"""
API tests for the Handoff endpoints.

POST /api/v1/conversations/{conversation_id}/handoff
GET  /api/v1/companies/{company_id}/handoffs
POST /api/v1/handoffs/{handoff_id}/assign
POST /api/v1/handoffs/{handoff_id}/resolve
POST /api/v1/conversations/{conversation_id}/resume-bot
"""
import uuid
from datetime import datetime, timezone

import pytest


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

async def _create_conversation(client, company_id: uuid.UUID, phone="+919999999999") -> uuid.UUID:
    """Utility: create a conversation by sending a webhook."""
    from app.models.base import new_uuid
    return new_uuid()


# ──────────────────────────────────────────────────────────────────────────────
# Request handoff
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.api
async def test_request_handoff_success(
    client, sample_company_id, db_session
):
    """Create a conversation, then request handoff via API."""
    from app.models.conversation import Conversation
    from app.models.base import new_uuid

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919318492023",
        current_mode="bot",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/conversations/{conv.id}/handoff",
        json={"reason": "Customer requested human agent", "requested_by": "customer"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "requested"
    assert data["conversation_id"] == str(conv.id)


@pytest.mark.asyncio
@pytest.mark.api
async def test_request_handoff_unknown_conversation_returns_404(client):
    fake_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/conversations/{fake_id}/handoff",
        json={"reason": "test", "requested_by": "customer"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.api
async def test_request_handoff_sets_agent_mode(
    client, sample_company_id, db_session
):
    """After handoff request, conversation.current_mode should be 'agent'."""
    from app.models.conversation import Conversation
    from app.models.base import new_uuid
    from sqlalchemy import select

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919876543211",
        current_mode="bot",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()

    await client.post(
        f"/api/v1/conversations/{conv.id}/handoff",
        json={"reason": "test", "requested_by": "customer"},
    )

    result = await db_session.execute(
        select(Conversation).where(Conversation.id == conv.id)
    )
    updated_conv = result.scalar_one()
    assert updated_conv.current_mode == "agent"


# ──────────────────────────────────────────────────────────────────────────────
# List handoffs
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.api
async def test_list_handoffs_empty(client, sample_company_id):
    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/handoffs"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
@pytest.mark.api
async def test_list_handoffs_returns_company_handoffs(
    client, sample_company_id, db_session
):
    from app.models.conversation import Conversation
    from app.models.handoff import Handoff
    from app.models.base import new_uuid

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919876543212",
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
        reason="test handoff",
        status="requested",
    )
    db_session.add(handoff)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/companies/{sample_company_id}/handoffs"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1


# ──────────────────────────────────────────────────────────────────────────────
# Assign handoff
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.api
async def test_assign_handoff_success(client, sample_company_id, db_session):
    from app.models.conversation import Conversation
    from app.models.handoff import Handoff
    from app.models.base import new_uuid

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919876543213",
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
        status="requested",
    )
    db_session.add(handoff)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/handoffs/{handoff.id}/assign",
        json={"agent_id": "agent-007"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["assigned_agent_id"] == "agent-007"
    assert data["status"] == "assigned"


@pytest.mark.asyncio
@pytest.mark.api
async def test_assign_nonexistent_handoff_returns_404(client):
    response = await client.post(
        f"/api/v1/handoffs/{uuid.uuid4()}/assign",
        json={"agent_id": "agent-001"},
    )
    assert response.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# Resolve handoff
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.api
async def test_resolve_handoff_success(client, sample_company_id, db_session):
    from app.models.conversation import Conversation
    from app.models.handoff import Handoff
    from app.models.base import new_uuid

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919876543214",
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

    response = await client.post(
        f"/api/v1/handoffs/{handoff.id}/resolve",
        json={"resolution_note": "Issue resolved by agent."},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None


# ──────────────────────────────────────────────────────────────────────────────
# Resume bot
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.api
async def test_resume_bot_sets_bot_mode(client, sample_company_id, db_session):
    from app.models.conversation import Conversation
    from app.models.base import new_uuid
    from sqlalchemy import select

    conv = Conversation(
        id=new_uuid(),
        company_id=sample_company_id,
        customer_phone="+919876543215",
        current_mode="agent",
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/conversations/{conv.id}/resume-bot"
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(Conversation).where(Conversation.id == conv.id)
    )
    updated = result.scalar_one()
    assert updated.current_mode == "bot"


@pytest.mark.asyncio
@pytest.mark.api
async def test_resume_bot_unknown_conversation_returns_404(client):
    response = await client.post(
        f"/api/v1/conversations/{uuid.uuid4()}/resume-bot"
    )
    assert response.status_code == 404
