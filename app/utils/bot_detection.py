"""
Bot / spam detection for inbound WhatsApp messages.

Detection signals
-----------------
1. **Rate flood** – customer sends more than ``max_messages`` in
   ``window_seconds``.  Bots and automated tools blast messages far faster
   than any human can type.

2. **Identical message flood** – the same message text is repeated more than
   ``max_identical`` times in the recent window.  Copy-paste / loop bots do
   this constantly.

3. **Ultra-fast burst** – every one of the last ``burst_count`` messages
   arrived less than ``burst_interval_seconds`` apart.  Humans pause between
   messages; loops do not.

When any signal fires the conversation is permanently blocked:
  - ``Conversation.is_blocked = True``
  - ``Conversation.block_reason`` is set to a human-readable string.

All future inbound messages for a blocked conversation are silently stored
(for audit) but receive no reply — the bot simply returns early.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Detection thresholds (overridable via settings)
# ------------------------------------------------------------------ #

DEFAULT_RATE_WINDOW_SECONDS: int = 60
DEFAULT_MAX_MESSAGES_PER_WINDOW: int = 10

DEFAULT_MAX_IDENTICAL_IN_WINDOW: int = 4

DEFAULT_BURST_COUNT: int = 5
DEFAULT_BURST_INTERVAL_SECONDS: float = 2.0


# ------------------------------------------------------------------ #
# Public helpers
# ------------------------------------------------------------------ #


def is_bot_flood(
    recent_messages: List[Message],
    *,
    window_seconds: int = DEFAULT_RATE_WINDOW_SECONDS,
    max_messages: int = DEFAULT_MAX_MESSAGES_PER_WINDOW,
    max_identical: int = DEFAULT_MAX_IDENTICAL_IN_WINDOW,
    burst_count: int = DEFAULT_BURST_COUNT,
    burst_interval_seconds: float = DEFAULT_BURST_INTERVAL_SECONDS,
) -> Optional[str]:
    """
    Analyse recent *customer* messages and return a block reason string if
    bot behaviour is detected, or ``None`` if the sender looks human.

    Args:
        recent_messages: Messages in chronological order (oldest first).
                         Only ``sender_type == "customer"`` rows are used.
        window_seconds:  Look-back window for rate counting.
        max_messages:    Max allowed customer messages inside the window.
        max_identical:   Max allowed repeats of the same text inside the window.
        burst_count:     Number of consecutive messages to check for ultra-fast
                         burst detection.
        burst_interval_seconds: Max seconds between messages to be counted as
                         part of a burst.

    Returns:
        A non-empty string (block reason) if bot detected, else ``None``.
    """
    customer_msgs = [m for m in recent_messages if m.sender_type == "customer"]
    if not customer_msgs:
        return None

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)

    # Normalise timestamps – DB rows may be naive UTC
    def _utc(ts: datetime) -> datetime:
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts

    window_msgs = [m for m in customer_msgs if _utc(m.created_at) >= cutoff]

    # ── Signal 1: rate flood ──────────────────────────────────────────
    if len(window_msgs) > max_messages:
        reason = (
            f"rate_flood: {len(window_msgs)} messages in {window_seconds}s "
            f"(limit {max_messages})"
        )
        logger.warning("Bot detected – %s", reason)
        return reason

    # ── Signal 2: identical message flood ────────────────────────────
    if window_msgs:
        texts = [m.message_text.strip().lower() for m in window_msgs]
        for text in set(texts):
            count = texts.count(text)
            if count >= max_identical:
                reason = (
                    f"identical_flood: message repeated {count}x in {window_seconds}s"
                )
                logger.warning("Bot detected – %s", reason)
                return reason

    # ── Signal 3: ultra-fast burst ───────────────────────────────────
    if len(customer_msgs) >= burst_count:
        tail = customer_msgs[-burst_count:]
        timestamps = [_utc(m.created_at) for m in tail]
        gaps = [
            (timestamps[i + 1] - timestamps[i]).total_seconds()
            for i in range(len(timestamps) - 1)
        ]
        if all(g < burst_interval_seconds for g in gaps):
            reason = (
                f"ultra_fast_burst: {burst_count} consecutive messages each "
                f"< {burst_interval_seconds}s apart"
            )
            logger.warning("Bot detected – %s", reason)
            return reason

    return None


async def block_conversation(
    conversation: Conversation,
    reason: str,
    db: AsyncSession,
) -> None:
    """
    Permanently mark a conversation as blocked and persist it.

    Idempotent — safe to call even if already blocked.
    """
    if getattr(conversation, "is_blocked", False):
        return

    conv_repo = ConversationRepository(db)
    await conv_repo.update(conversation, {"is_blocked": True, "block_reason": reason})
    conversation.is_blocked = True  # type: ignore[attr-defined]
    conversation.block_reason = reason  # type: ignore[attr-defined]

    logger.info(
        "Conversation blocked (bot/spam detected)",
        extra={
            "conversation_id": str(conversation.id),
            "company_id": str(conversation.company_id),
            "customer_phone": conversation.customer_phone,
            "reason": reason,
        },
    )
