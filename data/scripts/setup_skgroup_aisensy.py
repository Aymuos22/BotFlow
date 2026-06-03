"""
One-off: set SK Group to AiSensy (project id, WABA number, API key) and
whatsapp_provider=aisensy.

Run inside the API container::

  export AISENSY_API_KEY=...
  python data/scripts/setup_skgroup_aisensy.py

Optional: AISENSY_WHATSAPP_NUMBER, AISENSY_PROJECT_ID.
"""
from __future__ import annotations

import asyncio
import os
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.company_config import CompanyConfig
from app.repositories.company_config_repository import CompanyConfigRepository

SK_GROUP_ID = uuid.UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")
DEFAULT_AISENSY_WA = "whatsapp:+919818201631"
DEFAULT_PROJECT_ID = "69df47ae1a15c91193bbf875"


async def main() -> None:
    key = (os.environ.get("AISENSY_API_KEY") or "").strip()
    if not key:
        raise SystemExit("Missing AISENSY_API_KEY in environment.")
    wa = (os.environ.get("AISENSY_WHATSAPP_NUMBER") or DEFAULT_AISENSY_WA).strip()
    project_id = (os.environ.get("AISENSY_PROJECT_ID") or DEFAULT_PROJECT_ID).strip()

    async with AsyncSessionLocal() as db:
        repo = CompanyConfigRepository(db)
        dup = await db.execute(
            select(CompanyConfig).where(CompanyConfig.aisensy_whatsapp_number == wa)
        )
        found = dup.scalar_one_or_none()
        if found is not None and found.company_id != SK_GROUP_ID:
            raise SystemExit(
                f"aisensy_whatsapp_number {wa!r} is already assigned to company "
                f"{found.company_id}. Clear that row first."
            )
        cfg = await repo.get_by_company(SK_GROUP_ID)
        if not cfg:
            raise SystemExit("No company_configs row for SK Group.")
        before = (cfg.whatsapp_provider or "")
        cfg.aisensy_whatsapp_number = wa
        cfg.aisensy_project_id = project_id
        cfg.aisensy_api_key = key
        cfg.whatsapp_provider = "aisensy"
        await db.commit()
        print(
            f"OK: SK Group -> whatsapp_provider aisensy (was {before!r}). "
            f"aisensy_whatsapp_number={wa!r}, aisensy_project_id={project_id!r}."
        )


if __name__ == "__main__":
    asyncio.run(main())
