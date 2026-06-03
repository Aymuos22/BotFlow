"""
Repository for the CompanyConfig domain model.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_config import CompanyConfig
from app.repositories.base import BaseRepository


class CompanyConfigRepository(BaseRepository[CompanyConfig]):
    """Async repository for CompanyConfig records."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(CompanyConfig, db)

    async def get_by_company(self, company_id: UUID) -> Optional[CompanyConfig]:
        """Retrieve the config for a given company_id (one-to-one)."""
        result = await self.db.execute(
            select(CompanyConfig).where(CompanyConfig.company_id == company_id)
        )
        return result.scalar_one_or_none()

    async def get_by_weaviate_collection(
        self, collection_name: str
    ) -> Optional[CompanyConfig]:
        """Retrieve config by Weaviate collection name."""
        result = await self.db.execute(
            select(CompanyConfig).where(
                CompanyConfig.weaviate_collection == collection_name
            )
        )
        return result.scalar_one_or_none()

    async def get_by_twilio_number(
        self, twilio_whatsapp_number: str
    ) -> Optional[CompanyConfig]:
        """
        Retrieve config by Twilio WhatsApp sender number.

        Used for inbound webhook routing: the ``To`` field in Twilio's webhook
        payload contains the Twilio number that received the message, which we
        map to the correct company.

        Args:
            twilio_whatsapp_number: Number in ``whatsapp:+<E.164>`` format,
                                    e.g. ``whatsapp:+14155238886``.
        """
        result = await self.db.execute(
            select(CompanyConfig).where(
                CompanyConfig.twilio_whatsapp_number == twilio_whatsapp_number
            )
        )
        return result.scalar_one_or_none()

    async def get_by_aisensy_number(
        self, aisensy_whatsapp_number: str
    ) -> Optional[CompanyConfig]:
        """
        Retrieve config by AiSensy / WABA business WhatsApp number.

        Used for inbound webhook routing when ``whatsapp_provider == "aisensy"``.
        """
        result = await self.db.execute(
            select(CompanyConfig).where(
                CompanyConfig.aisensy_whatsapp_number == aisensy_whatsapp_number
            )
        )
        return result.scalar_one_or_none()

    async def get_by_meta_phone_number_id(
        self, phone_number_id: str
    ) -> Optional[CompanyConfig]:
        """Route Meta Cloud API webhooks: metadata.phone_number_id → tenant."""
        result = await self.db.execute(
            select(CompanyConfig).where(
                CompanyConfig.meta_phone_number_id == phone_number_id
            )
        )
        return result.scalar_one_or_none()

    async def list_configs_with_meta_phone_number(self) -> list[CompanyConfig]:
        """Companies that have Meta Cloud API routing id (for webhook GET verify)."""
        result = await self.db.execute(
            select(CompanyConfig).where(CompanyConfig.meta_phone_number_id.isnot(None))
        )
        return list(result.scalars().all())
