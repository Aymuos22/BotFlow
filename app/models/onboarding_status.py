"""
OnboardingStatus ORM model.

Tracks the multi-step onboarding progress for each company.
This record is created during full onboarding and updated as each
integration step completes or fails.

Activation gate (all must be True):
  1. config_saved        – CompanyConfig row exists
  2. weaviate_ready      – Weaviate collection created
  3. Twilio credentials  – checked in OnboardingService against CompanyConfig
     (twilio_whatsapp_number, twilio_account_sid, twilio_auth_token)

``is_ready_to_activate`` is computed in the service layer (not on this model)
because it depends on CompanyConfig.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid

if TYPE_CHECKING:
    from app.models.company import Company


class OnboardingStatus(Base):
    """
    Tracks per-company onboarding readiness.

    Each boolean flag represents a discrete onboarding step.
    ``activated`` is set to True only when the company is fully activated.
    """

    __tablename__ = "onboarding_status"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Readiness flags
    # ------------------------------------------------------------------ #
    config_saved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    weaviate_ready: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True once the Weaviate collection has been created",
    )
    activated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True once the company has been fully activated",
    )

    # ------------------------------------------------------------------ #
    # Error tracking
    # ------------------------------------------------------------------ #
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Last error message from any onboarding step",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ------------------------------------------------------------------ #
    # Relationship
    # ------------------------------------------------------------------ #
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="onboarding_status",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<OnboardingStatus company_id={self.company_id} "
            f"activated={self.activated}>"
        )
