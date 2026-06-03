"""
Pydantic schemas for the Company domain.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import CompanyStatus


class CompanyBase(BaseModel):
    """Shared fields for Company read/write schemas."""
    name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Unique machine-readable identifier (slug)",
        examples=["acme-corp"],
    )
    display_name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Human-readable company name",
        examples=["Acme Corporation"],
    )

    @field_validator("name")
    @classmethod
    def name_must_be_slug_safe(cls, v: str) -> str:
        """Reject names with characters that could break URL slugs."""
        import re
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9 _\-\.]+$', v.strip()):
            raise ValueError(
                "Company name must start with alphanumeric and contain only "
                "letters, digits, spaces, hyphens, underscores, or dots."
            )
        return v.strip()


class CompanyCreate(CompanyBase):
    """Request body for creating a new company."""
    pass


class CompanyUpdate(BaseModel):
    """Request body for updating mutable company fields."""
    display_name: Optional[str] = Field(None, min_length=2, max_length=200)


class CompanyStatusUpdate(BaseModel):
    """Request body for PATCH /companies/{id}/status."""
    status: CompanyStatus

    model_config = {"use_enum_values": True}


class CompanyRead(CompanyBase):
    """Full company representation returned by read endpoints."""
    id: uuid.UUID
    status: CompanyStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "use_enum_values": True}
