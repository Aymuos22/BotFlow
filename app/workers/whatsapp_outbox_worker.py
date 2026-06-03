"""Poll and send due WhatsApp campaign/follow-up outbox jobs."""
from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging_config import setup_logging
from app.services.whatsapp_campaign_service import WhatsAppCampaignService

logger = logging.getLogger(__name__)


async def run_once() -> int:
    async with AsyncSessionLocal() as db:
        try:
            count = await WhatsAppCampaignService(db).process_due_outbox_once()
            await db.commit()
            return count
        except Exception:
            await db.rollback()
            raise


_TEMPLATE_POLL_INTERVAL = 60  # seconds between Meta template approval checks
_last_template_poll: float = 0.0


async def poll_pending_templates() -> None:
    """Check Meta template approval for pending_template campaigns and auto-start them."""
    global _last_template_poll
    import time
    now = time.monotonic()
    if now - _last_template_poll < _TEMPLATE_POLL_INTERVAL:
        return
    _last_template_poll = now
    async with AsyncSessionLocal() as db:
        try:
            started = await WhatsAppCampaignService(db).auto_start_pending_campaigns()
            await db.commit()
            if started:
                logger.info("Auto-started campaigns after template approval", extra={"count": started})
        except Exception as exc:
            await db.rollback()
            logger.warning("Template poll failed", extra={"error": str(exc)})


async def run_forever() -> None:
    setup_logging(settings.log_level)
    logger.info("WhatsApp outbox worker started")
    while True:
        try:
            count = await run_once()
            if count:
                logger.info("WhatsApp outbox batch processed", extra={"count": count})
            await poll_pending_templates()
        except Exception as exc:
            logger.exception("WhatsApp outbox worker iteration failed", extra={"error": str(exc)})
        await asyncio.sleep(max(1, settings.whatsapp_outbox_poll_seconds))


if __name__ == "__main__":
    asyncio.run(run_forever())
