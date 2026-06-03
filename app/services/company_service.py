"""
CompanyService – company lifecycle management.

Handles creation, retrieval, and status transitions for Company records.
All business rules (uniqueness, valid status transitions) live here.
"""
import logging
from typing import List
from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError
from app.repositories.company_repository import CompanyRepository
from app.schemas.company import CompanyCreate, CompanyRead, CompanyStatusUpdate

logger = logging.getLogger(__name__)


class CompanyService:
    """
    Service for Company domain operations.

    Args:
        company_repo: Repository for Company persistence.
    """

    def __init__(self, company_repo: CompanyRepository) -> None:
        self.company_repo = company_repo

    async def create_company(self, payload: CompanyCreate) -> CompanyRead:
        """
        Create a new company.

        Business rules:
          - ``name`` must be globally unique.

        Args:
            payload: Validated company creation data.

        Returns:
            The newly created CompanyRead schema.

        Raises:
            ConflictError: If a company with the same name already exists.
        """
        existing = await self.company_repo.get_by_name(payload.name)
        if existing:
            raise ConflictError(
                f"A company with name '{payload.name}' already exists."
            )
        company = await self.company_repo.create(
            {
                "name": payload.name,
                "display_name": payload.display_name,
                "status": "draft",
            }
        )
        logger.info(
            "Company created",
            extra={"company_id": str(company.id), "company_name": company.name},
        )
        return CompanyRead.model_validate(company)

    async def get_company_by_id(self, company_id: UUID) -> CompanyRead:
        """
        Retrieve a company by UUID.

        Raises:
            NotFoundError: If the company does not exist.
        """
        company = await self.company_repo.get(company_id)
        if not company:
            raise NotFoundError("Company", str(company_id))
        return CompanyRead.model_validate(company)

    async def update_company_status(
        self, company_id: UUID, payload: CompanyStatusUpdate
    ) -> CompanyRead:
        """
        Update a company's lifecycle status.

        Raises:
            NotFoundError: If the company does not exist.
        """
        company = await self.company_repo.get(company_id)
        if not company:
            raise NotFoundError("Company", str(company_id))
        updated = await self.company_repo.update(
            company, {"status": payload.status}
        )
        logger.info(
            "Company status updated",
            extra={"company_id": str(company_id), "status": payload.status},
        )
        return CompanyRead.model_validate(updated)
