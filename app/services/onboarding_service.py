"""
OnboardingService – one-click company onboarding and activation.

Orchestrates the full onboarding flow:
  1. Create Company row
  2. Generate deterministic Weaviate collection name
  3. Create CompanyConfig row (WhatsApp provider: Twilio)
  4. Create CompanyChannel row
  5. Create OnboardingStatus row
  6. Call Weaviate to create collection (non-fatal failure)
  7. Update OnboardingStatus flags
  8. Return OnboardingSummary with next_steps

Activation gate (all must be True):
  - config_saved
  - weaviate_ready
  - Twilio credentials present on CompanyConfig (number, Account SID, Auth Token)
"""
import logging
from typing import List
from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError, PreconditionFailedError
from app.integrations.weaviate.client import WeaviateClient
from app.models.company_config import CompanyConfig
from app.repositories.company_channel_repository import CompanyChannelRepository
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.onboarding_status_repository import OnboardingStatusRepository
from app.schemas.company import CompanyRead
from app.schemas.company_channel import CompanyChannelRead
from app.schemas.company_config import CompanyConfigRead
from app.schemas.onboarding import (
    ActivationResponse,
    FullOnboardingRequest,
    OnboardingStatusRead,
    OnboardingSummary,
    ReadinessResponse,
)
from app.utils.naming import (
    generate_twilio_channel_key,
    generate_weaviate_collection_name,
)

logger = logging.getLogger(__name__)


