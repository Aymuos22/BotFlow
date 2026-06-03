"""
Pydantic schemas for Conversation and Message domains.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ConversationRead(BaseModel):
    """Full conversation representation."""
    id: uuid.UUID
    company_id: uuid.UUID
    customer_phone: str
    current_mode: str
    status: str
    detected_language: Optional[str]
    assigned_agent_id: Optional[str]
    last_message_at: Optional[datetime]
    lead_warmth: Optional[str] = None
    lead_warmth_locked: bool = False
    lead_summary: Optional[str] = None
    lead_summary_updated_at: Optional[datetime] = None
    inquiry_complete: bool = False
    inquiry_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InboxConversationItem(ConversationRead):
    """Inbox list row with a short preview of the last message in the thread."""
    last_message_preview: Optional[str] = None


class SheetPreviewRow(BaseModel):
    """Exact row preview for the Google Sheets Leads tab."""

    conversation_id: uuid.UUID
    customer_phone: str
    conversations_last_10_user_messages: str
    summary: str
    lead_type: str
    last_message_at: Optional[datetime] = None
    inquiry_complete: bool = False


class PortalInboxPatchRequest(BaseModel):
    """Update lead labels from the company dashboard."""

    lead_warmth: Optional[str] = Field(
        default=None, description="hot | warm | cold — omit or null to clear"
    )
    inquiry_complete: Optional[bool] = None


class PortalInboxSendRequest(BaseModel):
    """Send WhatsApp as agent from the dashboard inbox."""

    message_text: str = Field(..., min_length=1, max_length=4096)


class MessageRead(BaseModel):
    """Full message representation."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    company_id: uuid.UUID
    sender_type: str
    message_text: str
    normalized_text: Optional[str]
    language: Optional[str]
    response_type: Optional[str]
    external_message_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
