"""List companies and Twilio / Weaviate integration fields."""
import asyncio
import os
import sys

import asyncpg


async def run() -> None:
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    url = raw.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    rows = await conn.fetch(
        """
        SELECT co.id, co.name, co.display_name, co.status,
               cc.weaviate_collection, cc.whatsapp_provider,
               cc.twilio_whatsapp_number,
               ch.session_name AS channel_key, ch.phone_number AS channel_phone
        FROM companies co
        JOIN company_configs cc ON cc.company_id = co.id
        LEFT JOIN company_channels ch ON ch.company_id = co.id AND ch.is_primary = TRUE
        ORDER BY co.name
        """
    )
    await conn.close()
    for r in rows:
        print(f"{r['name']} ({r['id']}) — {r['status']}")
        print(f"  weaviate_collection: {r['weaviate_collection']}")
        print(f"  whatsapp_provider: {r['whatsapp_provider']}")
        print(f"  twilio_whatsapp_number: {r['twilio_whatsapp_number']}")
        print(f"  channel_key / phone: {r['channel_key']} / {r['channel_phone']}")
        print()


if __name__ == "__main__":
    asyncio.run(run())
