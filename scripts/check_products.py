import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine
from app.core.config import settings
from app.integrations.weaviate.client import WeaviateClient

async def main():
    async with AsyncSessionLocal() as db:
        r = await db.execute(text("SELECT count(1) FROM products WHERE company_id='33eaf707-06f1-4e30-93d8-d8da71afaa92' AND is_active=true"))
        db_count = r.scalar()
        print(f"DB products (active): {db_count}")

        r2 = await db.execute(text("SELECT count(1) FROM products WHERE company_id='33eaf707-06f1-4e30-93d8-d8da71afaa92' AND weaviate_indexed=true"))
        indexed_count = r2.scalar()
        print(f"DB products (weaviate_indexed=true): {indexed_count}")

    weaviate = WeaviateClient(
        url=settings.weaviate_url,
        api_key=settings.weaviate_api_key,
        timeout=settings.weaviate_timeout_seconds,
    )
    # Query Weaviate for a count of all chunks with product_id set
    gql = """{
      Aggregate {
        Co33EAF70706F14E3093D8D8DA71AFAA92 {
          meta { count }
        }
      }
    }"""
    result = await weaviate._post_graphql(gql)
    count = result.get("data", {}).get("Aggregate", {}).get("Co33EAF70706F14E3093D8D8DA71AFAA92", [{}])[0].get("meta", {}).get("count", "?")
    print(f"Weaviate total objects in collection: {count}")
    await weaviate.aclose()
    await engine.dispose()

asyncio.run(main())
