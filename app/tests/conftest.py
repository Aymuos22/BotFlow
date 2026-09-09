"""
Shared pytest fixtures for the BotFlow test suite.

Test strategy
-------------
- API tests   : httpx.AsyncClient with real in-memory SQLite DB +
                mocked Weaviate / S3 / LLM clients
- Unit tests  : pytest-mock, no DB
- Integration : real in-memory SQLite DB, no HTTP calls

Fixture scopes
--------------
- ``test_engine``          : function-scoped, fresh DB per test (full isolation)
- ``db_session``           : function-scoped, rolls back after each test
- ``client``               : function-scoped, TestClient bound to db_session
- ``mock_weaviate_client`` : function-scoped AsyncMock
- ``mock_storage_client``  : function-scoped MagicMock  [Phase 2]
- ``mock_llm_client``      : function-scoped AsyncMock  [Phase 2]
- ``mock_rag_service``     : function-scoped AsyncMock  [Phase 2]
- ``mock_indexing_service``: function-scoped AsyncMock  [Phase 2]
- ``sample_company_id``    : UUID for an onboarded company [Phase 2/3]
- ``sample_twilio_to``     : Twilio ``whatsapp:+…`` sender on the sample company (webhook routing)
"""
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.utils.naming import generate_twilio_channel_key

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Must match ``CompanyConfig.twilio_whatsapp_number`` on ``sample_company_id``.
SAMPLE_TWILIO_WHATSAPP_TO = "whatsapp:+14155238886"


# ------------------------------------------------------------------ #
# Portal / onboarding auth — tests start without portal locks so existing
# suites keep passing even if .env defines PORTAL_ADMIN_API_KEY or company keys.
# ------------------------------------------------------------------ #


@pytest.fixture(autouse=True)
def _portal_settings_isolated_from_dotenv():
    from app.core import config

    s = config.settings
    old_admin = s.portal_admin_api_key
    old_keys = s.portal_company_keys_json
    old_bootstrap = s.portal_bootstrap_secret
    old_supabase_jwt = s.supabase_jwt_secret
    s.portal_admin_api_key = None
    s.portal_company_keys_json = None
    s.portal_bootstrap_secret = None
    s.supabase_jwt_secret = None
    yield
    s.portal_admin_api_key = old_admin
    s.portal_company_keys_json = old_keys
    s.portal_bootstrap_secret = old_bootstrap
    s.supabase_jwt_secret = old_supabase_jwt


# ------------------------------------------------------------------ #
# Database fixtures
# ------------------------------------------------------------------ #


