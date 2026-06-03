"""
Repository for the Product domain model.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """Async repository for Product records."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Product, db)

    async def list_by_company(
        self,
        company_id: UUID,
        *,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Product]:
        q = select(Product).where(Product.company_id == company_id)
        if is_active is not None:
            q = q.where(Product.is_active == is_active)
        if category:
            q = q.where(Product.category == category)
        if search:
            pattern = f"%{search}%"
            q = q.where(
                Product.name.ilike(pattern) | Product.sku.ilike(pattern)
            )
        q = q.order_by(Product.name).limit(limit).offset(offset)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def count_by_company(self, company_id: UUID) -> int:
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.count()).select_from(Product).where(
                Product.company_id == company_id
            )
        )
        return result.scalar_one()

    async def get_by_sku(self, company_id: UUID, sku: str) -> Optional[Product]:
        result = await self.db.execute(
            select(Product).where(
                Product.company_id == company_id, Product.sku == sku
            )
        )
        return result.scalar_one_or_none()

    async def get_for_company(
        self, product_id: UUID, company_id: UUID
    ) -> Optional[Product]:
        """Get a product only if it belongs to the given company."""
        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id, Product.company_id == company_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_ids_for_company(
        self, company_id: UUID, product_ids: List[UUID]
    ) -> List[Product]:
        if not product_ids:
            return []
        result = await self.db.execute(
            select(Product).where(
                Product.company_id == company_id,
                Product.id.in_(product_ids),
                Product.is_active == True,  # noqa: E712
            )
        )
        by_id = {p.id: p for p in result.scalars().all()}
        return [by_id[pid] for pid in product_ids if pid in by_id]

    async def list_unindexed(self, company_id: UUID) -> List[Product]:
        result = await self.db.execute(
            select(Product).where(
                Product.company_id == company_id,
                Product.weaviate_indexed == False,  # noqa: E712
                Product.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())
