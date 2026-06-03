"""Repositories for WhatsApp campaigns and outbox."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whatsapp_campaign import (
    WhatsAppCampaign,
    WhatsAppCampaignRecipient,
    WhatsAppFollowupRule,
    WhatsAppOutboxJob,
    WhatsAppSuppression,
)
from app.repositories.base import BaseRepository


class WhatsAppCampaignRepository(BaseRepository[WhatsAppCampaign]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(WhatsAppCampaign, db)

    async def list_for_company(self, company_id: uuid.UUID, limit: int = 100) -> list[WhatsAppCampaign]:
        result = await self.db.execute(
            select(WhatsAppCampaign)
            .where(WhatsAppCampaign.company_id == company_id)
            .order_by(WhatsAppCampaign.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class WhatsAppRecipientRepository(BaseRepository[WhatsAppCampaignRecipient]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(WhatsAppCampaignRecipient, db)

    async def list_for_campaign(self, campaign_id: uuid.UUID, limit: int = 200) -> list[WhatsAppCampaignRecipient]:
        result = await self.db.execute(
            select(WhatsAppCampaignRecipient)
            .where(WhatsAppCampaignRecipient.campaign_id == campaign_id)
            .order_by(WhatsAppCampaignRecipient.row_index.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


class WhatsAppFollowupRuleRepository(BaseRepository[WhatsAppFollowupRule]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(WhatsAppFollowupRule, db)

    async def list_for_company(self, company_id: uuid.UUID) -> list[WhatsAppFollowupRule]:
        result = await self.db.execute(
            select(WhatsAppFollowupRule)
            .where(WhatsAppFollowupRule.company_id == company_id)
            .order_by(WhatsAppFollowupRule.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active(self, company_id: Optional[uuid.UUID] = None) -> list[WhatsAppFollowupRule]:
        stmt = select(WhatsAppFollowupRule).where(WhatsAppFollowupRule.is_active.is_(True))
        if company_id:
            stmt = stmt.where(WhatsAppFollowupRule.company_id == company_id)
        result = await self.db.execute(stmt.order_by(WhatsAppFollowupRule.created_at.asc()))
        return list(result.scalars().all())


class WhatsAppOutboxRepository(BaseRepository[WhatsAppOutboxJob]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(WhatsAppOutboxJob, db)

    async def list_due(self, limit: int) -> list[WhatsAppOutboxJob]:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(WhatsAppOutboxJob)
            .where(
                WhatsAppOutboxJob.status == "queued",
                WhatsAppOutboxJob.next_attempt_at <= now,
            )
            .order_by(WhatsAppOutboxJob.next_attempt_at.asc(), WhatsAppOutboxJob.created_at.asc())
            .limit(max(1, limit))
        )
        return list(result.scalars().all())

    async def list_for_company(
        self,
        company_id: uuid.UUID,
        *,
        campaign_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[WhatsAppOutboxJob]:
        stmt = select(WhatsAppOutboxJob).where(WhatsAppOutboxJob.company_id == company_id)
        if campaign_id:
            stmt = stmt.where(WhatsAppOutboxJob.campaign_id == campaign_id)
        if status:
            stmt = stmt.where(WhatsAppOutboxJob.status == status)
        result = await self.db.execute(
            stmt.order_by(WhatsAppOutboxJob.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def counts_for_campaign(self, campaign_id: uuid.UUID) -> dict[str, int]:
        result = await self.db.execute(
            select(WhatsAppOutboxJob.status, func.count())
            .where(WhatsAppOutboxJob.campaign_id == campaign_id)
            .group_by(WhatsAppOutboxJob.status)
        )
        return {str(status): int(count) for status, count in result.all()}

    async def exists_followup_job(
        self,
        *,
        conversation_id: uuid.UUID,
        followup_rule_id: uuid.UUID,
        step_index: int,
    ) -> bool:
        result = await self.db.execute(
            select(WhatsAppOutboxJob.id)
            .where(
                WhatsAppOutboxJob.conversation_id == conversation_id,
                WhatsAppOutboxJob.followup_rule_id == followup_rule_id,
                WhatsAppOutboxJob.followup_step_index == step_index,
                WhatsAppOutboxJob.status.in_(["queued", "sending", "sent"]),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


class WhatsAppSuppressionRepository(BaseRepository[WhatsAppSuppression]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(WhatsAppSuppression, db)

    async def get_for_phone(self, company_id: uuid.UUID, phone_number: str) -> Optional[WhatsAppSuppression]:
        result = await self.db.execute(
            select(WhatsAppSuppression)
            .where(
                WhatsAppSuppression.company_id == company_id,
                WhatsAppSuppression.phone_number == phone_number,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()
