import sys, asyncio
sys.path.insert(0, '.')
import os
try:
    from dotenv import load_dotenv; load_dotenv('.env', override=False)
except Exception:
    pass
db = os.environ.get('DATABASE_URL', '')
if ':6543/' in db:
    os.environ['DATABASE_URL'] = db.replace(':6543/', ':5432/')

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.repositories.company_config_repository import CompanyConfigRepository
from app.integrations.weaviate.client import WeaviateClient
from app.integrations.llm.client import get_llm_client
import uuid, json


async def test():
    cid = uuid.UUID('b271173d-3270-49ae-a8b4-979c80d1b431')

    # 1. Config
    async with AsyncSessionLocal() as s:
        cfg = await CompanyConfigRepository(s).get_by_company(cid)
        collection = cfg.weaviate_collection
        prompt = cfg.system_prompt or 'You are a helpful assistant.'
        print('=== Config ===')
        print('system_prompt chars:', len(cfg.system_prompt or ''))
        print('collection:', collection)
        print('rag_config:', cfg.rag_config_json)
        print('fallback_config:', cfg.fallback_config_json)

    # 2. Weaviate search
    print()
    print('=== Weaviate RAG ===')
    weaviate = WeaviateClient(url=settings.weaviate_url, api_key=settings.weaviate_api_key, timeout=30)
    chunks = []
    try:
        result = await weaviate.hybrid_search(
            collection_name=collection,
            query='What are his skills',
            top_k=3,
            hybrid_alpha=0.5,
        )
        print('raw result type:', type(result))
        print('raw result keys:', list(result.keys()) if isinstance(result, dict) else 'not a dict')
        # Try to extract chunks
        if isinstance(result, dict):
            objects = result.get('objects') or result.get('data', {}).get('Get', {}).get(collection, [])
            print('objects count:', len(objects) if objects else 0)
            if objects:
                for i, obj in enumerate(objects[:3]):
                    props = obj.get('properties', obj)
                    text = props.get('text', props.get('content', str(props)))[:150]
                    chunks.append(str(text))
                    print(f'  chunk {i+1}: {text[:100]}')
        print('chunks extracted:', len(chunks))
    except Exception as e:
        print('Weaviate error:', e)
        import traceback; traceback.print_exc()
    finally:
        await weaviate.aclose()

    # 3. LLM
    print()
    print('=== LLM ===')
    print('provider:', settings.llm_provider)
    print('model:', settings.llm_model)
    print('groq_key set:', bool(settings.groq_api_key))
    try:
        llm = get_llm_client()
        test_chunks = chunks if chunks else ['Soumya Darshan Sukla is a skilled software developer.']
        resp = await llm.generate_answer(
            context_chunks=test_chunks,
            user_query='What are his skills?',
            system_prompt=prompt,
        )
        print('LLM response:', str(resp)[:300])
    except Exception as e:
        print('LLM error:', e)
        import traceback; traceback.print_exc()

    await engine.dispose()


asyncio.run(test())
