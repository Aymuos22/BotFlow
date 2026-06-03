"""
Pydantic schemas for Handoff domain.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HandoffCreate(BaseModel):
    """Request body for triggering a handoff."""
    reason: Optional[str] = Field(None, max_length=500)
    requested_by: str = Field(default="customer", pattern="^(system|customer|agent)$")


class HandoffRead(BaseModel):
    """Full handoff representation."""
    id: uuid.UUID
    company_id: uuid.UUID
    conversation_id: uuid.UUID
    requested_by: str
    reason: Optional[str]
    status: str
    assigned_agent_id: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HandoffAssignRequest(BaseModel):
    """Request body for assigning a handoff to an agent."""
    agent_id: str = Field(..., min_length=1, max_length=200)


class HandoffResolveRequest(BaseModel):
    """Request body for resolving a handoff."""
    resolution_note: Optional[str] = Field(None, max_length=1000)


class AgentMessageRequest(BaseModel):
    """Request body for an agent to send a message."""
    message_text: str = Field(..., min_length=1, max_length=4000)
    agent_id: str = Field(..., min_length=1, max_length=200)
