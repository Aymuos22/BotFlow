#!/usr/bin/env python3
"""
Run one RAG query the same way as POST /api/v1/portal/chat (no HTTP).

Usage (from repo root, .env loaded):

    python scripts/smoke_portal_rag.py
    python scripts/smoke_portal_rag.py --message "Your question here"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Windows consoles often default to cp1252; LLM output may include emoji.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.integrations.embeddings.client import get_embedding_client  # noqa: E402
from app.integrations.llm.client import get_llm_client  # noqa: E402
from app.integrations.weaviate.client import WeaviateClient  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402
from app.services.fallback_service import FallbackService  # noqa: E402
from app.services.rag_service import RAGService  # noqa: E402

SK_GROUP = UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")
DEFAULT_MESSAGE = "Hi Can you help me with stamina issues"


async def _run(message: str) -> int:
    s = get_settings()
    async with AsyncSessionLocal() as db:
        cfg = await CompanyConfigRepository(db).get_by_company(SK_GROUP)
        if not cfg:
            print("ERROR: No company_config for SK Group — onboard company first.", file=sys.stderr)
            return 1

        weaviate = WeaviateClient(
            url=s.weaviate_url,
            api_key=s.weaviate_api_key,
            timeout=s.weaviate_timeout_seconds,
        )
        llm = get_llm_client()
        try:
            rag = RAGService(
                config_repo=CompanyConfigRepository(db),
                weaviate_client=weaviate,
                llm_client=llm,
                fallback_service=FallbackService(),
                default_top_k=s.rag_top_k,
                default_score_threshold=s.rag_score_threshold,
                default_hybrid_alpha=s.rag_hybrid_alpha,
                default_conversation_turns=s.rag_conversation_turns,
                augment_search_with_history=s.rag_augment_search_with_history,
                embedding_client=get_embedding_client(),
            )
            raw = await rag.process_query(
                company_id=SK_GROUP,
                query=message,
                conversation_id=None,
                message_id=None,
                background_tasks=None,
            )
        finally:
            await weaviate.aclose()

    out = {
        "response_type": raw.get("response_type"),
        "answer_preview": (raw.get("answer") or "")[:2000],
        "answer_length": len(raw.get("answer") or ""),
        "top_score": raw.get("top_score"),
        "language": raw.get("language"),
        "fallback_triggered": raw.get("fallback_triggered"),
        "sources_count": len(raw.get("sources") or []),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print()
    print("--- full answer ---")
    print(raw.get("answer") or "")
    return 0


async def _async_main(message: str) -> int:
    try:
        return await _run(message)
    finally:
        await engine.dispose()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--message", "-m", default=DEFAULT_MESSAGE)
    args = p.parse_args()
    raise SystemExit(asyncio.run(_async_main(args.message)))


if __name__ == "__main__":
    main()
