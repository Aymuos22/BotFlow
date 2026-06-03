"""
ProductService – manages product CRUD and Weaviate indexing.

Responsibilities:
  - Create / update / delete products in the database.
  - Build a text chunk from product fields and upsert it into Weaviate
    so the RAG pipeline can retrieve it.
  - Mark ``weaviate_indexed`` on the product row to track sync state.
  - Delete product chunks from Weaviate on product deletion.
  - Provide analytics aggregation via the event repository.
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError
from app.integrations.weaviate.client import WeaviateClient
from app.models.product import Product
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.product_event_repository import ProductEventRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.product import (
    BulkReindexResponse,
    ProductAnalyticsItem,
    ProductAnalyticsPoint,
    ProductAnalyticsResponse,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ReindexResult,
)

logger = logging.getLogger(__name__)


def build_chunk_text(product: Product) -> str:
    """
    Generate the embeddable text chunk for a product.

    This is the text that gets sent to the embedding model and stored
    in Weaviate for BM25 / hybrid search.  Structured fields are laid
    out in a human-readable way so both keyword and semantic search work.
    """
    parts: List[str] = [f"Product: {product.name}"]
    if product.sku:
        parts.append(f"SKU: {product.sku}")
    if product.category:
        parts.append(f"Category: {product.category}")
    if product.description:
        parts.append(f"Description: {product.description}")
    if product.synonyms:
        parts.append(f"Synonyms: {', '.join(product.synonyms)}")
    if product.price_json:
        pj = product.price_json
        currency = pj.get("currency", "INR")
        mrp = pj.get("mrp")
        cod = pj.get("cod_price")
        prepaid = pj.get("prepaid_price")
        prepaid_offer = pj.get("prepaid_offer", "")
        if mrp is not None or cod is not None or prepaid is not None:
            price_parts: List[str] = []
            if mrp is not None:
                price_parts.append(f"MRP {currency} {mrp}")
            if cod is not None:
                price_parts.append(f"COD {currency} {cod}")
            if prepaid is not None:
                label = f"Prepaid {currency} {prepaid}"
                if prepaid_offer:
                    label += f" ({prepaid_offer})"
                price_parts.append(label)
            parts.append(f"Pricing: {' | '.join(price_parts)}")
        else:
            amount = (
                pj.get("selling_price")
                or pj.get("sale_price")
                or pj.get("amount")
                or pj.get("price")
            )
            unit = pj.get("unit", "")
            if amount is not None:
                price_str = f"{currency} {amount}".strip()
                if unit:
                    price_str += f" {unit}"
                parts.append(f"Price: {price_str}")
    if product.attributes_json:
        attr_lines = ", ".join(
            f"{k}={v}" for k, v in product.attributes_json.items()
        )
        parts.append(f"Attributes: {attr_lines}")
    return "\n".join(parts)


class ProductService:
    def __init__(
        self,
        product_repo: ProductRepository,
        event_repo: ProductEventRepository,
        config_repo: CompanyConfigRepository,
        weaviate_client: WeaviateClient,
    ) -> None:
        self._products = product_repo
        self._events = event_repo
        self._configs = config_repo
        self._weaviate = weaviate_client

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    async def create_product(
        self, company_id: UUID, payload: ProductCreate
    ) -> Product:
        if payload.sku:
            existing = await self._products.get_by_sku(company_id, payload.sku)
            if existing:
                raise ConflictError(
                    f"A product with SKU '{payload.sku}' already exists."
                )
        product = await self._products.create(
            {
                "company_id": company_id,
                "name": payload.name,
                "sku": payload.sku,
                "category": payload.category,
                "description": payload.description,
                "price_json": payload.price_json,
                "attributes_json": payload.attributes_json,
                "synonyms_json": payload.synonyms,
                "is_active": payload.is_active,
                "weaviate_indexed": False,
            }
        )
        await self._products.db.commit()
        logger.info(
            "Product created",
            extra={"company_id": str(company_id), "product_id": str(product.id)},
        )
        # Auto-index into Weaviate so RAG can search it immediately.
        # Non-fatal: DB row is already committed even if Weaviate is unreachable.
        if payload.is_active:
            result = await self.index_product(product)
            if not result.success:
                logger.warning(
                    "Auto-index failed for new product (not fatal, call /reindex later)",
                    extra={"product_id": str(product.id), "error": result.message},
                )
        return product

    async def update_product(
        self, product_id: UUID, company_id: UUID, payload: ProductUpdate
    ) -> Product:
        product = await self._products.get_for_company(product_id, company_id)
        if not product:
            raise NotFoundError("Product", str(product_id))

        update_data = payload.model_dump(exclude_none=True)
        if "synonyms" in update_data:
            update_data["synonyms_json"] = update_data.pop("synonyms")
        if not update_data:
            return product

        if "sku" in update_data and update_data["sku"] != product.sku:
            existing = await self._products.get_by_sku(
                company_id, update_data["sku"]
            )
            if existing and existing.id != product_id:
                raise ConflictError(
                    f"A product with SKU '{update_data['sku']}' already exists."
                )

        # Track whether indexable content is changing
        indexable = {"name", "sku", "category", "description", "price_json", "attributes_json", "synonyms_json"}
        needs_reindex = bool(update_data.keys() & indexable)
        if needs_reindex:
            update_data["weaviate_indexed"] = False

        product = await self._products.update(product, update_data)
        await self._products.db.commit()

        # Auto-reindex if content changed and product is active
        if needs_reindex and product.is_active:
            result = await self.index_product(product)
            if not result.success:
                logger.warning(
                    "Auto-reindex failed after product update (not fatal)",
                    extra={"product_id": str(product.id), "error": result.message},
                )
        return product

    async def delete_product(self, product_id: UUID, company_id: UUID) -> None:
        product = await self._products.get_for_company(product_id, company_id)
        if not product:
            raise NotFoundError("Product", str(product_id))

        config = await self._configs.get_by_company(company_id)
        if config:
            try:
                await self._weaviate.delete_document_chunks(
                    config.weaviate_collection, str(product_id)
                )
            except Exception as exc:
                logger.warning(
                    "Could not remove product chunks from Weaviate (non-fatal)",
                    extra={"product_id": str(product_id), "error": str(exc)},
                )

        await self._products.delete(product)
        await self._products.db.commit()
        logger.info(
            "Product deleted",
            extra={"company_id": str(company_id), "product_id": str(product_id)},
        )

    async def get_product(self, product_id: UUID, company_id: UUID) -> Product:
        product = await self._products.get_for_company(product_id, company_id)
        if not product:
            raise NotFoundError("Product", str(product_id))
        return product

    async def list_products(
        self,
        company_id: UUID,
        *,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict[str, Any]:
        items = await self._products.list_by_company(
            company_id,
            is_active=is_active,
            category=category,
            search=search,
            limit=limit,
            offset=offset,
        )
        total = await self._products.count_by_company(company_id)
        return {
            "products": [ProductRead.model_validate(p) for p in items],
            "total": total,
        }

    # ------------------------------------------------------------------ #
    # Indexing
    # ------------------------------------------------------------------ #

    async def index_product(self, product: Product) -> ReindexResult:
        """Push a single product's chunk into Weaviate."""
        config = await self._configs.get_by_company(product.company_id)
        if not config:
            return ReindexResult(
                product_id=str(product.id),
                name=product.name,
                success=False,
                message="Company config not found.",
            )

        chunk_text = build_chunk_text(product)
        try:
            count = await self._weaviate.upsert_document_chunks(
                collection_name=config.weaviate_collection,
                document_id=str(product.id),
                company_id=str(product.company_id),
                file_name=product.name,
                s3_key="",
                chunks=[chunk_text],
                # product_id is injected via a separate upsert path
            )
            # Also set product_id on the chunk object
            await self._upsert_product_chunk(
                config.weaviate_collection, product, chunk_text
            )
            await self._products.update(product, {"weaviate_indexed": True})
            await self._products.db.commit()
            logger.info(
                "Product indexed",
                extra={
                    "product_id": str(product.id),
                    "chunks": count,
                },
            )
            return ReindexResult(
                product_id=str(product.id),
                name=product.name,
                success=True,
                message="Indexed successfully.",
            )
        except Exception as exc:
            logger.error(
                "Product indexing failed",
                extra={"product_id": str(product.id), "error": str(exc)},
            )
            return ReindexResult(
                product_id=str(product.id),
                name=product.name,
                success=False,
                message=str(exc),
            )

    async def _upsert_product_chunk(
        self,
        collection_name: str,
        product: Product,
        chunk_text: str,
    ) -> None:
        """
        Upsert a single object with ``product_id`` populated.
        Uses the same deterministic UUID strategy as document chunks.
        """
        import uuid as uuid_lib
        obj_id = str(
            uuid_lib.uuid5(
                uuid_lib.NAMESPACE_URL,
                f"{product.id}-chunk-0",
            )
        )
        obj = {
            "class": collection_name,
            "id": obj_id,
            "properties": {
                "document_id": str(product.id),
                "company_id": str(product.company_id),
                "chunk_index": 0,
                "chunk_text": chunk_text,
                "file_name": product.name,
                "s3_key": "",
                "product_id": str(product.id),
            },
        }
        http = await self._weaviate._http_client()
        response = await http.post(
            f"{self._weaviate.url}/v1/batch/objects",
            json={"objects": [obj]},
            headers=self._weaviate._headers(),
        )
        self._weaviate._raise_for_status(response, "upsert_product_chunk")

    async def reindex_all(self, company_id: UUID) -> BulkReindexResponse:
        """Reindex all active products for a company (runs synchronously)."""
        products = await self._products.list_by_company(
            company_id, is_active=True, limit=5000
        )
        queued = 0
        for product in products:
            result = await self.index_product(product)
            if result.success:
                queued += 1
        return BulkReindexResponse(
            queued=queued,
            message=f"Reindexed {queued}/{len(products)} products.",
        )

    # ------------------------------------------------------------------ #
    # Analytics
    # ------------------------------------------------------------------ #

    async def get_analytics(
        self, company_id: UUID, period_days: int = 30, limit: int = 20
    ) -> ProductAnalyticsResponse:
        rows = await self._events.get_product_analytics(
            company_id, period_days=period_days, limit=limit
        )
        series_rows = await self._events.get_product_event_series(
            company_id, period_days=period_days
        )
        items = [ProductAnalyticsItem(**r) for r in rows]
        series = [ProductAnalyticsPoint(**r) for r in series_rows]
        top_retrieved = sorted(items, key=lambda x: x.retrieved_count, reverse=True)[
            :limit
        ]
        top_suggested = sorted(items, key=lambda x: x.suggested_count, reverse=True)[
            :limit
        ]
        total = sum(
            i.retrieved_count + i.suggested_count for i in items
        )
        return ProductAnalyticsResponse(
            period_days=period_days,
            total_events=total,
            items=items,
            top_retrieved=top_retrieved,
            top_suggested=top_suggested,
            series=series,
        )
