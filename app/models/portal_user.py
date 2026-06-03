"""
Portal users — DB-backed accounts for first-party API clients.

``role`` is ``admin`` (full portal) or ``user`` (single ``company_id``).
Passwords are stored as bcrypt hashes.
"""
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.company import Company


class PortalUser(Base, TimestampMixin):
    __tablename__ = "portal_users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="admin | user"
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    company: Mapped[Optional["Company"]] = relationship(
        "Company", foreign_keys=[company_id], lazy="noload"
    )
