"""Quick debug: what product_cards does RAG return for a test query?"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COMPANY_ID = "33eaf707-06f1-4e30-93d8-d8da71afaa92"
QUERY = "ayush for men k baare mein batao"

async def main():
    from app.core.config import get_settings
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.repositories.product_repository import ProductRepository
    from app.services.rag_service import RAGService
    from app.integrations.weaviate.client import WeaviateClient
    from app.integrations.embeddings.client import EmbeddingClient
    from app.integrations.llm.client import LLMClient

    s = get_settings()
    engine = create_async_engine(s.database_url)
    weaviate = WeaviateClient(url=s.weaviate_url, api_key=s.weaviate_api_key)
    embedding = EmbeddingClient()
    llm = LLMClient()

    async with AsyncSession(engine) as db:
        svc = RAGService(
            weaviate_client=weaviate,
            embedding_client=embedding,
            llm_client=llm,
            product_repo=ProductRepository(db),
        )
        result = await svc.process_query(
            company_id=COMPANY_ID,
            query=QUERY,
            language="hi",
        )

    print("response_type:", result["response_type"])
    print("answer:", result["answer"][:200])
    print("recommended_products:", result["recommended_products"])

asyncio.run(main())
