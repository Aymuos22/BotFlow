"""
Model package – import all ORM models here so Alembic ``env.py``
can import a single symbol (``Base``) and discover all tables.
"""
# Phase 1 models
from app.models.base import Base  # noqa: F401 – re-exported
from app.models.company import Company  # noqa: F401
from app.models.company_config import CompanyConfig  # noqa: F401
from app.models.company_channel import CompanyChannel  # noqa: F401
from app.models.onboarding_status import OnboardingStatus  # noqa: F401

# Phase 2 models
from app.models.document import Document  # noqa: F401
from app.models.document_index_job import DocumentIndexJob  # noqa: F401
from app.models.conversation import Conversation  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.retrieval_log import RetrievalLog  # noqa: F401

# Phase 3 models
from app.models.handoff import Handoff  # noqa: F401
from app.models.daily_company_metrics import DailyCompanyMetrics  # noqa: F401
from app.models.portal_user import PortalUser  # noqa: F401
from app.models.google_sheet_sync_job import GoogleSheetSyncJob  # noqa: F401
from app.models.whatsapp_campaign import (  # noqa: F401
    WhatsAppCampaign,
    WhatsAppCampaignRecipient,
    WhatsAppFollowupRule,
    WhatsAppOutboxJob,
    WhatsAppSuppression,
)

# Phase 4 models
from app.models.product import Product  # noqa: F401
from app.models.product_event import ProductEvent  # noqa: F401

__all__ = [
    "Base",
    # Phase 1
    "Company",
    "CompanyConfig",
    "CompanyChannel",
    "OnboardingStatus",
    # Phase 2
    "Document",
    "DocumentIndexJob",
    "Conversation",
    "Message",
    "RetrievalLog",
    # Phase 3
    "Handoff",
    "DailyCompanyMetrics",
    "PortalUser",
    "GoogleSheetSyncJob",
    # Phase 4
    "Product",
    "ProductEvent",
]
