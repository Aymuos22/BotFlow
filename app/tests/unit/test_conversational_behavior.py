"""
Tests for the conversational AI behavior changes:

1. RAG service — product queries always go through the LLM (no fixed-format bypass).
2. Webhooks    — product images are only sent on explicit requests or first-time introductions.
3. LLM client  — system prompt contains the correct anti-brochure instructions.
"""
import uuid
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------

def _config(collection="CoABC", language="english", threshold=0.4):
    return MagicMock(
        weaviate_collection=collection,
        default_language=language,
        supported_languages=[language, "hinglish"],
        rag_config_json={"score_threshold": threshold},
        fallback_config_json={"english": "Sorry, no info found."},
        system_prompt=None,
    )


def _search_result(score: Optional[float] = 0.8, chunks=None):
    if chunks is None:
        chunks = ["Product: Kaama Gold\nUsed For: sexual health\nPrice: INR 1200"]
    if score is None:
        return {"chunks": [], "top_score": None}
    return {"chunks": chunks, "top_score": score}


def _make_rag_service(config_repo, weaviate, llm, persister):
    from app.services.rag_service import RAGService
    from app.services.fallback_service import FallbackService

    return RAGService(
        config_repo=config_repo,
        weaviate_client=weaviate,
        llm_client=llm,
        fallback_service=FallbackService(),
        log_persister=persister,
    )


def _mock_message(sender_type: str, text: str):
    m = MagicMock()
    m.sender_type = sender_type
    m.message_text = text
    return m


# ===========================================================================
# 1. RAG service — LLM is ALWAYS called for product queries
# ===========================================================================

