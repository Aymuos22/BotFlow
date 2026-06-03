"""
Register a Meta Cloud API business phone number (PHONE_NUMBER_ID/register).

This reads the Meta Graph token from the RCS CompanyConfig row in the DB.

Usage (inside API container):
  python /tmp/_meta_register_phone_cli.py <PHONE_NUMBER_ID> <PIN>
"""

from __future__ import annotations

import asyncio
import json
import sys
from uuid import UUID

import httpx

sys.path.insert(0, "/app")

from app.core.config import get_settings  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402

RCS = UUID("6fb68814-252b-4508-b221-e1ef611ae80f")


async def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python _meta_register_phone_cli.py <PHONE_NUMBER_ID> <PIN>")
        raise SystemExit(2)

    phone_id = sys.argv[1].strip()
    pin = sys.argv[2].strip()
    if not phone_id.isdigit():
        print("PHONE_NUMBER_ID must be digits")
        raise SystemExit(2)
    if len(pin) != 6 or not pin.isdigit():
        print("PIN must be 6 digits")
        raise SystemExit(2)

    async with AsyncSessionLocal() as s:
        cfg = await CompanyConfigRepository(s).get_by_company(RCS)
        if not cfg or not cfg.meta_graph_access_token:
            print("RCS: missing meta_graph_access_token in DB")
            raise SystemExit(1)
        token = cfg.meta_graph_access_token

    settings = get_settings()
    base = settings.meta_graph_api_base_url.rstrip("/")
    ver = settings.meta_graph_api_version.strip().lstrip("/")
    url = f"{base}/{ver}/{phone_id}/register"

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"messaging_product": "whatsapp", "pin": pin},
        )

    print("HTTP", r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)

    await engine.dispose()
    raise SystemExit(0 if r.is_success else 1)


if __name__ == "__main__":
    asyncio.run(main())

