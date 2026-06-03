"""
Company ORM model.

A ``Company`` is the top-level multi-tenant entity.  Every other
resource (config, channels, sessions) belongs to a company.

Status lifecycle:
    draft → active → inactive / suspended
"""
import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.company_config import CompanyConfig
    from app.models.company_channel import CompanyChannel
    from app.models.onboarding_status import OnboardingStatus


class Company(Base, TimestampMixin):
    """
    Represents a tenant (customer company) of the SaaS platform.

    Columns
    -------
    id           : UUID primary key
    name         : Unique machine-readable slug (e.g. ``acme-corp``)
    display_name : Human-readable label shown in UIs
    status       : Lifecycle state – draft | active | inactive | suspended
    """

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique machine-readable company identifier",
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable company name shown in UIs",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
        comment="draft | active | inactive | suspended",
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    config: Mapped["CompanyConfig"] = relationship(
        "CompanyConfig",
        back_populates="company",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="noload",
    )
    channels: Mapped[List["CompanyChannel"]] = relationship(
        "CompanyChannel",
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    onboarding_status: Mapped["OnboardingStatus"] = relationship(
        "OnboardingStatus",
        back_populates="company",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r} status={self.status!r}>"
