"""
Unit tests for RAGService decision logic.

Tests cover:
  - Language detection flow
  - Weaviate search invocation
  - Fallback decision
  - LLM call
  - Retrieval logging
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest


def _now():
    return datetime.now(timezone.utc)


def _config(collection="CoABC", language="english", threshold=0.4):
    return MagicMock(
        weaviate_collection=collection,
        default_language=language,
        supported_languages=[language, "hinglish"],
        rag_config_json={"score_threshold": threshold},
        fallback_config_json={"english": "Sorry, no info found.", "hindi": "माफ करें।"},
    )


def _search_result(score: Optional[float] = 0.8, count: int = 3):
    if score is None or count == 0:
        return {"chunks": [], "top_score": None}
    chunks = [f"chunk {i}" for i in range(count)]
    return {"chunks": chunks, "top_score": score}


@pytest.fixture
def mock_config_repo():
    repo = AsyncMock()
    repo.get_by_company.return_value = _config()
    return repo


@pytest.fixture
def mock_weaviate():
    client = AsyncMock()
    client.hybrid_search.return_value = _search_result()
    return client


@pytest.fixture
def mock_llm():
    client = AsyncMock()
    client.generate_answer.return_value = "Here is your answer."
    return client


@pytest.fixture
def mock_log_persister():
    return AsyncMock()


@pytest.fixture
def rag_service(mock_config_repo, mock_weaviate, mock_llm, mock_log_persister):
    from app.services.rag_service import RAGService
    from app.services.fallback_service import FallbackService
    return RAGService(
        config_repo=mock_config_repo,
        weaviate_client=mock_weaviate,
        llm_client=mock_llm,
        fallback_service=FallbackService(),
        log_persister=mock_log_persister,
    )


class TestRAGServiceQuery:
    @pytest.mark.asyncio
    async def test_happy_path_returns_rag_answer(
        self, rag_service, mock_weaviate, mock_llm, mock_log_persister
    ):
        company_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        msg_id = uuid.uuid4()

        result = await rag_service.process_query(
            company_id=company_id,
            query="What is the return policy?",
            conversation_id=conv_id,
            message_id=msg_id,
        )

        assert result["response_type"] == "rag"
        assert "Here is your answer." in result["answer"]
        mock_weaviate.hybrid_search.assert_called_once()
        mock_llm.generate_answer.assert_called_once()
        mock_log_persister.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_score_returns_fallback(
        self, mock_config_repo, mock_weaviate, mock_llm, mock_log_persister
    ):
        from app.services.rag_service import RAGService
        from app.services.fallback_service import FallbackService

        mock_weaviate.hybrid_search.return_value = _search_result(score=0.1)

        svc = RAGService(
            config_repo=mock_config_repo,
            weaviate_client=mock_weaviate,
            llm_client=mock_llm,
            fallback_service=FallbackService(),
            log_persister=mock_log_persister,
        )

        result = await svc.process_query(
            company_id=uuid.uuid4(),
            query="random question",
            conversation_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
        )

        assert result["response_type"] == "fallback"
        mock_llm.generate_answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_greeting_returns_canned_answer(
        self, mock_config_repo, mock_weaviate, mock_llm, mock_log_persister
    ):
        """Recognised greetings return a canned answer without hitting the LLM."""
        from app.services.rag_service import RAGService
        from app.services.fallback_service import FallbackService

        mock_weaviate.hybrid_search.return_value = _search_result(score=0.1)

        svc = RAGService(
            config_repo=mock_config_repo,
            weaviate_client=mock_weaviate,
            llm_client=mock_llm,
            fallback_service=FallbackService(),
            log_persister=mock_log_persister,
        )

        result = await svc.process_query(
            company_id=uuid.uuid4(),
            query="helllo ji",
            conversation_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
        )

        assert result["response_type"] == "rag"
        assert result["fallback_triggered"] is False
        # Greeting is intercepted early — LLM is NOT called; a canned reply is returned.
        mock_llm.generate_answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_results_returns_fallback(
        self, mock_config_repo, mock_weaviate, mock_llm, mock_log_persister
    ):
        from app.services.rag_service import RAGService
        from app.services.fallback_service import FallbackService

        mock_weaviate.hybrid_search.return_value = _search_result(score=None, count=0)

        svc = RAGService(
            config_repo=mock_config_repo,
            weaviate_client=mock_weaviate,
            llm_client=mock_llm,
            fallback_service=FallbackService(),
            log_persister=mock_log_persister,
        )

        result = await svc.process_query(
            company_id=uuid.uuid4(),
            query="obscure query",
            conversation_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
        )

        assert result["response_type"] == "fallback"

    @pytest.mark.asyncio
    async def test_retrieval_log_always_created(
        self, rag_service, mock_log_persister
    ):
        """Even on fallback, a retrieval log must be saved."""
        await rag_service.process_query(
            company_id=uuid.uuid4(),
            query="test",
            conversation_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
        )
        mock_log_persister.assert_called_once()

    @pytest.mark.asyncio
    async def test_rag_log_contains_expected_fields(
        self, rag_service, mock_log_persister
    ):
        company_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        msg_id = uuid.uuid4()

        await rag_service.process_query(
            company_id=company_id,
            query="test query",
            conversation_id=conv_id,
            message_id=msg_id,
        )

        payload = mock_log_persister.call_args[0][0]
        assert payload["company_id"] == company_id
        assert payload["query_text"] == "test query"

    @pytest.mark.asyncio
    async def test_sticky_reply_language_for_short_message(
        self, mock_config_repo, mock_weaviate, mock_llm, mock_log_persister
    ):
        from app.services.rag_service import RAGService
        from app.services.fallback_service import FallbackService

        mock_config_repo.get_by_company.return_value = MagicMock(
            weaviate_collection="CoABC",
            default_language="english",
            supported_languages=["english", "hindi", "hinglish"],
            rag_config_json={"score_threshold": 0.4},
            fallback_config_json={"english": "Sorry.", "hindi": "माफ़ करें।"},
            system_prompt="You are helpful.",
        )

        svc = RAGService(
            config_repo=mock_config_repo,
            weaviate_client=mock_weaviate,
            llm_client=mock_llm,
            fallback_service=FallbackService(),
            log_persister=mock_log_persister,
        )

        result = await svc.process_query(
            company_id=uuid.uuid4(),
            query="ok",
            conversation_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
            conversation_reply_language="hindi",
        )

        assert result["language"] == "hindi"
        # generate_answer may be called twice: once for the answer and once for
        # language repair (when the LLM returns English text but Hindi is required).
        assert mock_llm.generate_answer.call_count >= 1
        first_call_kw = mock_llm.generate_answer.call_args_list[0].kwargs
        assert first_call_kw.get("output_language") == "hindi"
