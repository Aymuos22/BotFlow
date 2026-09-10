#!/usr/bin/env python3
"""
Set Meta WhatsApp Cloud API credentials for an existing company (DB only).

Secrets must come from environment variables (never commit values).
Uses the same fields as POST /api/v1/portal/admin/companies/{id}/meta-whatsapp.

Example (from repo root):
  export META_GRAPH_ACCESS_TOKEN='...'
  export META_WEBHOOK_VERIFY_TOKEN='...'
  # optional: export META_APP_SECRET='...'
  python scripts/setup_company_meta_whatsapp.py \\
    --company rcs \\
    --phone-number-id 1062677916934285 \\
    --enable-meta-provider
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

# Switch from PgBouncer transaction pooler (port 6543) to session pooler
# (port 5432) so asyncpg prepared statements work in standalone scripts.
import os as _os
_db_url = _os.environ.get("DATABASE_URL", "")
if ":6543/" in _db_url:
    _os.environ["DATABASE_URL"] = _db_url.replace(":6543/", ":5432/")

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402


async def _find_company(session, company_key: str) -> Optional[Company]:
    key = company_key.strip()
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
            f"Ambiguous company key {company_key!r}; matches: {', '.join(names)}"
        )
    return rows[0] if rows else None


async def _run(
    company_key: str,
    phone_number_id: str,
    enable_meta_provider: bool,
) -> int:
    token = (os.environ.get("META_GRAPH_ACCESS_TOKEN") or "").strip()
    verify = (os.environ.get("META_WEBHOOK_VERIFY_TOKEN") or "").strip()
    app_secret = (os.environ.get("META_APP_SECRET") or "").strip()

    if not token:
        print("META_GRAPH_ACCESS_TOKEN is required in the environment.", file=sys.stderr)
        return 1
    if not verify:
        print(
            "META_WEBHOOK_VERIFY_TOKEN is required in the environment.",
            file=sys.stderr,
        )
        return 1

    async with AsyncSessionLocal() as session:
        company = await _find_company(session, company_key)
        if company is None:
            print(
                f"No company found for {company_key!r} (try slug or display name). "
                "Onboard first: scripts/onboard_company.py",
                file=sys.stderr,
            )
            return 1

        repo = CompanyConfigRepository(session)
        cfg = await repo.get_by_company(company.id)
        if cfg is None:
            print(f"Company {company.id} has no company_configs row.", file=sys.stderr)
            return 1

        pid = phone_number_id.strip()
        existing = await repo.get_by_meta_phone_number_id(pid)
        if existing is not None and str(existing.company_id) != str(company.id):
            print(
                f"phone_number_id {pid} is already used by company {existing.company_id}.",
                file=sys.stderr,
            )
            return 1

        cfg.meta_phone_number_id = pid
        cfg.meta_graph_access_token = token
        cfg.meta_webhook_verify_token = verify
        if app_secret:
            cfg.meta_app_secret = app_secret
        if enable_meta_provider:
            cfg.whatsapp_provider = "meta"

        await session.commit()
        await session.refresh(cfg)

        payload = {
            "company_id": str(company.id),
            "company_name": company.name,
            "display_name": company.display_name,
            "meta_phone_number_id": cfg.meta_phone_number_id,
            "whatsapp_provider": cfg.whatsapp_provider,
            "has_meta_graph_token": bool(cfg.meta_graph_access_token),
            "has_meta_webhook_verify_token": bool(cfg.meta_webhook_verify_token),
            "has_meta_app_secret": bool(cfg.meta_app_secret),
        }
        print(json.dumps(payload, indent=2))

    await engine.dispose()
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Configure Meta WhatsApp for a company (DB).")
    p.add_argument(
        "--company",
        required=True,
        help="Company slug (name) or display name, e.g. rcs or RCS",
    )
    p.add_argument(
        "--phone-number-id",
        required=True,
        help="Meta WhatsApp phone_number_id (routing id from webhook metadata)",
    )
    p.add_argument(
        "--enable-meta-provider",
        action="store_true",
        help="Set whatsapp_provider to meta (use for production Meta channel)",
    )
    args = p.parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                args.company,
                args.phone_number_id,
                args.enable_meta_provider,
            )
        )
    )


if __name__ == "__main__":
    main()
