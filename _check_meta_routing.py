import sys, asyncio
sys.path.insert(0, '/app')
import asyncpg
from app.core.config import settings

async def main():
    raw_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(raw_url)
    try:
        rows = await conn.fetch("""
            SELECT c.name, cc.whatsapp_provider, cc.meta_phone_number_id, cc.meta_waba_id,
                   (cc.meta_graph_access_token_encrypted IS NOT NULL) AS has_token,
                   (cc.meta_app_secret_encrypted IS NOT NULL) AS has_secret,
                   cc.system_prompt LIKE '%SkinRange%' OR cc.system_prompt LIKE '%skinrange%' AS prompt_has_skinrange
            FROM companies c
            JOIN company_configs cc ON cc.company_id = c.id
            ORDER BY c.name
        """)
        print("=== Meta config per company ===")
        for r in rows:
            print(f"\n  Company: {r['name']}")
            print(f"    provider:         {r['whatsapp_provider']}")
            print(f"    meta_phone_id:    {r['meta_phone_number_id']}")
            print(f"    meta_waba_id:     {r['meta_waba_id']}")
            print(f"    has_token:        {r['has_token']}")
            print(f"    has_secret:       {r['has_secret']}")
            print(f"    prompt_skinrange: {r['prompt_has_skinrange']}")
    finally:
        await conn.close()

asyncio.run(main())
