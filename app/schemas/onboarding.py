"""
Pydantic schemas for the onboarding domain.

These schemas cover both request payloads and response shapes
for the one-click full-onboarding endpoint and the readiness check.
"""
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import SUPPORTED_LANGUAGES
from app.schemas.company import CompanyRead
from app.schemas.company_channel import CompanyChannelCreate, CompanyChannelRead
from app.schemas.company_config import CompanyConfigCreate, CompanyConfigRead


class FullOnboardingRequest(BaseModel):
    """
    Request body for POST /api/v1/onboarding/company/full.

    A single call creates the company, config, channel, and Weaviate collection.
    Twilio credentials are configured later via the portal.
    """

    company_name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Unique machine-readable company slug",
        examples=["acme-corp"],
    )
    display_name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Human-readable company name",
        examples=["Acme Corporation"],
    )

    phone_number: str = Field(
        ...,
        description="E.164 phone number for the WhatsApp channel",
        examples=["+911234567890"],
    )

    default_language: str = Field(default="english")
    supported_languages: List[str] = Field(default_factory=lambda: ["english"])
    system_prompt: Optional[str] = None
    rag_config_json: Optional[Dict[str, Any]] = None
    fallback_config_json: Optional[Dict[str, Any]] = None
    handoff_config_json: Optional[Dict[str, Any]] = None
    business_hours_json: Optional[Dict[str, Any]] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        if not re.match(r'^\+?[1-9]\d{6,14}$', v.strip()):
            raise ValueError(
                "phone_number must be a valid phone number (E.164 format recommended)"
            )
        return v.strip()

    @field_validator("supported_languages")
    @classmethod
    def validate_supported_languages(cls, v: List[str]) -> List[str]:
        invalid = [lang for lang in v if lang not in SUPPORTED_LANGUAGES]
        if invalid:
            raise ValueError(
                f"Unsupported languages: {invalid}. "
                f"Must be one of {SUPPORTED_LANGUAGES}"
            )
        if not v:
            raise ValueError("At least one language must be specified.")
        return v

    @field_validator("default_language")
    @classmethod
    def validate_default_language(cls, v: str) -> str:
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"default_language must be one of {SUPPORTED_LANGUAGES}"
            )
        return v

    @model_validator(mode="after")
    def default_must_be_supported(self) -> "FullOnboardingRequest":
        if self.default_language not in self.supported_languages:
            raise ValueError(
                "default_language must be included in supported_languages"
            )
        return self


class OnboardingStatusRead(BaseModel):
    """Represents the current onboarding readiness of a company."""
    id: uuid.UUID
    company_id: uuid.UUID
    config_saved: bool
    weaviate_ready: bool
    activated: bool
    last_error: Optional[str]
    updated_at: datetime
    is_ready_to_activate: bool
    twilio_configured: bool = Field(
        description="True when Twilio WhatsApp number, Account SID, and Auth Token are set.",
    )

    model_config = {"from_attributes": True}


class OnboardingSummary(BaseModel):
    """
    Response body for POST /api/v1/onboarding/company/full.

    Includes the created company, config, channel, and onboarding status.
    ``next_steps`` provides human-readable guidance for the admin.
    """
    company: CompanyRead
    config: CompanyConfigRead
    channel: CompanyChannelRead
    onboarding_status: OnboardingStatusRead
    next_steps: List[str] = Field(
        default_factory=list,
        description="Ordered list of actions the admin must take next",
    )


class ReadinessResponse(BaseModel):
    """Response body for GET /api/v1/companies/{id}/readiness."""
    company_id: uuid.UUID
    company_name: str
    onboarding_status: OnboardingStatusRead
    is_ready_to_activate: bool
    blocking_reasons: List[str] = Field(
        default_factory=list,
        description="Why activation is currently blocked (empty if ready)",
    )


class ActivationResponse(BaseModel):
    """Response body for POST /api/v1/companies/{id}/activate."""
    company_id: uuid.UUID
    activated: bool
    message: str
