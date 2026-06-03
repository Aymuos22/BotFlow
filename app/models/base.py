"""
SQLAlchemy declarative base and shared model mixins.

All ORM models inherit from ``Base``.  Common timestamp fields are
provided by ``TimestampMixin``.

Note: We use ``sqlalchemy.Uuid`` (SQLAlchemy 2.0+) for UUID columns.
This maps to the native ``UUID`` type on PostgreSQL and a ``CHAR(32)``
on SQLite, giving cross-database compatibility for tests.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base – imported by all model files."""
    pass


class TimestampMixin:
    """
    Adds ``created_at`` and ``updated_at`` columns to any model.

    ``created_at`` uses a server-side SQL default (``now()``).
    ``updated_at`` is updated at the Python/ORM level on every write
    so it works identically on both PostgreSQL and SQLite.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        sort_order=998,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        sort_order=999,
    )


def new_uuid() -> uuid.UUID:
    """Generate a new UUID4.  Used as column ``default``."""
    return uuid.uuid4()
