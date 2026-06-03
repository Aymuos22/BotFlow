"""
WeaviateCollectionService – Weaviate collection lifecycle management.

Phase 1: create / check / delete collections only.
Phase 2 will add document ingestion and vector search methods.

Future S3 readiness:
  When document ingestion is built, the collection schema will include
  ``s3_bucket`` and ``s3_key`` text properties so metadata for every
  ingested chunk points back to the source S3 object.
"""
import logging
from uuid import UUID

from app.core.exceptions import ExternalServiceError, NotFoundError
from app.integrations.weaviate.client import WeaviateClient
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.onboarding_status_repository import OnboardingStatusRepository

logger = logging.getLogger(__name__)


class WeaviateCollectionService:
    """
    Manages Weaviate collection operations for a given company.
    """

    def __init__(
        self,
        config_repo: CompanyConfigRepository,
        onboarding_repo: OnboardingStatusRepository,
        weaviate_client: WeaviateClient,
    ) -> None:
        self.config_repo = config_repo
        self.onboarding_repo = onboarding_repo
        self.weaviate_client = weaviate_client

    async def _get_collection_name(self, company_id: UUID) -> str:
        config = await self.config_repo.get_by_company(company_id)
        if not config:
            raise NotFoundError("CompanyConfig", str(company_id))
        return config.weaviate_collection

    async def ensure_collection(self, company_id: UUID) -> bool:
        """
        Create the Weaviate collection if it does not already exist.

        Updates ``onboarding_status.weaviate_ready`` on success.

        Returns:
            True if collection was created or already existed.
        """
        collection_name = await self._get_collection_name(company_id)

        await self.weaviate_client.ensure_indexing_collection(collection_name)

        onboarding = await self.onboarding_repo.get_by_company(company_id)
        if onboarding:
            await self.onboarding_repo.update(
                onboarding, {"weaviate_ready": True}
            )

        logger.info(
            "Weaviate collection ensured",
            extra={"company_id": str(company_id), "collection": collection_name},
        )
        return True

    async def collection_exists(self, company_id: UUID) -> bool:
        """Check whether the company's Weaviate collection exists."""
        collection_name = await self._get_collection_name(company_id)
        return await self.weaviate_client.collection_exists(collection_name)

    async def delete_collection(self, company_id: UUID) -> bool:
        """Delete the company's Weaviate collection."""
        collection_name = await self._get_collection_name(company_id)
        result = await self.weaviate_client.delete_collection(collection_name)

        onboarding = await self.onboarding_repo.get_by_company(company_id)
        if onboarding:
            await self.onboarding_repo.update(
                onboarding, {"weaviate_ready": False}
            )

        return result
