"""
Unit tests for ConversationService.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


def _now():
    return datetime.now(timezone.utc)


def _conversation(**kwargs):
    return MagicMock(
        id=uuid.uuid4(),
        company_id=kwargs.get("company_id", uuid.uuid4()),
        customer_phone=kwargs.get("customer_phone", "+911234567890"),
        current_mode=kwargs.get("current_mode", "bot"),
        status=kwargs.get("status", "active"),
        detected_language=kwargs.get("detected_language", None),
        assigned_agent_id=None,
        last_message_at=None,
        created_at=_now(),
        updated_at=_now(),
    )


def _message(**kwargs):
    return MagicMock(
        id=uuid.uuid4(),
        conversation_id=kwargs.get("conversation_id", uuid.uuid4()),
        company_id=kwargs.get("company_id", uuid.uuid4()),
        sender_type=kwargs.get("sender_type", "customer"),
        message_text=kwargs.get("message_text", "Hello"),
        normalized_text=None,
        language=None,
        response_type=None,
        external_message_id=None,
        created_at=_now(),
    )


@pytest.fixture
def mock_conv_repo():
    return AsyncMock()


@pytest.fixture
def mock_msg_repo():
    return AsyncMock()


@pytest.fixture
def conv_service(mock_conv_repo, mock_msg_repo):
    from app.services.conversation_service import ConversationService
    return ConversationService(
        conversation_repo=mock_conv_repo,
        message_repo=mock_msg_repo,
    )


class TestCreateOrGetConversation:
    @pytest.mark.asyncio
    async def test_returns_existing_conversation(
        self, conv_service, mock_conv_repo
    ):
        company_id = uuid.uuid4()
        phone = "+911234567890"
        existing = _conversation(company_id=company_id, customer_phone=phone)
        mock_conv_repo.get_by_company_and_phone.return_value = existing

        result = await conv_service.create_or_get_conversation(company_id, phone)
        assert result is existing
        mock_conv_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new_when_not_found(
        self, conv_service, mock_conv_repo
    ):
        company_id = uuid.uuid4()
        phone = "+911234567890"
        mock_conv_repo.get_by_company_and_phone.return_value = None
        new_conv = _conversation(company_id=company_id, customer_phone=phone)
        mock_conv_repo.create.return_value = new_conv

        result = await conv_service.create_or_get_conversation(company_id, phone)
        assert result is new_conv
        mock_conv_repo.create.assert_called_once()


class TestAppendMessage:
    @pytest.mark.asyncio
    async def test_appends_customer_message(
        self, conv_service, mock_msg_repo, mock_conv_repo
    ):
        conv_id = uuid.uuid4()
        company_id = uuid.uuid4()
        msg = _message(conversation_id=conv_id, company_id=company_id)
        mock_msg_repo.create.return_value = msg
        mock_conv_repo.touch_last_message_at.return_value = None

        result = await conv_service.append_message(
            conversation_id=conv_id,
            company_id=company_id,
            sender_type="customer",
            message_text="Hello",
        )
        assert result is msg
        mock_msg_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_last_message_at(
        self, conv_service, mock_msg_repo, mock_conv_repo
    ):
        conv_id = uuid.uuid4()
        company_id = uuid.uuid4()
        mock_msg_repo.create.return_value = _message()
        mock_conv_repo.touch_last_message_at.return_value = None

        await conv_service.append_message(
            conversation_id=conv_id,
            company_id=company_id,
            sender_type="bot",
            message_text="I'm here to help!",
            response_type="rag",
        )
        mock_conv_repo.touch_last_message_at.assert_called_once()


class TestRefreshReplyLanguage:
    @pytest.mark.asyncio
    async def test_updates_on_strong_hindi_message(
        self, conv_service, mock_conv_repo
    ):
        conv = _conversation(detected_language=None)
        mock_conv_repo.update.return_value = conv

        await conv_service.refresh_reply_language_after_customer_message(
            conv, "मुझे मदद चाहिए"
        )
        mock_conv_repo.update.assert_called_once()
        assert conv.detected_language == "hindi"

    @pytest.mark.asyncio
    async def test_weak_message_does_not_overwrite_sticky(
        self, conv_service, mock_conv_repo
    ):
        conv = _conversation(detected_language="hindi")

        await conv_service.refresh_reply_language_after_customer_message(conv, "ok")
        mock_conv_repo.update.assert_not_called()
        assert conv.detected_language == "hindi"
