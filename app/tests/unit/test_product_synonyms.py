import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.product_service import build_chunk_text


def test_product_synonyms_are_normalized_on_create_schema():
    payload = ProductCreate(
        name="Aadved Sleep",
        synonyms=[" neend ki dawa ", "Nind medicine", "neend ki dawa", ""],
    )

    assert payload.synonyms == ["neend ki dawa", "Nind medicine"]


def test_product_synonyms_can_be_cleared_on_update_schema():
    payload = ProductUpdate(synonyms=[])

    assert payload.synonyms == []


def test_product_index_text_includes_synonyms():
    product = Product(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        name="Aadved Sleep",
        sku="SKR-SLEEP",
        description="Supports restful sleep.",
        synonyms_json=["neend ki dawa", "nind medicine", "sleep capsule"],
        is_active=True,
    )

    chunk = build_chunk_text(product)

    assert "Synonyms: neend ki dawa, nind medicine, sleep capsule" in chunk


@pytest.mark.asyncio
async def test_rag_product_answer_uses_db_cards(monkeypatch):
    """
    When a product_id is returned by Weaviate, the RAG service must:
    - Fetch the canonical product card from the DB (not use the raw Weaviate chunk).
    - Pass that DB card context to the LLM (not the stale Weaviate chunk text).
    - Return the LLM's conversational response.

    The LLM is now always called — there is no fixed-template fast path.
    """
    from app.services import rag_service as rag_mod
    from app.services.fallback_service import FallbackService
    from app.services.rag_service import RAGService

    product_id = uuid.uuid4()
    company_id = uuid.uuid4()
    config_repo = AsyncMock()
    config_repo.db = object()
    config_repo.get_by_company.return_value = MagicMock(
        weaviate_collection="CoABC",
        default_language="english",
        supported_languages=["english", "hinglish"],
        rag_config_json={"score_threshold": 0.4},
        fallback_config_json={"english": "Sorry."},
        system_prompt="You are helpful.",
    )
    weaviate = AsyncMock()
    weaviate.hybrid_search.return_value = {
        "top_score": 0.9,
        "hits": [
            {
                "chunk_text": "Product: Old Chunk Name\nUsed For: sleep and insomnia",
                "file_name": "product",
                "document_id": str(product_id),
                "chunk_index": 0,
                "score": 0.9,
                "product_id": str(product_id),
            }
        ],
    }
    llm = AsyncMock()
    llm.generate_answer.return_value = (
        "Official DB Sleep Product is great for restful sleep. "
        "It costs INR 499. Would you like to know more?"
    )

    async def fake_db_cards(db, *, company_id, product_ids):
        return [
            {
                "name": "Official DB Sleep Product",
                "used_for": "Sleep support from DB",
                "dosage": "1 capsule before sleep",
                "price": "INR 499",
                "stock": "In Stock",
                "link": "https://example.test/sleep",
            }
        ]

    monkeypatch.setattr(rag_mod, "_product_cards_from_db", fake_db_cards)

    svc = RAGService(
        config_repo=config_repo,
        weaviate_client=weaviate,
        llm_client=llm,
        fallback_service=FallbackService(),
    )

    result = await svc.process_query(
        company_id=company_id,
        query="Can you suggest product for sleep?",
    )

    assert result["response_type"] == "rag"
    # The LLM must be called — there is no fixed-template bypass any more.
    llm.generate_answer.assert_called_once()
    # The LLM must have received the DB card context (not the stale Weaviate chunk).
    call_kwargs = llm.generate_answer.call_args.kwargs
    context_joined = "\n".join(call_kwargs.get("context_chunks", []))
    assert "Official DB Sleep Product" in context_joined
    assert "Old Chunk Name" not in context_joined
    # The answer should be the LLM's conversational response.
    assert "Official DB Sleep Product" in result["answer"]
