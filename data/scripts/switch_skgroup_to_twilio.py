"""
Switch SK Group back to Twilio as the active WhatsApp provider.

Does not change Twilio or AiSensy stored numbers/credentials — only sets
``whatsapp_provider`` to ``twilio``. Run inside the API container::

  python data/scripts/switch_skgroup_to_twilio.py
"""
from __future__ import annotations

import asyncio
import uuid

from app.core.database import AsyncSessionLocal
from app.repositories.company_config_repository import CompanyConfigRepository

SK_GROUP_ID = uuid.UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        repo = CompanyConfigRepository(db)
        cfg = await repo.get_by_company(SK_GROUP_ID)
        if not cfg:
            raise SystemExit("No company_configs row for SK Group.")
        before = (cfg.whatsapp_provider or "")
        cfg.whatsapp_provider = "twilio"
        await db.commit()
        print(
            f"OK: SK Group whatsapp_provider twilio (was {before!r}). "
            f"twilio_whatsapp_number={cfg.twilio_whatsapp_number!r}."
        )


if __name__ == "__main__":
    asyncio.run(main())
