"""
LLM-based lead temperature (hot / warm / cold) from recent customer messages.

Skips if ``conversation.lead_warmth_locked`` is true (set from the portal).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository

logger = logging.getLogger(__name__)

_MAX_CUSTOMER_CHUNKS = 8
_MAX_CHARS_PER_MSG = 800

_CLASSIFIER_SYSTEM = """You label WhatsApp leads for a customer-support bot (health / wellness / products).

Return exactly one JSON object and nothing else (no markdown fences):
{"warmth":"hot"|"warm"|"cold"}

Use only the customer's own messages (English, Hindi, Hinglish, or mixed — infer intent).

- hot: strong buying intent, urgency, asking price/checkout/delivery, ready to order, or repeated detailed purchase-related questions
- warm: real interest: product details, benefits, how to use, comparison, or clear pre-purchase questions, but not clearly ready to pay
- cold: only greetings, vague chat, off-topic, obvious browsing with no product focus, or disinterest

If unsure, choose "warm". Never output text outside the JSON."""


def _parse_warmth(raw: str) -> Optional[str]:
    if not raw or not raw.strip():
        return None
    t = raw.strip()
    m = re.search(
        r'\{\s*"warmth"\s*:\s*"(hot|warm|cold)"\s*\}',
        t,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).lower()
    try:
        data = json.loads(t)
        if isinstance(data, dict) and "warmth" in data:
            w = str(data["warmth"]).lower().strip()
            if w in ("hot", "warm", "cold"):
                return w
    except json.JSONDecodeError:
        pass
    return None


def _classify_with_groq_sync(customer_lines: str) -> str:
    s = get_settings()
    from groq import Groq  # type: ignore[import-not-found]

    key = s.groq_api_key
    client = Groq(api_key=key) if key else Groq()
    r = client.chat.completions.create(
        model=s.llm_model,
        messages=[
            {"role": "system", "content": _CLASSIFIER_SYSTEM},
            {
                "role": "user",
                "content": f"Customer messages (newest last):\n{customer_lines}",
            },
        ],
        temperature=0.1,
        max_tokens=64,
    )
    ch = r.choices[0].message
    return (ch.content or "").strip()


def _classify_with_openai_sync(customer_lines: str) -> str:
    s = get_settings()
    from openai import OpenAI  # type: ignore[import-not-found]

    key = s.openai_api_key
    if not key:
        return ""
    client = OpenAI(api_key=key)
    r = client.chat.completions.create(
        model=s.llm_model,
        messages=[
            {"role": "system", "content": _CLASSIFIER_SYSTEM},
            {
                "role": "user",
                "content": f"Customer messages (newest last):\n{customer_lines}",
            },
        ],
        temperature=0.1,
        max_tokens=64,
    )
    ch = r.choices[0].message
    return (ch.content or "").strip()


def _classify_text_sync(text: str) -> str:
    s = get_settings()
    prov = (s.llm_provider or "groq").strip().lower()
    if prov == "openai":
        return _classify_with_openai_sync(text)
    return _classify_with_groq_sync(text)


def _build_customer_excerpt(msgs: List[Any]) -> str:
    """msgs: message rows, newest last."""
    out: list[str] = []
    for m in msgs:
        if getattr(m, "sender_type", None) != "customer":
            continue
        t = (m.message_text or "").strip()
        if not t:
            continue
        if len(t) > _MAX_CHARS_PER_MSG:
            t = t[:_MAX_CHARS_PER_MSG] + "…"
        out.append(t)
    return "\n---\n".join(out[-_MAX_CUSTOMER_CHUNKS:])


async def classify_lead_warmth_for_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    company_id: uuid.UUID,
) -> None:
    """
    If the conversation is not locked, derive hot/warm/cold from recent customer
    messages and update ``lead_warmth``.
    """
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)

    conv = await conv_repo.get(conversation_id)
    if not conv or conv.company_id != company_id:
        return
    if bool(getattr(conv, "is_blocked", False)):
        return
    if bool(getattr(conv, "lead_warmth_locked", False)):
        return

    recent = await msg_repo.list_recent_for_conversation(
        conversation_id, limit=60
    )
    if not recent:
        return
    block = _build_customer_excerpt(list(recent))
    if not block or len(block) < 3:
        return

    try:
        raw = await asyncio.to_thread(_classify_text_sync, block)
    except Exception:
        logger.exception(
            "Lead warmth LLM call failed",
            extra={"conversation_id": str(conversation_id)},
        )
        return
    warmth = _parse_warmth(raw)
    if warmth not in ("hot", "warm", "cold"):
        logger.warning(
            "Lead warmth parse miss",
            extra={"conversation_id": str(conversation_id), "raw": raw[:200]},
        )
        return

    await conv_repo.update(conv, {"lead_warmth": warmth})
    await db.flush()


async def run_lead_warmth_after_inbound(
    conversation_id: str, company_id: str
) -> None:
    """
    Entry point for FastAPI ``BackgroundTasks``: own DB session and commit.
    """
    try:
        cid = uuid.UUID(conversation_id)
        coid = uuid.UUID(company_id)
    except ValueError:
        logger.warning("Lead warmth: bad UUID in background task", extra={})
        return

    from app.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            await classify_lead_warmth_for_conversation(db, cid, coid)
            await db.commit()
    except Exception:
        logger.exception(
            "Lead warmth background task failed",
            extra={"conversation_id": conversation_id, "company_id": company_id},
        )
