"""
Unit tests for CompanyService.

All repository calls are replaced with AsyncMocks so tests run
with no database I/O.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.company import CompanyCreate, CompanyStatusUpdate
from app.schemas.common import CompanyStatus


def _make_company(
    name: str = "test-co",
    display_name: str = "Test Co",
    status: str = "draft",
) -> MagicMock:
    """Build a mock Company ORM object."""
    c = MagicMock()
    c.id = uuid.uuid4()
    c.name = name
    c.display_name = display_name
    c.status = status
    return c


@pytest.fixture
def mock_company_repo():
    repo = AsyncMock()
    repo.get_by_name = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=_make_company())
    repo.get = AsyncMock(return_value=_make_company())
    repo.update = AsyncMock(side_effect=lambda obj, data: obj)
    return repo


@pytest.fixture
def company_service(mock_company_repo):
    from app.services.company_service import CompanyService
    return CompanyService(company_repo=mock_company_repo)


@pytest.mark.unit
class TestCompanyServiceCreate:
    async def test_creates_company_successfully(self, company_service, mock_company_repo):
        payload = CompanyCreate(name="acme", display_name="Acme Corp")
        result = await company_service.create_company(payload)
        mock_company_repo.create.assert_called_once()
        assert result is not None

    async def test_raises_conflict_if_name_taken(self, company_service, mock_company_repo):
        mock_company_repo.get_by_name.return_value = _make_company()
        payload = CompanyCreate(name="acme", display_name="Acme Corp")
        with pytest.raises(ConflictError):
            await company_service.create_company(payload)

    async def test_does_not_create_if_name_taken(self, company_service, mock_company_repo):
        mock_company_repo.get_by_name.return_value = _make_company()
        payload = CompanyCreate(name="acme", display_name="Acme Corp")
        try:
            await company_service.create_company(payload)
        except ConflictError:
            pass
        mock_company_repo.create.assert_not_called()


@pytest.mark.unit
class TestCompanyServiceGetById:
    async def test_returns_company(self, company_service, mock_company_repo):
        cid = uuid.uuid4()
        mock_company_repo.get.return_value = _make_company()
        result = await company_service.get_company_by_id(cid)
        assert result is not None

    async def test_raises_not_found_when_missing(self, company_service, mock_company_repo):
        mock_company_repo.get.return_value = None
        with pytest.raises(NotFoundError):
            await company_service.get_company_by_id(uuid.uuid4())


@pytest.mark.unit
class TestCompanyServiceUpdateStatus:
    async def test_updates_status(self, company_service, mock_company_repo):
        company = _make_company(status="draft")
        mock_company_repo.get.return_value = company
        payload = CompanyStatusUpdate(status=CompanyStatus.INACTIVE)
        await company_service.update_company_status(company.id, payload)
        mock_company_repo.update.assert_called_once()

    async def test_raises_not_found_when_missing(self, company_service, mock_company_repo):
        mock_company_repo.get.return_value = None
        with pytest.raises(NotFoundError):
            await company_service.update_company_status(
                uuid.uuid4(), CompanyStatusUpdate(status=CompanyStatus.INACTIVE)
            )
