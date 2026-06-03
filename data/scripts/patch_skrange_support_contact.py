"""
Patch skrange (SK Group) company config:

1. Update fallback_config_json so that when RAG cannot answer, the bot
   politely redirects the customer to the support team (9311443728) instead
   of giving a generic "I don't know" message.

2. Append a hard rule to the system_prompt instructing the LLM to never
   continue with assumptions — connect to support when information is absent.

Run inside the API container (or locally with DB env vars set):

    python data/scripts/patch_skrange_support_contact.py

Idempotent: safe to re-run.
"""
from __future__ import annotations

import asyncio
import uuid

from app.core.database import AsyncSessionLocal
from app.repositories.company_config_repository import CompanyConfigRepository

SK_GROUP_ID = uuid.UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")
SUPPORT_PHONE = "9311443728"

FALLBACK_MESSAGES = {
    "english": (
        "I'm sorry, I don't have the exact information on this right now. "
        f"Please connect with our support team at {SUPPORT_PHONE} — "
        "they'll be happy to help you further."
    ),
    "hinglish": (
        "Sorry, is baare mein mujhe abhi exact information nahi hai. "
        f"Please hamare support team se {SUPPORT_PHONE} par baat karein — "
        "woh aapki poori madad karenge."
    ),
    "hindi": (
        "माफ करें, इस बारे में अभी मेरे पास सटीक जानकारी नहीं है। "
        f"कृपया हमारी support team से {SUPPORT_PHONE} पर संपर्क करें — "
        "वे आपकी पूरी सहायता करेंगे।"
    ),
}

SUPPORT_RULE = (
    "\n\n## Critical Behavior Rule\n"
    "If the required information is NOT available in the knowledge base or context provided, "
    "do NOT continue the conversation with guesses or assumptions. "
    "Instead, politely tell the customer you don't have that information right now "
    f"and ask them to contact the support team at {SUPPORT_PHONE}. "
    "Example: \"I'm sorry, I don't have the exact information on this right now. "
    f"Please connect with our support team at {SUPPORT_PHONE} — they'll be happy to help you.\""
)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        repo = CompanyConfigRepository(db)
        cfg = await repo.get_by_company(SK_GROUP_ID)
        if not cfg:
            raise SystemExit("No company_configs row found for SK Group.")

        # ── 1. Update fallback_config_json ─────────────────────────────── #
        existing_fallback = cfg.fallback_config_json or {}
        updated_fallback = {**existing_fallback, **FALLBACK_MESSAGES}
        cfg.fallback_config_json = updated_fallback

        # ── 2. Append support rule to system_prompt ────────────────────── #
        current_prompt = (cfg.system_prompt or "").strip()
        if SUPPORT_RULE.strip() not in current_prompt:
            cfg.system_prompt = current_prompt + SUPPORT_RULE

        await db.commit()
        print(
            f"OK: skrange fallback_config_json updated with support number {SUPPORT_PHONE}.\n"
            f"OK: system_prompt patched with no-assumption rule.\n"
            f"  system_prompt length: {len(cfg.system_prompt or '')} chars\n"
            f"  fallback_config_json keys: {list(updated_fallback.keys())}"
        )


if __name__ == "__main__":
    asyncio.run(main())
