#!/usr/bin/env python3
"""
Copy company_configs from a source tenant to a destination tenant (same DB).

Use this to clone AI settings, integrations secrets, Meta/Twilio/AiSensy tokens,
behaviour JSON, Sheets sync fields, etc. from one company to another — e.g. SK Range
(sk-group) → RCS (rcs).

NEVER copied (destination-specific):
    - id
    - company_id
    - weaviate_collection (bound to tenant / vectors)
    - created_at / updated_at

Routing identifiers (Twilio whatsapp:+…, AiSensy numbers, Meta phone_number_id) are tied
to webhooks — only one tenant can own each value globally (Meta phone_number_id is unique).
Default is to KEEP the destination routing fields (--routing keep-dest) and only refresh
secrets + behaviour from the source.

Use case — **source “clean” only for new connections**: after cloning to another tenant,
remove stored routing + secrets (+ Sheets / handoff WhatsApp notify) on the source so you can paste
**new** Twilio/Meta/AiSensy ids and tokens from the dashboard. Prefer ``--ready-for-new-integrations``
(prompts/RAG/handoff JSON are left untouched). Use ``--sanitize-source`` alone for that same wipe,
or add ``--blank-source-ai`` if you also want AI fields cleared on the source.

Full “move” WhatsApp routing from source → dest (``--routing from-source``), then unplug source with
``--ready-for-new-integrations`` or ``--sanitize-source``.

Examples (from repo root, DATABASE_URL set):
  Dry run (shows what would change):
    python scripts/copy_company_config.py --from sk-group --to rcs --dry-run

  Copy secrets + AI config; keep RCS phone / Meta IDs as-is:
    python scripts/copy_company_config.py --from sk-group --to rcs

  After copy → SK ready for **new** webhook/credentials only (recommended “clean to plug configs”):

    python scripts/copy_company_config.py --from sk-group --to rcs \\
      --routing from-source --ready-for-new-integrations

  Same, but **also** strip prompts/behaviour JSON on SK (RCS already has copies):

    python scripts/copy_company_config.py --from sk-group --to rcs \\
      --routing from-source --sanitize-source --blank-source-ai

  Older granular flags (--clear-source-routing / --clear-source-secrets) still work instead of
  ``--sanitize-source`` if you do not want Sheets/handoff-reset/provider reset on the source.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import or_, select

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.company_config import CompanyConfig  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402


ROUTING_COLUMNS = (
    "twilio_whatsapp_number",
    "twilio_account_sid",
    "meta_phone_number_id",
    "aisensy_whatsapp_number",
    "aisensy_project_id",
)


async def find_company(session, company_key: str) -> Optional[Company]:
    key = company_key.strip()
    key_lower = key.lower()
    uid: UUID | None = None
    try:
        uid = UUID(key)
    except ValueError:
        pass

    predicates = []
    if uid:
        predicates.append(Company.id == uid)
    predicates.extend(
        [
            Company.name == key,
            Company.name == key_lower,
            Company.display_name.ilike(key),
        ]
    )
    result = await session.execute(select(Company).where(or_(*predicates)))
    rows = list(result.scalars().all())
    if len(rows) > 1:
        names = [f"{c.name} ({c.display_name}) {c.id}" for c in rows]
        raise SystemExit(f"Ambiguous company key {company_key!r}; matches:\n  " + "\n  ".join(names))
    return rows[0] if rows else None


def snapshot_public(cfg: CompanyConfig) -> dict[str, Any]:
    return {
        "whatsapp_provider": cfg.whatsapp_provider,
        **{k: getattr(cfg, k, None) for k in ROUTING_COLUMNS},
        "google_sheets_enabled": cfg.google_sheets_enabled,
        "google_sheet_id": cfg.google_sheet_id,
        "google_sheet_url": cfg.google_sheet_url,
        "default_language": cfg.default_language,
        "supported_languages": list(cfg.supported_languages or []) if cfg.supported_languages else [],
        "system_prompt": cfg.system_prompt,
        "rag_config_json": cfg.rag_config_json,
        "fallback_config_json": cfg.fallback_config_json,
        "handoff_config_json": cfg.handoff_config_json,
        "business_hours_json": cfg.business_hours_json,
        "whatsapp_agent_inactivity_minutes": cfg.whatsapp_agent_inactivity_minutes,
        "handoff_staff_notify_whatsapp": cfg.handoff_staff_notify_whatsapp,
        "is_active": cfg.is_active,
    }


def secrets_signature(cfg: CompanyConfig) -> dict[str, bool]:
    return {
        "twilio_auth_token_stored": cfg.has_stored_twilio_auth_token,
        "aisensy_api_key_stored": cfg.has_stored_aisensy_api_key,
        "meta_graph_token_stored": cfg.has_stored_meta_graph_token,
        "meta_app_secret_stored": cfg.has_stored_meta_app_secret,
        "meta_webhook_verify_token_stored": cfg.has_stored_meta_webhook_verify_token,
    }


async def validate_meta_phone_for_destination(
    repo: CompanyConfigRepository,
    dest_company_id: UUID,
    src_company_id: UUID,
    new_meta_phone: Optional[str],
) -> None:
    if not new_meta_phone or not str(new_meta_phone).strip():
        return
    pid = str(new_meta_phone).strip()
    row = await repo.get_by_meta_phone_number_id(pid)
    if row is None:
        return
    if str(row.company_id) == str(dest_company_id):
        return
    if str(row.company_id) == str(src_company_id):
        return
    raise SystemExit(
        f"Cannot assign meta_phone_number_id {pid!r}: already used "
        f"by company_id={row.company_id}."
    )


def copy_secrets_and_behaviour(src: CompanyConfig, dst: CompanyConfig) -> None:
    """Copy decryptable secrets and non-routing behavioural fields."""

    dst.whatsapp_provider = src.whatsapp_provider

    dst.google_sheets_enabled = src.google_sheets_enabled
    dst.google_sheet_id = src.google_sheet_id
    dst.google_sheet_url = src.google_sheet_url

    dst.default_language = src.default_language
    dst.supported_languages = list(src.supported_languages or []) if src.supported_languages else []
    dst.system_prompt = src.system_prompt
    dst.rag_config_json = src.rag_config_json
    dst.fallback_config_json = src.fallback_config_json
    dst.handoff_config_json = src.handoff_config_json
    dst.business_hours_json = src.business_hours_json

    dst.whatsapp_agent_inactivity_minutes = src.whatsapp_agent_inactivity_minutes
    dst.handoff_staff_notify_whatsapp = src.handoff_staff_notify_whatsapp
    dst.is_active = src.is_active

    if src.has_stored_twilio_auth_token:
        dst.twilio_auth_token = src.twilio_auth_token
    else:
        dst.twilio_auth_token = None

    if src.twilio_account_sid:
        dst.twilio_account_sid = src.twilio_account_sid
    # twilio whatsapp routing optional — applied in routing_pass

    if src.has_stored_aisensy_api_key:
        dst.aisensy_api_key = src.aisensy_api_key
    else:
        dst.aisensy_api_key = None

    if src.has_stored_meta_graph_token:
        dst.meta_graph_access_token = src.meta_graph_access_token
    else:
        dst.meta_graph_access_token = None

    if src.has_stored_meta_app_secret:
        dst.meta_app_secret = src.meta_app_secret
    else:
        dst.meta_app_secret = None

    if src.has_stored_meta_webhook_verify_token:
        dst.meta_webhook_verify_token = src.meta_webhook_verify_token
    else:
        dst.meta_webhook_verify_token = None


def apply_routing_from_source(src: CompanyConfig, dst: CompanyConfig) -> None:
    for col in ROUTING_COLUMNS:
        setattr(dst, col, getattr(src, col))


def clear_routing(cfg: CompanyConfig) -> None:
    for col in ROUTING_COLUMNS:
        setattr(cfg, col, None)


def clear_all_secrets(cfg: CompanyConfig) -> None:
    cfg.twilio_auth_token = None
    cfg.twilio_account_sid = None
    cfg.aisensy_api_key = None
    cfg.meta_graph_access_token = None
    cfg.meta_app_secret = None
    cfg.meta_webhook_verify_token = None


def sanitize_source_company_config(src: CompanyConfig, *, blank_ai: bool) -> None:
    """
    Strip SK/source tenant after assets were copied — no webhook routing,
    no stored tokens, neutral provider, Sheets + handoff notify cleared.

    Optionally reset prompts / JSON blobs so the source row is not a duplicate of RCS.
    """
    clear_routing(src)
    clear_all_secrets(src)

    src.whatsapp_provider = "twilio"

    src.google_sheets_enabled = False
    src.google_sheet_id = None
    src.google_sheet_url = None

    src.handoff_staff_notify_whatsapp = None

    if blank_ai:
        src.system_prompt = None
        src.rag_config_json = None
        src.fallback_config_json = None
        src.handoff_config_json = None
        src.business_hours_json = None
        src.default_language = "english"
        src.supported_languages = ["english"]
        src.whatsapp_agent_inactivity_minutes = None


async def _run(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    async with AsyncSessionLocal() as session:
        src_co = await find_company(session, args.from_company)
        dst_co = await find_company(session, args.to_company)
        if src_co is None:
            raise SystemExit(f"No source company matched {args.from_company!r}")
        if dst_co is None:
            raise SystemExit(f"No destination company matched {args.to_company!r}")
        if src_co.id == dst_co.id:
            raise SystemExit("Source and destination are the same company.")

        repo = CompanyConfigRepository(session)
        src = await repo.get_by_company(src_co.id)
        dst = await repo.get_by_company(dst_co.id)
        if src is None or dst is None:
            raise SystemExit("Missing company_configs row for source or destination.")

        routing = args.routing.strip().lower()

        payload = {
            "from": {"id": str(src_co.id), "name": src_co.name, "display_name": src_co.display_name},
            "to": {"id": str(dst_co.id), "name": dst_co.name, "display_name": dst_co.display_name},
            "routing_mode": routing,
            "would_copy_public": snapshot_public(src),
            "would_copy_secret_flags": secrets_signature(src),
            "destination_weaviate_collection_unchanged": dst.weaviate_collection,
        }

        payload["sanitize_source"] = bool(args.sanitize_source)
        payload["blank_source_ai"] = bool(args.blank_source_ai)
        payload["ready_for_new_integrations"] = bool(
            getattr(args, "ready_for_new_integrations", False),
        )

        print(json.dumps(payload, indent=2, default=str))

        if routing == "from-source":
            await validate_meta_phone_for_destination(
                repo, dst_co.id, src_co.id, src.meta_phone_number_id,
            )

        if args.dry_run:
            await session.rollback()
            print("\nDry run — no changes committed.")
            return 0

        copy_secrets_and_behaviour(src, dst)

        if routing == "from-source":
            apply_routing_from_source(src, dst)
        elif routing == "keep-dest":
            pass
        else:
            raise SystemExit(f"Unknown --routing {routing!r}")

        if args.sanitize_source:
            sanitize_source_company_config(src, blank_ai=args.blank_source_ai)
        else:
            if args.clear_source_routing:
                clear_routing(src)

            if args.clear_source_secrets:
                clear_all_secrets(src)

        await session.commit()
        await session.refresh(dst)
        await session.refresh(src)

        summary = {
            "ok": True,
            "destination": {
                "company_id": str(dst_co.id),
                "meta_phone_number_id": dst.meta_phone_number_id,
                "whatsapp_provider": dst.whatsapp_provider,
                "secret_flags": secrets_signature(dst),
            },
            "source": {
                "company_id": str(src_co.id),
                "sanitized": bool(args.sanitize_source),
                "meta_phone_number_id": src.meta_phone_number_id,
                "whatsapp_provider": src.whatsapp_provider,
                "secret_flags": secrets_signature(src),
            },
        }
        print("\nCommitted:\n", json.dumps(summary, indent=2))

    await engine.dispose()
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description="Copy company_configs from one tenant to another (SK Range → RCS, etc.).",
    )
    p.add_argument(
        "--from",
        dest="from_company",
        required=True,
        help="Source slug, display name, or UUID (e.g. sk-group)",
    )
    p.add_argument(
        "--to",
        dest="to_company",
        required=True,
        help="Destination slug, display name, or UUID (e.g. rcs)",
    )
    p.add_argument(
        "--routing",
        choices=("keep-dest", "from-source"),
        default="keep-dest",
        help=(
            "keep-dest: preserve destination Twilio/AiSensy/Meta IDs; refresh tokens + prompts. "
            "from-source: also copy routing fields (must not collide on meta_phone_number_id)."
        ),
    )
    p.add_argument(
        "--ready-for-new-integrations",
        action="store_true",
        help=(
            "After copy: clear source routing + all integration secrets + reset whatsapp_provider to "
            "twilio, disable Google Sheets sync and clear ids/URLs, clear handoff notify — so you can "
            "plug new Meta/Twilio/AiSensy in the portal. Does NOT clear prompts/RAG/handoff JSON "
            "(equivalent to --sanitize-source without --blank-source-ai)."
        ),
    )
    p.add_argument(
        "--sanitize-source",
        action="store_true",
        help=(
            "After copy: clear source routing IDs, wipe all integration secrets on source, "
            "set whatsapp_provider=twilio, disable Google Sheets + clear sheet refs, "
            "clear handoff_staff_notify_whatsapp. Use --blank-source-ai to also strip prompts "
            "and behaviour JSON."
        ),
    )
    p.add_argument(
        "--blank-source-ai",
        action="store_true",
        help=(
            "With --sanitize-source: null prompts/handoff/RAG JSON on source; defaults to english only. "
            "Do not combine with --ready-for-new-integrations."
        ),
    )
    p.add_argument(
        "--clear-source-routing",
        action="store_true",
        help=(
            "After copy: null routing columns on source only. "
            "Not needed when using --sanitize-source (superset)."
        ),
    )
    p.add_argument(
        "--clear-source-secrets",
        action="store_true",
        help="Clear integration secrets on the source after copy (destructive).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON preview and roll back.",
    )
    args = p.parse_args()
    if args.ready_for_new_integrations:
        if args.blank_source_ai:
            raise SystemExit(
                "--ready-for-new-integrations only clears connection fields (for new webhook/creds). "
                "Omit --blank-source-ai, or use --sanitize-source together with --blank-source-ai "
                "if you intend to wipe AI prompts on the source too.",
            )
        args.sanitize_source = True
    if args.blank_source_ai and not args.sanitize_source:
        raise SystemExit("--blank-source-ai requires --sanitize-source.")
    if args.sanitize_source and (args.clear_source_routing or args.clear_source_secrets):
        raise SystemExit(
            "Use --sanitize-source alone (it already clears routing + secrets), "
            "or drop --sanitize-source and use --clear-source-routing / --clear-source-secrets.",
        )

    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