@pytest.fixture
async def test_engine():
    """
    Creates a brand-new in-memory SQLite engine with all tables.
    Drops tables and disposes engine after the test.
    """
    from app.models.base import Base  # local import avoids circular at collection

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a test session that rolls back all writes after the test,
    ensuring each test starts with a clean database state.
    """
    TestSession = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        autoflush=True,
        autocommit=False,
    )
    async with TestSession() as session:
        yield session
        await session.rollback()


# ------------------------------------------------------------------ #
# Integration client mocks (Phase 1)
# ------------------------------------------------------------------ #


@pytest.fixture
def mock_weaviate_client() -> AsyncMock:
    """Weaviate HTTP client mock with sensible default return values."""
    from app.integrations.weaviate.client import WeaviateClient

    mock = AsyncMock(spec=WeaviateClient)
    mock.create_collection.return_value = True
    mock.ensure_indexing_collection.return_value = True
    mock.collection_exists.return_value = True
    mock.delete_collection.return_value = True
    # Phase 2 extensions
    mock.upsert_document_chunks.return_value = 3
    mock.hybrid_search.return_value = {
        "chunks": ["Relevant chunk 1", "Relevant chunk 2"],
        "top_score": 0.85,
        "raw": {},
    }
    mock.delete_document_chunks.return_value = True
    return mock


# ------------------------------------------------------------------ #
# Integration client mocks (Phase 2)
# ------------------------------------------------------------------ #


@pytest.fixture
def mock_storage_client() -> MagicMock:
    """
    StorageClient mock.

    Note: SupabaseStorageClient methods are SYNC (supabase-py wrapping), so we
    use MagicMock (not AsyncMock) for the storage client.
    """
    from app.integrations.s3.client import SupabaseStorageClient

    mock = MagicMock(spec=SupabaseStorageClient)
    mock.upload_file.return_value = "companies/test/documents/test/file.txt"
    mock.get_file.return_value = b"Sample document content for testing."
    mock.file_exists.return_value = True
    mock.delete_file.return_value = True
    mock.generate_presigned_url.return_value = "https://supabase.example.com/presigned-url"
    return mock


@pytest.fixture
def mock_llm_client() -> AsyncMock:
    """LLM client mock returning a canned answer."""
    from app.integrations.llm.client import LLMClientProtocol

    mock = AsyncMock(spec=LLMClientProtocol)
    mock.generate_answer.return_value = "This is a mock LLM answer for testing."
    return mock


@pytest.fixture
def mock_rag_service() -> AsyncMock:
    """RAGService mock for webhook tests."""
    from app.services.rag_service import RAGService

    mock = AsyncMock(spec=RAGService)
    mock.process_query.return_value = {
        "response_type": "rag",
        "answer": "Here is your mock answer.",
        "fallback_triggered": False,
        "language": "english",
        "detected_language": "english",
    }
    return mock


@pytest.fixture
def mock_indexing_service() -> AsyncMock:
    """IndexingService mock for document API tests."""
    from app.services.indexing_service import IndexingService

    mock = AsyncMock(spec=IndexingService)
    mock.trigger_indexing.return_value = MagicMock(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        status="completed",
        retry_count=1,
        error_message=None,
        started_at=None,
        completed_at=None,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    return mock


# ------------------------------------------------------------------ #
# HTTP test client
# ------------------------------------------------------------------ #


@pytest.fixture
async def client(
    db_session: AsyncSession,
    mock_weaviate_client: AsyncMock,
    mock_storage_client: MagicMock,
    mock_llm_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_indexing_service: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Returns an httpx.AsyncClient pointing at the FastAPI app with:
      - DB dependency overridden to use the test SQLite session
      - Weaviate / S3 / LLM clients overridden with mocks
      - RAGService and IndexingService overridden with mocks
    """
    from app.core.database import get_db
    from app.integrations.llm.client import get_llm_client
    from app.integrations.s3.client import get_storage_client
    from app.integrations.weaviate.client import get_weaviate_client
    from app.main import create_app

    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_weaviate_client] = lambda: mock_weaviate_client
    app.dependency_overrides[get_storage_client] = lambda: mock_storage_client
    app.dependency_overrides[get_llm_client] = lambda: mock_llm_client

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ------------------------------------------------------------------ #
# Convenience data fixtures
# ------------------------------------------------------------------ #


@pytest.fixture
async def sample_company_id(db_session: AsyncSession) -> uuid.UUID:
    """
    Returns a UUID for a company that has been persisted to the test DB.

    Includes Twilio fields so outbound sends and webhook routing can run.
    """
    from app.models.company import Company
    from app.models.company_config import CompanyConfig
    from app.models.company_channel import CompanyChannel
    from app.models.onboarding_status import OnboardingStatus
    from app.models.base import new_uuid

    company_id = new_uuid()
    channel_key = generate_twilio_channel_key(company_id)

    company = Company(
        id=company_id,
        name=f"test-company-{company_id.hex[:8]}",
        display_name="Test Company",
        status="active",
    )
    db_session.add(company)
    await db_session.flush()

    config = CompanyConfig(
        company_id=company_id,
        weaviate_collection=f"Co{company_id.hex[:20]}",
        whatsapp_provider="twilio",
        default_language="english",
        supported_languages=["english"],
        twilio_whatsapp_number=SAMPLE_TWILIO_WHATSAPP_TO,
        twilio_account_sid="AC" + "0" * 32,
    )
    config.twilio_auth_token = "test-auth-token"
    db_session.add(config)

    channel = CompanyChannel(
        company_id=company_id,
        channel_type="whatsapp",
        phone_number="+911234567890",
        session_name=channel_key,
        is_primary=True,
        status="active",
    )
    db_session.add(channel)

    onboarding = OnboardingStatus(
        company_id=company_id,
        config_saved=True,
        weaviate_ready=True,
        activated=True,
    )
    db_session.add(onboarding)
    await db_session.flush()
    return company_id


@pytest.fixture
def sample_twilio_to() -> str:
    """Twilio ``To`` value that routes to ``sample_company_id``."""
    return SAMPLE_TWILIO_WHATSAPP_TO


@pytest.fixture
def valid_onboarding_payload() -> dict:
    """Minimal valid payload for POST /api/v1/onboarding/company/full."""
    return {
        "company_name": "test-company",
        "display_name": "Test Company",
        "phone_number": "+911234567890",
        "default_language": "english",
        "supported_languages": ["english"],
    }
