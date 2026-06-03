"""
Schemas for WhatsApp admin operations (support UI).
"""

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class WhatsAppChangeNumberRequest(BaseModel):
    """Request body to change a company's WhatsApp number."""

    phone_number: str = Field(
        ...,
        description="New E.164 phone number for the company's primary WhatsApp channel",
        examples=["+911234567890"],
    )

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\+?[1-9]\d{6,14}$", v):
            raise ValueError(
                "phone_number must be a valid phone number (E.164 format recommended)"
            )
        return v


class WhatsAppChangeNumberResponse(BaseModel):
    """Response body for a WhatsApp number change operation."""

    company_id: str
    old_phone_number: Optional[str] = None
    new_phone_number: str
    old_channel_key: Optional[str] = None
    new_channel_key: str
    note: str = (
        "Update Twilio WhatsApp sender and webhook configuration if your business number changed."
    )
