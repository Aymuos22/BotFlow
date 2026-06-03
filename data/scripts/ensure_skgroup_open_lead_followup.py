#!/usr/bin/env python3
"""
Create a default open-lead follow-up rule for SK Group (Skin Range) if none exist.

Requires DATABASE_URL. Sends use Meta WhatsApp Cloud + an approved template name.
Optional env:
  SKRANGE_FOLLOWUP_TEMPLATE_NAME   (default: follow_up_template)
  SKRANGE_FOLLOWUP_DELAY_MINUTES   (default: 1440)

Usage (repo root):

  python data/scripts/ensure_skgroup_open_lead_followup.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.repositories.whatsapp_campaign_repository import (  # noqa: E402
    WhatsAppFollowupRuleRepository,
)

SK_GROUP_ID = UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")


async def main() -> int:
    template = os.environ.get("SKRANGE_FOLLOWUP_TEMPLATE_NAME", "follow_up_template").strip()
    delay = int(os.environ.get("SKRANGE_FOLLOWUP_DELAY_MINUTES", "1440"))
    async with AsyncSessionLocal() as db:
        repo = WhatsAppFollowupRuleRepository(db)
        existing = await repo.list_for_company(SK_GROUP_ID)
        if existing:
            print(f"SK Group already has {len(existing)} follow-up rule(s); nothing to do.")
            await engine.dispose()
            return 0
        await repo.create(
            {
                "company_id": SK_GROUP_ID,
                "name": "Open lead reminder",
                "is_active": True,
                "steps_json": [
                    {
                        "delay_minutes": delay,
                        "template_name": template,
                        "language_code": "en",
                        "body_variables": [],
                        "header_media_url": None,
                    }
                ],
            }
        )
        await db.commit()
        print(f"Created open-lead follow-up: delay={delay} min, template={template!r}")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
