"""
ConfigResolutionService – runtime company config resolution.

Used by handlers to route an incoming WhatsApp message to the correct
company's config based on either:
  - company_id (direct lookup)
  - channel ``session_name`` (reverse lookup via company_channels)

This service is intentionally read-only – it never mutates data.
"""
import logging
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.repositories.company_channel_repository import CompanyChannelRepository
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.schemas.company_config import CompanyConfigRead

logger = logging.getLogger(__name__)


class ConfigResolutionService:
    """
    Resolves company configuration for runtime message routing.

    Args:
        company_repo: For fetching company metadata.
        config_repo:  For fetching CompanyConfig records.
        channel_repo: For reverse-looking up company from session_name.
    """

    def __init__(
        self,
        company_repo: CompanyRepository,
        config_repo: CompanyConfigRepository,
        channel_repo: CompanyChannelRepository,
    ) -> None:
        self.company_repo = company_repo
        self.config_repo = config_repo
        self.channel_repo = channel_repo

    async def resolve_by_company_id(self, company_id: UUID) -> CompanyConfigRead:
        """
        Resolve company config by company UUID.

        Args:
            company_id: The company's UUID.

        Returns:
            CompanyConfigRead for the company.

        Raises:
            NotFoundError: If company or config does not exist.
        """
        company = await self.company_repo.get(company_id)
        if not company:
            raise NotFoundError("Company", str(company_id))

        config = await self.config_repo.get_by_company(company_id)
        if not config:
            raise NotFoundError("CompanyConfig", str(company_id))

        logger.debug(
            "Config resolved by company_id",
            extra={"company_id": str(company_id)},
        )
        return CompanyConfigRead.model_validate(config)

    async def resolve_by_session_name(self, session_name: str) -> CompanyConfigRead:
        """
        Resolve company config by channel ``session_name``.

        Args:
            session_name: The channel key stored on ``company_channels.session_name``.

        Returns:
            CompanyConfigRead for the company owning this session.

        Raises:
            NotFoundError: If no channel or config matches the session name.
        """
        channel = await self.channel_repo.get_by_session_name(session_name)
        if not channel:
            raise NotFoundError(
                "CompanyChannel",
                f"session_name={session_name}",
            )

        company = await self.company_repo.get(channel.company_id)
        if not company:
            raise NotFoundError("Company", str(channel.company_id))

        config = await self.config_repo.get_by_company(channel.company_id)
        if not config:
            raise NotFoundError(
                "CompanyConfig",
                f"company_id={channel.company_id}",
            )

        logger.debug(
            "Config resolved by session_name",
            extra={"session_name": session_name, "company_id": str(channel.company_id)},
        )
        return CompanyConfigRead.model_validate(config)
