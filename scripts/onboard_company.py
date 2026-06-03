#!/usr/bin/env python3
"""
Onboard a company using the same logic as POST /api/v1/onboarding/company/full.

No HTTP server or admin key required. Uses DATABASE_URL and Weaviate from .env.
On a new database, run once: python scripts/create_tables.py

Example:
  python scripts/onboard_company.py --company-name sk-group --display-name "SK Group" --phone +919318492023
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.integrations.weaviate.client import WeaviateClient  # noqa: E402
from app.repositories.company_channel_repository import CompanyChannelRepository  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402
from app.repositories.company_repository import CompanyRepository  # noqa: E402
from app.repositories.onboarding_status_repository import OnboardingStatusRepository  # noqa: E402
from app.schemas.onboarding import FullOnboardingRequest  # noqa: E402
from app.services.onboarding_service import OnboardingService  # noqa: E402

logger = logging.getLogger("onboard_company")


async def _run(payload: FullOnboardingRequest) -> int:
    try:
        weaviate = WeaviateClient(
            url=settings.weaviate_url,
            api_key=settings.weaviate_api_key,
            timeout=settings.weaviate_timeout_seconds,
        )

        async with AsyncSessionLocal() as session:
            service = OnboardingService(
                company_repo=CompanyRepository(session),
                config_repo=CompanyConfigRepository(session),
                channel_repo=CompanyChannelRepository(session),
                onboarding_repo=OnboardingStatusRepository(session),
                weaviate_client=weaviate,
            )
            try:
                summary = await service.full_onboard(payload)
            except Exception as exc:
                await session.rollback()
                logger.error("%s", exc)
                return 1
            await session.commit()

        out = {
            "company_id": str(summary.company.id),
            "company_name": summary.company.name,
            "weaviate_collection": summary.config.weaviate_collection,
            "whatsapp_channel_key": summary.channel.session_name,
            "weaviate_ready": summary.onboarding_status.weaviate_ready,
            "twilio_configured": summary.onboarding_status.twilio_configured,
            "next_steps": summary.next_steps,
        }
        print(json.dumps(out, indent=2))
        return 0
    finally:
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Onboard a company (DB + Weaviate).")
    p.add_argument("--company-name", required=True, help="Unique slug, e.g. sk-group")
    p.add_argument(
        "--display-name",
        default=None,
        help="Human-readable name (default: derived from company-name)",
    )
    p.add_argument(
        "--phone",
        default="+15555550100",
        help="E.164 WhatsApp channel number (change from placeholder if needed)",
    )
    args = p.parse_args()
    display = args.display_name or args.company_name.replace("-", " ").title()
    payload = FullOnboardingRequest(
        company_name=args.company_name.strip(),
        display_name=display.strip(),
        phone_number=args.phone.strip(),
    )
    raise SystemExit(asyncio.run(_run(payload)))


if __name__ == "__main__":
    main()
