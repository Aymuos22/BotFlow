#!/usr/bin/env python3
"""
Activate the myresume company.

Usage:
    python scripts/activate_myresume.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
import uuid

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Load .env so DATABASE_URL is visible in os.environ, then swap the
# PgBouncer transaction pooler (port 6543) for the session pooler (port 5432)
# so asyncpg prepared statements work correctly in standalone scripts.
import os as _os
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass  # dotenv not installed; rely on env already being set

_db_url = _os.environ.get("DATABASE_URL", "")
if ":6543/" in _db_url:
    _os.environ["DATABASE_URL"] = _db_url.replace(":6543/", ":5432/")

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.repositories.company_channel_repository import CompanyChannelRepository  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402
from app.repositories.company_repository import CompanyRepository  # noqa: E402
from app.repositories.onboarding_status_repository import OnboardingStatusRepository  # noqa: E402
from app.services.onboarding_service import OnboardingService  # noqa: E402

COMPANY_ID = uuid.UUID("b271173d-3270-49ae-a8b4-979c80d1b431")


async def _run() -> int:
    async with AsyncSessionLocal() as session:
        service = OnboardingService(
            company_repo=CompanyRepository(session),
            config_repo=CompanyConfigRepository(session),
            channel_repo=CompanyChannelRepository(session),
            onboarding_repo=OnboardingStatusRepository(session),
            weaviate_client=None,  # not needed for activation
        )
        result = await service.activate_company(COMPANY_ID)
        await session.commit()
        print(f"activated : {result.activated}")
        print(f"message   : {result.message}")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