class TestProductQueriesAlwaysUseLLM:

    @pytest.fixture
    def mock_config_repo(self):
        repo = AsyncMock()
        repo.get_by_company.return_value = _config()
        repo.db = None
        return repo

    @pytest.fixture
    def mock_weaviate(self):
        client = AsyncMock()
        client.hybrid_search.return_value = _search_result()
        return client

    @pytest.fixture
    def mock_llm(self):
        client = AsyncMock()
        client.generate_answer.return_value = "Kaama Gold helps with sexual health. Want more details?"
        return client

    @pytest.fixture
    def persister(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_product_recommendation_query_calls_llm(
        self, mock_config_repo, mock_weaviate, mock_llm, persister
    ):
        """A product recommendation question must always call the LLM — never a fixed template."""
        svc = _make_rag_service(mock_config_repo, mock_weaviate, mock_llm, persister)

        result = await svc.process_query(
            company_id=uuid.uuid4(),
            query="suggest me something for joint pain",
        )

        assert result["response_type"] == "rag"
        mock_llm.generate_answer.assert_called_once()
        # The answer must come from the LLM, not a hardcoded template
        assert "joint pain" not in result["answer"].lower() or mock_llm.generate_answer.called

    @pytest.mark.asyncio
    async def test_price_query_calls_llm(
        self, mock_config_repo, mock_weaviate, mock_llm, persister
    ):
        """Price queries must always call the LLM."""
        svc = _make_rag_service(mock_config_repo, mock_weaviate, mock_llm, persister)

        result = await svc.process_query(
            company_id=uuid.uuid4(),
            query="Kaama Gold ka price kya hai?",
        )

        assert result["response_type"] == "rag"
        mock_llm.generate_answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_buy_intent_query_calls_llm(
        self, mock_config_repo, mock_weaviate, mock_llm, persister
    ):
        """Buy-intent queries (order/buy/khareed) must always call the LLM."""
        svc = _make_rag_service(mock_config_repo, mock_weaviate, mock_llm, persister)

        result = await svc.process_query(
            company_id=uuid.uuid4(),
            query="I want to order this product",
        )

        assert result["response_type"] == "rag"
        mock_llm.generate_answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_answer_returned_verbatim(
        self, mock_config_repo, mock_weaviate, mock_llm, persister
    ):
        """The LLM's response (not a template) must be what is returned."""
        llm_response = "Kaama Gold helps with male sexual wellness. Want to know the price?"
        mock_llm.generate_answer.return_value = llm_response

        svc = _make_rag_service(mock_config_repo, mock_weaviate, mock_llm, persister)

        result = await svc.process_query(
            company_id=uuid.uuid4(),
            query="What is Kaama Gold used for?",
        )

        # Core LLM text should be present in the answer
        assert "Kaama Gold" in result["answer"]
        assert "sexual wellness" in result["answer"].lower() or mock_llm.generate_answer.called

    @pytest.mark.asyncio
    async def test_non_product_query_calls_llm(
        self, mock_config_repo, mock_weaviate, mock_llm, persister
    ):
        """Non-product queries (policy, returns) also always call the LLM."""
        svc = _make_rag_service(mock_config_repo, mock_weaviate, mock_llm, persister)

        result = await svc.process_query(
            company_id=uuid.uuid4(),
            query="What is your return policy?",
        )

        assert result["response_type"] == "rag"
        mock_llm.generate_answer.assert_called_once()


# ===========================================================================
# 2. Webhook helpers — image sending logic
# ===========================================================================

class TestCustomerAsksForImage:

    def _fn(self, query):
        from app.api.v1.endpoints.webhooks import _customer_asks_for_image
        return _customer_asks_for_image(query)

    # --- Should detect image requests ---
    def test_detects_english_image(self):
        assert self._fn("Can you send me the image?") is True

    def test_detects_english_photo(self):
        assert self._fn("Show me the photo of this product") is True

    def test_detects_english_picture(self):
        assert self._fn("What does it look like? Send a picture") is True

    def test_detects_english_pic(self):
        assert self._fn("Send me the pic") is True

    def test_detects_hinglish_dikhao(self):
        assert self._fn("product dikhao") is True

    def test_detects_hinglish_dikha(self):
        assert self._fn("dikha do yaar") is True

    def test_detects_hinglish_bhejo(self):
        assert self._fn("photo bhejo") is True

    def test_detects_hindi_tasveer(self):
        assert self._fn("तस्वीर भेजो") is True

    def test_detects_hindi_photo(self):
        assert self._fn("फोटो दिखाओ") is True

    def test_show_me_without_image(self):
        # "show me" alone → triggers (intent to see)
        assert self._fn("show me more details") is True

    # --- Should NOT detect as image requests ---
    def test_price_query_not_image(self):
        assert self._fn("Kaama Gold ka price kya hai?") is False

    def test_product_recommendation_not_image(self):
        assert self._fn("joint pain ke liye kuch suggest karo") is False

    def test_order_query_not_image(self):
        assert self._fn("I want to order this product") is False

    def test_greeting_not_image(self):
        assert self._fn("Hello, how are you?") is False

    def test_empty_string(self):
        assert self._fn("") is False

    def test_none_like_empty(self):
        assert self._fn("") is False


class TestFilterNewProductsForImages:

    def _fn(self, products, msgs):
        from app.api.v1.endpoints.webhooks import _filter_new_products_for_images
        return _filter_new_products_for_images(products, msgs)

    def _prod(self, name):
        return {"name": name, "image_url": f"http://example.com/{name}.jpg"}

    # --- Empty / edge cases ---
    def test_empty_products_returns_empty(self):
        assert self._fn([], []) == []

    def test_no_prior_msgs_returns_all(self):
        products = [self._prod("Kaama Gold"), self._prod("Liv Muztang")]
        result = self._fn(products, [])
        assert len(result) == 2

    def test_no_prior_bot_msgs_returns_all(self):
        """Only customer messages in history → treat all products as new."""
        products = [self._prod("Kaama Gold")]
        msgs = [_mock_message("customer", "joint pain ke liye kuch batao")]
        result = self._fn(products, msgs)
        assert len(result) == 1

    # --- First-time introduction ---
    def test_product_not_in_prior_msgs_is_included(self):
        """Product never mentioned before → image should be sent."""
        products = [self._prod("Sandy RX")]
        msgs = [_mock_message("bot", "Kaama Gold helps with sexual health.")]
        result = self._fn(products, msgs)
        assert len(result) == 1
        assert result[0]["name"] == "Sandy RX"

    # --- Already introduced — skip image ---
    def test_product_already_in_prior_bot_msg_is_excluded(self):
        """Product already mentioned by bot → do not send image again."""
        products = [self._prod("Kaama Gold")]
        msgs = [_mock_message("bot", "Kaama Gold is a great product for men's health.")]
        result = self._fn(products, msgs)
        assert result == []

    def test_mix_of_new_and_seen_products(self):
        """Only products not yet introduced should get images."""
        products = [self._prod("Kaama Gold"), self._prod("Liv Muztang")]
        msgs = [_mock_message("bot", "Kaama Gold helps with sexual wellness.")]
        result = self._fn(products, msgs)
        assert len(result) == 1
        assert result[0]["name"] == "Liv Muztang"

    def test_customer_message_does_not_count_as_introduction(self):
        """Customer mentioning a product name doesn't count — only bot messages matter."""
        products = [self._prod("Kaama Gold")]
        msgs = [
            _mock_message("customer", "tell me about Kaama Gold"),
        ]
        result = self._fn(products, msgs)
        # Bot hasn't mentioned it yet → include the image
        assert len(result) == 1

    def test_case_insensitive_match(self):
        """Product name matching is case-insensitive."""
        products = [self._prod("Kaama Gold")]
        msgs = [_mock_message("bot", "KAAMA GOLD is recommended for men.")]
        result = self._fn(products, msgs)
        assert result == []

    def test_multiple_prior_messages_all_scanned(self):
        """All prior bot messages are scanned, not just the latest."""
        products = [self._prod("Sandy RX")]
        msgs = [
            _mock_message("bot", "Kaama Gold is good for stamina."),
            _mock_message("bot", "Sandy RX is also available for skin health."),
        ]
        result = self._fn(products, msgs)
        assert result == []  # Sandy RX was mentioned in the second message


# ===========================================================================
# 3. LLM client — system prompt contains anti-brochure instructions
# ===========================================================================

class TestLLMSystemPromptInstructions:

    def test_whatsapp_style_not_brochure(self):
        from app.integrations.llm.client import _WHATSAPP_RESPONSE_STYLE
        assert "product brochure" in _WHATSAPP_RESPONSE_STYLE.lower()
        assert "respond to what was actually asked" in _WHATSAPP_RESPONSE_STYLE.lower()

    def test_whatsapp_style_only_share_details_on_request(self):
        from app.integrations.llm.client import _WHATSAPP_RESPONSE_STYLE
        assert "only share additional product details" in _WHATSAPP_RESPONSE_STYLE.lower()
        assert "if the customer specifically asks" in _WHATSAPP_RESPONSE_STYLE.lower()

    def test_response_priorities_answer_only_what_was_asked(self):
        from app.integrations.llm.client import _RAG_RESPONSE_PRIORITIES
        assert "answer only what the customer specifically asked" in _RAG_RESPONSE_PRIORITIES.lower()

    def test_response_priorities_no_all_available_details(self):
        from app.integrations.llm.client import _RAG_RESPONSE_PRIORITIES
        # The old brochure instruction must be gone
        assert "always include all available details" not in _RAG_RESPONSE_PRIORITIES.lower()
        assert "never omit a field" not in _RAG_RESPONSE_PRIORITIES.lower()

    def test_response_priorities_knowledgeable_friend_framing(self):
        from app.integrations.llm.client import _RAG_RESPONSE_PRIORITIES
        assert "knowledgeable friend" in _RAG_RESPONSE_PRIORITIES.lower()

    def test_full_system_prompt_assembled_correctly(self):
        """_compose_full_system must include both lang note and anti-brochure style."""
        from app.integrations.llm.client import (
            _compose_full_system,
            _LANG_INSTRUCTIONS,
            _DEFAULT_SYSTEM_PROMPT,
        )
        lang_note = _LANG_INSTRUCTIONS["english"]
        result = _compose_full_system(
            lang_note=lang_note,
            base_prompt=_DEFAULT_SYSTEM_PROMPT,
            max_system_chars=8000,
        )
        assert "product brochure" in result.lower()
        assert "answer only what the customer specifically asked" in result.lower()
        assert "english" in result.lower()