class OnboardingService:
    """
    Orchestrates the multi-step company onboarding and activation flow.
    """

    def __init__(
        self,
        company_repo: CompanyRepository,
        config_repo: CompanyConfigRepository,
        channel_repo: CompanyChannelRepository,
        onboarding_repo: OnboardingStatusRepository,
        weaviate_client: WeaviateClient,
    ) -> None:
        self.company_repo = company_repo
        self.config_repo = config_repo
        self.channel_repo = channel_repo
        self.onboarding_repo = onboarding_repo
        self.weaviate_client = weaviate_client

    @staticmethod
    def _twilio_configured(config: CompanyConfig | None) -> bool:
        if config is None:
            return False
        return bool(
            config.twilio_whatsapp_number
            and config.twilio_account_sid
            and config.twilio_auth_token
        )

    def _is_ready_to_activate(self, onboarding, config: CompanyConfig | None) -> bool:
        return bool(
            onboarding.config_saved
            and onboarding.weaviate_ready
            and self._twilio_configured(config)
        )

    async def full_onboard(self, payload: FullOnboardingRequest) -> OnboardingSummary:
        """
        Execute the full one-click onboarding flow.

        Returns an OnboardingSummary regardless of whether Weaviate
        calls succeeded.  Failures in external services are non-fatal and
        reflected in the onboarding_status flags.

        Raises:
            ConflictError: If the company name is already taken.
        """
        existing = await self.company_repo.get_by_name(payload.company_name)
        if existing:
            raise ConflictError(
                f"A company with name '{payload.company_name}' already exists."
            )

        existing_channel = await self.channel_repo.get_by_phone_number(payload.phone_number)
        if existing_channel:
            raise ConflictError(
                f"WhatsApp phone number '{payload.phone_number}' is already registered "
                f"to another company."
            )

        company = await self.company_repo.create(
            {
                "name": payload.company_name,
                "display_name": payload.display_name,
                "status": "draft",
            }
        )
        company_id = company.id
        logger.info("Company row created", extra={"company_id": str(company_id)})

        collection_name = generate_weaviate_collection_name(company_id)
        channel_key = generate_twilio_channel_key(company_id)

        config = await self.config_repo.create(
            {
                "company_id": company_id,
                "weaviate_collection": collection_name,
                "whatsapp_provider": "twilio",
                "default_language": payload.default_language,
                "supported_languages": payload.supported_languages,
                "system_prompt": payload.system_prompt,
                "rag_config_json": payload.rag_config_json,
                "fallback_config_json": payload.fallback_config_json,
                "handoff_config_json": payload.handoff_config_json,
                "business_hours_json": payload.business_hours_json,
                "is_active": True,
            }
        )
        logger.info("Config row created", extra={"company_id": str(company_id)})

        existing_primary = await self.channel_repo.get_primary_by_company(
            company_id, "whatsapp"
        )
        if existing_primary:
            raise ConflictError(
                "Company already has a primary WhatsApp channel."
            )
        channel = await self.channel_repo.create(
            {
                "company_id": company_id,
                "channel_type": "whatsapp",
                "phone_number": payload.phone_number,
                "session_name": channel_key,
                "is_primary": True,
                "status": "pending",
            }
        )

        onboarding = await self.onboarding_repo.create(
            {
                "company_id": company_id,
                "config_saved": True,
                "weaviate_ready": False,
                "activated": False,
            }
        )

        weaviate_ok = False
        weaviate_error: str | None = None
        try:
            await self.weaviate_client.create_collection(collection_name)
            weaviate_ok = True
            logger.info(
                "Weaviate collection created",
                extra={"collection": collection_name},
            )
        except Exception as exc:
            weaviate_error = str(exc)
            logger.warning(
                "Weaviate collection creation failed (non-fatal)",
                extra={"collection": collection_name, "error": weaviate_error},
            )

        last_error = weaviate_error
        onboarding = await self.onboarding_repo.update(
            onboarding,
            {
                "weaviate_ready": weaviate_ok,
                "last_error": last_error,
            },
        )

        next_steps = self._build_next_steps(weaviate_ok=weaviate_ok)

        ready = self._is_ready_to_activate(onboarding, config)

        return OnboardingSummary(
            company=CompanyRead.model_validate(company),
            config=CompanyConfigRead.model_validate(config),
            channel=CompanyChannelRead.model_validate(channel),
            onboarding_status=self._to_status_read(onboarding, config, ready),
            next_steps=next_steps,
        )

    async def get_readiness(self, company_id: UUID) -> ReadinessResponse:
        """
        Return the current onboarding readiness for a company.

        Raises:
            NotFoundError: If the company does not exist.
        """
        company = await self.company_repo.get(company_id)
        if not company:
            raise NotFoundError("Company", str(company_id))

        onboarding = await self.onboarding_repo.get_by_company(company_id)
        if not onboarding:
            raise NotFoundError("OnboardingStatus", str(company_id))

        config = await self.config_repo.get_by_company(company_id)
        ready = self._is_ready_to_activate(onboarding, config)
        blocking = self._get_blocking_reasons(onboarding, config)

        return ReadinessResponse(
            company_id=company_id,
            company_name=company.name,
            onboarding_status=self._to_status_read(onboarding, config, ready),
            is_ready_to_activate=ready,
            blocking_reasons=blocking,
        )

    async def activate_company(self, company_id: UUID) -> ActivationResponse:
        """
        Activate a company after verifying all readiness gates.

        Requires config_saved, weaviate_ready, and Twilio credentials on CompanyConfig.
        """
        company = await self.company_repo.get(company_id)
        if not company:
            raise NotFoundError("Company", str(company_id))

        onboarding = await self.onboarding_repo.get_by_company(company_id)
        if not onboarding:
            raise NotFoundError("OnboardingStatus", str(company_id))

        config = await self.config_repo.get_by_company(company_id)
        if not self._is_ready_to_activate(onboarding, config):
            reasons = self._get_blocking_reasons(onboarding, config)
            raise PreconditionFailedError(
                f"Company is not ready to activate. Blocking: {'; '.join(reasons)}"
            )

        await self.company_repo.update(company, {"status": "active"})
        await self.onboarding_repo.update(onboarding, {"activated": True})

        logger.info("Company activated", extra={"company_id": str(company_id)})
        return ActivationResponse(
            company_id=company_id,
            activated=True,
            message="Company activated successfully.",
        )

    def _to_status_read(self, onboarding, config: CompanyConfig | None, ready: bool) -> OnboardingStatusRead:
        return OnboardingStatusRead(
            id=onboarding.id,
            company_id=onboarding.company_id,
            config_saved=onboarding.config_saved,
            weaviate_ready=onboarding.weaviate_ready,
            activated=onboarding.activated,
            last_error=onboarding.last_error,
            updated_at=onboarding.updated_at,
            is_ready_to_activate=ready,
            twilio_configured=self._twilio_configured(config),
        )

    @staticmethod
    def _get_blocking_reasons(onboarding, config: CompanyConfig | None) -> List[str]:
        reasons: List[str] = []
        if not onboarding.config_saved:
            reasons.append("Company config has not been saved yet.")
        if not onboarding.weaviate_ready:
            reasons.append("Weaviate collection has not been created.")
        if not OnboardingService._twilio_configured(config):
            reasons.append(
                "Twilio is not configured. Set Twilio WhatsApp number, Account SID, "
                "and Auth Token in the portal."
            )
        return reasons

    @staticmethod
    def _build_next_steps(*, weaviate_ok: bool) -> List[str]:
        steps: List[str] = []
        if not weaviate_ok:
            steps.append(
                "Weaviate collection creation failed. Check Weaviate connectivity."
            )
        steps.append(
            "Configure Twilio (WhatsApp number, Account SID, Auth Token) in the portal."
        )
        steps.append(
            "Then activate the company: POST /api/v1/companies/{id}/activate"
        )
        return steps
