"""
One-off: update Meta Graph API system token for SK Group (skrange).

Reads the token from META_GRAPH_ACCESS_TOKEN env var (never hardcoded).
All other Meta fields (phone_number_id, verify_token, app_secret) are
left untouched.

Run inside the API container::

  export META_GRAPH_ACCESS_TOKEN='EAAXyl3J...'
  python data/scripts/patch_skgroup_meta_token.py
"""
from __future__ import annotations

import asyncio
import os
import uuid

from app.core.database import AsyncSessionLocal
from app.repositories.company_config_repository import CompanyConfigRepository

SK_GROUP_ID = uuid.UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")


async def main() -> None:
    token = (os.environ.get("META_GRAPH_ACCESS_TOKEN") or "").strip()
    if not token:
        raise SystemExit("Missing META_GRAPH_ACCESS_TOKEN in environment.")

    async with AsyncSessionLocal() as db:
        repo = CompanyConfigRepository(db)
        cfg = await repo.get_by_company(SK_GROUP_ID)
        if not cfg:
            raise SystemExit("No company_configs row found for SK Group.")

        cfg.meta_graph_access_token = token
        await db.commit()
        print(
            f"OK: SK Group meta_graph_access_token updated "
            f"(phone_number_id={cfg.meta_phone_number_id!r}, "
            f"provider={cfg.whatsapp_provider!r})."
        )


if __name__ == "__main__":
    asyncio.run(main())
