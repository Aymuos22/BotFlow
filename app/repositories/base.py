"""
Generic async repository base class.

Provides standard CRUD operations typed against a SQLAlchemy model.
Domain repositories extend this class and add query-specific methods.
"""
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic base repository with typed async CRUD helpers.

    Args:
        model: The SQLAlchemy model class this repository manages.
        db:    The async database session for this request.
    """

    def __init__(self, model: Type[ModelType], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    async def get(self, id: UUID) -> Optional[ModelType]:
        """Fetch a single record by primary key UUID."""
        return await self.db.get(self.model, id)

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """Fetch all records with optional pagination."""
        result = await self.db.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, data: Dict[str, Any]) -> ModelType:
        """
        Create a new record from a plain dict of column values.

        Flushes the session (makes the row visible in the current
        transaction) and refreshes the object to populate server
        defaults such as ``created_at``.
        """
        obj = self.model(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: ModelType, data: Dict[str, Any]) -> ModelType:
        """
        Update an existing record with the supplied field mapping.

        Only keys present in ``data`` are changed; others are untouched.
        """
        for field, value in data.items():
            setattr(obj, field, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        """Delete a record and flush the change."""
        await self.db.delete(obj)
        await self.db.flush()

    async def count(self) -> int:
        """Return the total number of rows for this model."""
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()
