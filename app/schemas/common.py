"""
Shared Pydantic types and enumerations used across schemas.
"""
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class CompanyStatus(str, Enum):
    """Lifecycle status for a Company."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class ChannelType(str, Enum):
    """Supported inbound channel types (Phase 1: WhatsApp only)."""
    WHATSAPP = "whatsapp"


class ChannelStatus(str, Enum):
    """Status of a communication channel."""
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class LanguageOptionRead(BaseModel):
    """One row returned by GET /api/v1/meta/languages for UI labels."""

    code: str = Field(description="Stored on CompanyConfig.supported_languages")
    label: str = Field(description="Short UI title")
    description: str = Field(description="Helper text for checkboxes / selects")


# Single source of truth: codes and human-readable copy for portal / admin UIs.
LANGUAGE_CATALOG: List[LanguageOptionRead] = [
    LanguageOptionRead(
        code="english",
        label="English",
        description="Formal or casual replies in English.",
    ),
    LanguageOptionRead(
        code="hindi",
        label="Hindi (Devanagari)",
        description="Replies in Hindi using देवनागरी script.",
    ),
    LanguageOptionRead(
        code="hinglish",
        label="Hinglish (Roman Hindi)",
        description="Roman-script Hindi mixed with English (typical WhatsApp style).",
    ),
]

SUPPORTED_LANGUAGES: List[str] = [o.code for o in LANGUAGE_CATALOG]
