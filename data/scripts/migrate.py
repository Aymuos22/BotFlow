"""
Production database maintenance helper.

Prefer **Alembic** for schema migrations. This script only applies safe
data defaults that may be missing on older rows.

Run on deploy if needed (idempotent).
"""
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
    c = await asyncpg.connect(url)

    updated = await c.execute(
        "UPDATE company_configs "
        "SET whatsapp_agent_inactivity_minutes = 3 "
        "WHERE whatsapp_agent_inactivity_minutes IS NULL"
    )
    print(f"Inactivity default: {updated}")

    await c.close()
    print("Maintenance complete.")


if __name__ == "__main__":
    asyncio.run(run())
