"""
Pydantic schemas for CompanyChannel.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ChannelStatus, ChannelType


class CompanyChannelCreate(BaseModel):
    """Fields required to register a new channel during onboarding."""
    channel_type: ChannelType = ChannelType.WHATSAPP
    phone_number: str = Field(
        ...,
        description="E.164 phone number, e.g. +911234567890",
        examples=["+911234567890"],
    )
    is_primary: bool = Field(default=True)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        import re
        # Allow + prefix then 7–15 digits (E.164 standard)
        if not re.match(r'^\+?[1-9]\d{6,14}$', v.strip()):
            raise ValueError(
                "phone_number must be a valid phone number (E.164 format recommended)"
            )
        return v.strip()

    model_config = {"use_enum_values": True}


class CompanyChannelRead(BaseModel):
    """Full channel representation returned by read endpoints."""
    id: uuid.UUID
    company_id: uuid.UUID
    channel_type: str
    phone_number: str
    session_name: str
    is_primary: bool
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
