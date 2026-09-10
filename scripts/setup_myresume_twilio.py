#!/usr/bin/env python3
"""
Configure Twilio Sandbox WhatsApp credentials for the "myresume" company.

This script is idempotent – running it twice is safe.
It reads credentials from environment variables so nothing sensitive is
committed to source control.

Prerequisites
-------------
1.  The company must already exist in the database.
    If it doesn't, onboard it first:

        python scripts/onboard_company.py \\
          --company-name myresume \\
          --display-name "MyResume" \\
          --phone +14155238886

2.  Export your Twilio sandbox credentials before running:

        $env:TWILIO_ACCOUNT_SID  = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        $env:TWILIO_AUTH_TOKEN   = "your_auth_token_here"

    Optionally override the sandbox sender number (default: Twilio sandbox):

        $env:TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"

Usage
-----
    python scripts/setup_myresume_twilio.py [--enable-twilio-provider]

Flags
-----
--enable-twilio-provider   Also set whatsapp_provider = "twilio" on the config
                           (recommended for a fresh setup; omit if the company
                           is still mid-migration from another provider).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import or_, select

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Switch from the PgBouncer *transaction* pooler (port 6543) to the
# *session* pooler (port 5432) so asyncpg prepared statements work correctly
# in standalone scripts.  The session pooler supports the extended query
# protocol; the transaction pooler does not.
import os as _os
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass
_db_url = _os.environ.get("DATABASE_URL", "")
if ":6543/" in _db_url:
    _os.environ["DATABASE_URL"] = _db_url.replace(":6543/", ":5432/")

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402

# ── constants ─────────────────────────────────────────────────────────────────
COMPANY_SLUG = "myresume"
DISPLAY_NAME = "MyResume"
# Twilio Sandbox shared sender number (standard across all sandbox accounts)
DEFAULT_SANDBOX_NUMBER = "whatsapp:+14155238886"


# ── helpers ───────────────────────────────────────────────────────────────────

async def _find_company(session, key: str) -> Optional[Company]:
    """Find a company by slug or display name (case-insensitive)."""
    key_lower = key.lower()
    result = await session.execute(
        select(Company).where(
            or_(
                Company.name == key,
                Company.name == key_lower,
                Company.display_name.ilike(key),
            )
        )
    )
    rows = list(result.scalars().all())
    if len(rows) > 1:
        names = [f"{c.name} ({c.display_name})" for c in rows]
        raise SystemExit(
            f"Ambiguous company key {key!r}; matches: {', '.join(names)}"
        )
    return rows[0] if rows else None


async def _run(enable_twilio_provider: bool) -> int:
    # ── Read credentials from env ──────────────────────────────────────────
    account_sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    auth_token  = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    wa_number   = (
        os.environ.get("TWILIO_WHATSAPP_NUMBER") or DEFAULT_SANDBOX_NUMBER
    ).strip()

    if not account_sid:
        print(
            "ERROR: TWILIO_ACCOUNT_SID is not set.\n"
            "  $env:TWILIO_ACCOUNT_SID = 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'",
            file=sys.stderr,
        )
        return 1

    if not auth_token:
        print(
            "ERROR: TWILIO_AUTH_TOKEN is not set.\n"
            "  $env:TWILIO_AUTH_TOKEN = 'your_auth_token_here'",
            file=sys.stderr,
        )
        return 1

    # Ensure the number has the whatsapp: prefix
    if not wa_number.startswith("whatsapp:"):
        wa_number = f"whatsapp:{wa_number}"

    async with AsyncSessionLocal() as session:
        company = await _find_company(session, COMPANY_SLUG)
        if company is None:
            print(
                f"ERROR: Company '{COMPANY_SLUG}' not found in the database.\n"
                f"  Onboard it first:\n"
                f"    python scripts/onboard_company.py "
                f"--company-name {COMPANY_SLUG} "
                f"--display-name \"{DISPLAY_NAME}\" "
                f"--phone +14155238886",
                file=sys.stderr,
            )
            return 1

        repo = CompanyConfigRepository(session)
        cfg = await repo.get_by_company(company.id)
        if cfg is None:
            print(
                f"ERROR: Company '{COMPANY_SLUG}' ({company.id}) has no company_configs row.",
                file=sys.stderr,
            )
            return 1

        # Check for number conflicts with other companies
        existing = await repo.get_by_twilio_number(wa_number)
        if existing is not None and str(existing.company_id) != str(company.id):
            print(
                f"ERROR: Twilio number {wa_number!r} is already assigned to "
                f"company {existing.company_id}.",
                file=sys.stderr,
            )
            return 1

        # Apply Twilio sandbox credentials
        cfg.twilio_whatsapp_number = wa_number
        cfg.twilio_account_sid     = account_sid
        cfg.twilio_auth_token      = auth_token  # stored encrypted by ORM setter

        if enable_twilio_provider:
            cfg.whatsapp_provider = "twilio"

        await session.commit()
        await session.refresh(cfg)

        result = {
            "company_id":            str(company.id),
            "company_name":          company.name,
            "display_name":          company.display_name,
            "whatsapp_provider":     cfg.whatsapp_provider,
            "twilio_whatsapp_number": cfg.twilio_whatsapp_number,
            "twilio_account_sid":    cfg.twilio_account_sid,
            "has_twilio_auth_token": bool(cfg.twilio_auth_token),
            "sandbox":               wa_number == DEFAULT_SANDBOX_NUMBER,
        }
        print(json.dumps(result, indent=2))

    await engine.dispose()
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            f"Configure Twilio Sandbox credentials for '{COMPANY_SLUG}' (DB only)."
        )
    )
    p.add_argument(
        "--enable-twilio-provider",
        action="store_true",
        help="Set whatsapp_provider to 'twilio' (recommended for a fresh setup)",
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(_run(args.enable_twilio_provider)))


if __name__ == "__main__":
    main()
