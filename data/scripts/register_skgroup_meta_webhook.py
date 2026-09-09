"""
Register SK Group's WhatsApp Business Account (WABA) with the Meta App so
that webhook events are delivered to our backend callback URL.

What this does
--------------
1. Loads SK Group's CompanyConfig from the DB (meta_graph_access_token,
   meta_phone_number_id, meta_waba_id).
2. Resolves the WABA id — uses meta_waba_id if already stored, otherwise
   calls GET /{phone_number_id}?fields=whatsapp_business_account to look it
   up and persists it.
3. Calls POST /{waba_id}/subscribed_apps to subscribe the WABA to this
   Meta App.  This tells Meta to deliver inbound messages / status callbacks
   to the app's registered webhook callback URL.

Usage (from repo root, inside the API container or with venv active)::

    python data/scripts/register_skgroup_meta_webhook.py

The access token is read from the DB (already stored encrypted). No extra
environment variables required unless you want to override the token::

    export META_GRAPH_ACCESS_TOKEN='EAAXyl3J...'   # optional override
    python data/scripts/register_skgroup_meta_webhook.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.integrations.meta_whatsapp.client import MetaWhatsAppClient  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402

SK_GROUP_ID = uuid.UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")


async def main() -> None:
    s = get_settings()

    async with AsyncSessionLocal() as db:
        repo = CompanyConfigRepository(db)
        cfg = await repo.get_by_company(SK_GROUP_ID)
        if not cfg:
            raise SystemExit("No company_configs row found for SK Group.")

        # Prefer env-var override so this script can be run with a fresh token
        # without touching the DB first.
        token = (os.environ.get("META_GRAPH_ACCESS_TOKEN") or "").strip()
        if not token:
            token = cfg.meta_graph_access_token or ""
        if not token:
            raise SystemExit(
                "No Meta Graph access token found.\n"
                "Either store it via the portal or set META_GRAPH_ACCESS_TOKEN."
            )

        phone_id = (cfg.meta_phone_number_id or "").strip()
        if not phone_id:
            raise SystemExit(
                "meta_phone_number_id is not set for SK Group. "
                "Run setup_company_meta_whatsapp.py --company skrange first."
            )

        client = MetaWhatsAppClient(
            access_token=token,
            phone_number_id=phone_id,
            graph_base_url=s.meta_graph_api_base_url,
            graph_version=s.meta_graph_api_version,
            timeout=s.meta_webhook_timeout_seconds,
        )

        # ── Step 1: resolve WABA id ────────────────────────────────────────
        waba_id = (cfg.meta_waba_id or "").strip()
        if not waba_id:
            print("meta_waba_id not stored — looking up from phone_number_id …")
            waba_id = await client.fetch_whatsapp_business_account_id() or ""
            if not waba_id:
                raise SystemExit(
                    "Could not resolve WABA id from Meta API. "
                    "Check that the access token has whatsapp_business_management permission."
                )
            # Persist so future calls skip the lookup
            cfg.meta_waba_id = waba_id
            await db.commit()
            print(f"Resolved and saved WABA id: {waba_id}")
        else:
            print(f"Using stored WABA id: {waba_id}")

        # ── Step 2: subscribe WABA to the Meta App ────────────────────────
        print(f"Subscribing WABA {waba_id} to the Meta App …")
        result = await client.subscribe_waba_to_app(waba_id=waba_id)

        if result.get("success"):
            print(
                f"\n✓  SK Group WABA ({waba_id}) is now subscribed.\n"
                f"   Meta will deliver webhook events to your registered callback URL.\n"
                f"   Verify in Meta Developer → Your App → WhatsApp → Configuration → Webhook."
            )
        else:
            print(f"Unexpected response from Meta: {result}", file=sys.stderr)
            raise SystemExit(1)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
