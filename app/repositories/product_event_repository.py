"""
Repository for the ProductEvent analytics ledger.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_event import ProductEvent
from app.repositories.base import BaseRepository


class ProductEventRepository(BaseRepository[ProductEvent]):
    """Append-only repository for ProductEvent rows."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(ProductEvent, db)

    async def create_event(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        event_type: str,
        channel: str = "whatsapp",
        conversation_id: Optional[UUID] = None,
        query_text: Optional[str] = None,
    ) -> ProductEvent:
        return await self.create(
            {
                "company_id": company_id,
                "product_id": product_id,
                "event_type": event_type,
                "channel": channel,
                "conversation_id": conversation_id,
                "query_text": query_text,
            }
        )

    async def get_product_analytics(
        self,
        company_id: UUID,
        period_days: int = 30,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Return per-product counts for the given time window.

        Returns a list of dicts with keys:
            product_id, name, sku, category,
            retrieved_count, suggested_count,
            unique_conversations, suggestion_rate_pct
        """
        since = datetime.now(timezone.utc) - timedelta(days=period_days)

        stmt = (
            select(
                ProductEvent.product_id,
                Product.name,
                Product.sku,
                Product.category,
                func.count(ProductEvent.id).label("total_count"),
                func.sum(
                    func.cast(ProductEvent.event_type == "retrieved", type_=func.Integer() if False else None)
                ).label("_unused"),
            )
            .join(Product, Product.id == ProductEvent.product_id)
            .where(
                ProductEvent.company_id == company_id,
                ProductEvent.created_at >= since,
            )
            .group_by(ProductEvent.product_id, Product.name, Product.sku, Product.category)
            .limit(limit)
        )

        # Use raw SQL for the conditional aggregation (cleaner across DBs)
        raw = text(
            """
            SELECT
                pe.product_id,
                p.name,
                p.sku,
                p.category,
                COUNT(CASE WHEN pe.event_type = 'retrieved' THEN 1 END) AS retrieved_count,
                COUNT(CASE WHEN pe.event_type = 'suggested' THEN 1 END) AS suggested_count,
                COUNT(DISTINCT pe.conversation_id)                       AS unique_conversations
            FROM product_events pe
            JOIN products p ON p.id = pe.product_id
            WHERE pe.company_id = :company_id
              AND pe.created_at >= :since
            GROUP BY pe.product_id, p.name, p.sku, p.category
            ORDER BY retrieved_count DESC
            LIMIT :limit
            """
        )
        result = await self.db.execute(
            raw,
            {"company_id": str(company_id), "since": since, "limit": limit},
        )
        rows = result.mappings().all()

        out: List[Dict[str, Any]] = []
        for row in rows:
            retrieved = int(row["retrieved_count"] or 0)
            suggested = int(row["suggested_count"] or 0)
            rate = round(suggested * 100.0 / retrieved, 1) if retrieved > 0 else 0.0
            out.append(
                {
                    "product_id": str(row["product_id"]),
                    "name": row["name"],
                    "sku": row["sku"],
                    "category": row["category"],
                    "retrieved_count": retrieved,
                    "suggested_count": suggested,
                    "unique_conversations": int(row["unique_conversations"] or 0),
                    "suggestion_rate_pct": rate,
                }
            )
        return out

    async def get_product_event_series(
        self,
        company_id: UUID,
        period_days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Return daily retrieved/suggested product event totals."""
        since = datetime.now(timezone.utc) - timedelta(days=period_days)
        raw = text(
            """
            SELECT
                DATE(pe.created_at) AS event_date,
                COUNT(CASE WHEN pe.event_type = 'retrieved' THEN 1 END) AS retrieved_count,
                COUNT(CASE WHEN pe.event_type = 'suggested' THEN 1 END) AS suggested_count
            FROM product_events pe
            WHERE pe.company_id = :company_id
              AND pe.created_at >= :since
            GROUP BY DATE(pe.created_at)
            ORDER BY event_date ASC
            """
        )
        result = await self.db.execute(
            raw,
            {"company_id": str(company_id), "since": since},
        )
        return [
            {
                "date": str(row["event_date"]),
                "retrieved_count": int(row["retrieved_count"] or 0),
                "suggested_count": int(row["suggested_count"] or 0),
            }
            for row in result.mappings().all()
        ]
