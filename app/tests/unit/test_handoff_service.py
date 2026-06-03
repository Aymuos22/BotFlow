"""
Unit tests for HandoffService.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _now():
    return datetime.now(timezone.utc)


def _conversation(mode="bot", **kwargs):
    return MagicMock(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        customer_phone="+911234567890",
        current_mode=mode,
        status="active",
        detected_language="english",
        created_at=_now(),
        updated_at=_now(),
    )


def _handoff(status="requested", **kwargs):
    return MagicMock(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        requested_by=kwargs.get("requested_by", "customer"),
        reason=kwargs.get("reason", "keyword_detected"),
        status=status,
        assigned_agent_id=kwargs.get("assigned_agent_id", None),
        resolved_at=None,
        created_at=_now(),
        updated_at=_now(),
    )


@pytest.fixture
def mock_handoff_repo():
    return AsyncMock()


@pytest.fixture
def mock_conv_repo():
    return AsyncMock()


@pytest.fixture
def mock_msg_repo():
    return AsyncMock()


@pytest.fixture
def mock_company_config_repo():
    m = AsyncMock()
    m.get_by_company.return_value = None
    return m


@pytest.fixture
def mock_company_repo():
    return AsyncMock()


@pytest.fixture
def handoff_service(
    mock_handoff_repo,
    mock_conv_repo,
    mock_msg_repo,
    mock_company_config_repo,
    mock_company_repo,
):
    from app.services.handoff_service import HandoffService
    return HandoffService(
        handoff_repo=mock_handoff_repo,
        conversation_repo=mock_conv_repo,
        message_repo=mock_msg_repo,
        company_config_repo=mock_company_config_repo,
        company_repo=mock_company_repo,
    )


class TestRequestHandoff:
    @pytest.mark.asyncio
    async def test_creates_handoff_and_sets_agent_mode(
        self, handoff_service, mock_handoff_repo, mock_conv_repo, mock_company_config_repo
    ):
        conv = _conversation(mode="bot")
        handoff = _handoff()
        # No active handoff exists
        mock_handoff_repo.get_active_for_conversation.return_value = None
        mock_handoff_repo.create.return_value = handoff
        mock_conv_repo.update.return_value = conv

        result = await handoff_service.request_handoff(
            company_id=conv.company_id,
            conversation=conv,
            reason="keyword_detected",
            requested_by="customer",
        )

        assert result is handoff
        mock_handoff_repo.create.assert_called_once()
        mock_conv_repo.update.assert_called_once()
        # Verify conversation mode was updated to "agent"
        update_kwargs = mock_conv_repo.update.call_args
        data = update_kwargs[0][1] if update_kwargs[0] else update_kwargs[1].get("data", {})
        assert data.get("current_mode") == "agent"
        mock_company_config_repo.get_by_company.assert_called_once_with(
            conv.company_id
        )

    @pytest.mark.asyncio
    async def test_new_handoff_sends_staff_whatsapp_when_configured(
        self,
        handoff_service,
        mock_handoff_repo,
        mock_conv_repo,
        mock_company_config_repo,
        mock_company_repo,
    ):
        conv = _conversation(mode="bot")
        handoff = _handoff()
        cfg = MagicMock()
        cfg.whatsapp_provider = "twilio"
        cfg.handoff_staff_notify_whatsapp = "whatsapp:+15550001111"
        cfg.twilio_account_sid = "ACxxxxxxxx"
        cfg.twilio_auth_token = "token"
        cfg.twilio_whatsapp_number = "whatsapp:+15550002222"
        mock_company_config_repo.get_by_company.return_value = cfg
        mock_company_repo.get.return_value = MagicMock(display_name="Acme Ltd")
        mock_handoff_repo.get_active_for_conversation.return_value = None
        mock_handoff_repo.create.return_value = handoff
        mock_conv_repo.update.return_value = conv

        with patch(
            "app.services.handoff_service.send_company_whatsapp_text_best_effort",
            new_callable=AsyncMock,
        ) as send_wa:
            await handoff_service.request_handoff(
                company_id=conv.company_id,
                conversation=conv,
                reason="keyword_detected",
                requested_by="customer",
            )

        send_wa.assert_awaited_once()
        kwargs = send_wa.await_args.kwargs
        assert kwargs["to_number"] == "whatsapp:+15550001111"
        body = kwargs["text"]
        assert "Acme Ltd" in body
        assert "+911234567890" in body
        assert "keyword_detected" in body

    @pytest.mark.asyncio
    async def test_duplicate_handoff_returns_existing(
        self, handoff_service, mock_handoff_repo, mock_conv_repo, mock_company_config_repo
    ):
        """If an active handoff already exists, return it without creating a new one."""
        conv = _conversation(mode="agent")
        existing = _handoff(status="requested")
        mock_handoff_repo.get_active_for_conversation.return_value = existing

        result = await handoff_service.request_handoff(
            company_id=conv.company_id,
            conversation=conv,
            reason="test",
            requested_by="customer",
        )

        assert result is existing
        mock_handoff_repo.create.assert_not_called()
        mock_company_config_repo.get_by_company.assert_not_called()


class TestAssignHandoff:
    @pytest.mark.asyncio
    async def test_assigns_agent_to_handoff(
        self, handoff_service, mock_handoff_repo
    ):
        handoff = _handoff(status="requested")
        updated = _handoff(status="assigned", assigned_agent_id="agent-001")
        mock_handoff_repo.update.return_value = updated

        result = await handoff_service.assign_handoff(handoff, "agent-001")

        assert result is updated
        mock_handoff_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_cannot_assign_resolved_handoff(
        self, handoff_service, mock_handoff_repo
    ):
        from app.core.exceptions import ValidationError
        handoff = _handoff(status="resolved")

        with pytest.raises((ValidationError, ValueError)):
            await handoff_service.assign_handoff(handoff, "agent-001")


class TestResolveHandoff:
    @pytest.mark.asyncio
    async def test_resolves_active_handoff(
        self, handoff_service, mock_handoff_repo
    ):
        handoff = _handoff(status="active")
        resolved = _handoff(status="resolved")
        mock_handoff_repo.update.return_value = resolved

        result = await handoff_service.resolve_handoff(handoff)

        assert result is resolved
        mock_handoff_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_sets_resolved_at(
        self, handoff_service, mock_handoff_repo
    ):
        handoff = _handoff(status="assigned")
        mock_handoff_repo.update.return_value = _handoff(status="resolved")

        await handoff_service.resolve_handoff(handoff)

        call_data = mock_handoff_repo.update.call_args[0][1]
        assert call_data.get("resolved_at") is not None


class TestResumeBot:
    @pytest.mark.asyncio
    async def test_sets_conversation_mode_to_bot(
        self, handoff_service, mock_conv_repo
    ):
        conv = _conversation(mode="agent")
        mock_conv_repo.update.return_value = conv

        await handoff_service.resume_bot(conv)

        mock_conv_repo.update.assert_called_once()
        data = mock_conv_repo.update.call_args[0][1]
        assert data.get("current_mode") == "bot"
