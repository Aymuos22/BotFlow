"""
Product management endpoints.

All routes are accessible to:
  - Admins (X-Admin-Key or Bearer with role=admin)
  - Company portal users (Bearer with role=user and matching company_id)

Routes
------
POST   /api/v1/companies/{company_id}/products
GET    /api/v1/companies/{company_id}/products
GET    /api/v1/companies/{company_id}/products/{product_id}
PUT    /api/v1/companies/{company_id}/products/{product_id}
DELETE /api/v1/companies/{company_id}/products/{product_id}
POST   /api/v1/companies/{company_id}/products/{product_id}/reindex
POST   /api/v1/companies/{company_id}/products/reindex-all
GET    /api/v1/companies/{company_id}/analytics/products
"""
import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.portal_auth import require_portal_company_access
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.response import APIResponse
from app.integrations.weaviate.client import WeaviateClient, get_weaviate_client
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.product_event_repository import ProductEventRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.product import (
    BulkReindexResponse,
    ProductAnalyticsResponse,
    ProductCreate,
    ProductListResponse,
    ProductRead,
    ProductUpdate,
    ReindexResult,
)
from app.services.product_service import ProductService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Products"])


# ------------------------------------------------------------------ #
# Dependency
# ------------------------------------------------------------------ #

def _get_product_service(
    db: AsyncSession = Depends(get_db),
    weaviate: WeaviateClient = Depends(get_weaviate_client),
) -> ProductService:
    return ProductService(
        product_repo=ProductRepository(db),
        event_repo=ProductEventRepository(db),
        config_repo=CompanyConfigRepository(db),
        weaviate_client=weaviate,
    )


async def _validate_company(
    company_id: UUID, db: AsyncSession = Depends(get_db)
) -> None:
    company = await CompanyRepository(db).get(company_id)
    if not company:
        raise NotFoundError("Company", str(company_id))


# ------------------------------------------------------------------ #
# CRUD
# ------------------------------------------------------------------ #

@router.post(
    "/companies/{company_id}/products",
    response_model=APIResponse[ProductRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
)
async def create_product(
    company_id: UUID,
    payload: ProductCreate,
    _auth: UUID = Depends(require_portal_company_access),
    svc: ProductService = Depends(_get_product_service),
) -> Any:
    """
    Create a new product for the company.

    The product is NOT automatically indexed into Weaviate — call
    ``POST …/products/{id}/reindex`` or ``POST …/products/reindex-all``
    to make it searchable via RAG.
    """
    product = await svc.create_product(company_id, payload)
    indexed = ProductRead.model_validate(product).weaviate_indexed
    return APIResponse(
        success=True,
        data=ProductRead.model_validate(product),
        message="Product created and indexed." if indexed else "Product created. Weaviate unreachable — call /reindex when available.",
    )


@router.get(
    "/companies/{company_id}/products",
    response_model=APIResponse[ProductListResponse],
    summary="List products for a company",
)
async def list_products(
    company_id: UUID,
    is_active: Optional[bool] = Query(default=None),
    category: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, description="Search by name or SKU"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _auth: UUID = Depends(require_portal_company_access),
    svc: ProductService = Depends(_get_product_service),
) -> Any:
    result = await svc.list_products(
        company_id,
        is_active=is_active,
        category=category,
        search=q,
        limit=limit,
        offset=offset,
    )
    return APIResponse(success=True, data=ProductListResponse(**result))


@router.get(
    "/companies/{company_id}/products/{product_id}",
    response_model=APIResponse[ProductRead],
    summary="Get a single product",
)
async def get_product(
    company_id: UUID,
    product_id: UUID,
    _auth: UUID = Depends(require_portal_company_access),
    svc: ProductService = Depends(_get_product_service),
) -> Any:
    product = await svc.get_product(product_id, company_id)
    return APIResponse(success=True, data=ProductRead.model_validate(product))


@router.put(
    "/companies/{company_id}/products/{product_id}",
    response_model=APIResponse[ProductRead],
    summary="Update a product",
)
async def update_product(
    company_id: UUID,
    product_id: UUID,
    payload: ProductUpdate,
    _auth: UUID = Depends(require_portal_company_access),
    svc: ProductService = Depends(_get_product_service),
) -> Any:
    """
    Update product fields.  If any indexable field (name, description,
    price, attributes) changes, ``weaviate_indexed`` is set to ``false``
    and you should call ``/reindex`` to sync.
    """
    product = await svc.update_product(product_id, company_id, payload)
    return APIResponse(
        success=True,
        data=ProductRead.model_validate(product),
        message="Product updated.",
    )


@router.delete(
    "/companies/{company_id}/products/{product_id}",
    response_model=APIResponse[dict],
    summary="Delete a product",
)
async def delete_product(
    company_id: UUID,
    product_id: UUID,
    _auth: UUID = Depends(require_portal_company_access),
    svc: ProductService = Depends(_get_product_service),
) -> Any:
    """Delete product and remove its Weaviate chunks."""
    await svc.delete_product(product_id, company_id)
    return APIResponse(
        success=True,
        data={"deleted": True},
        message="Product deleted.",
    )


# ------------------------------------------------------------------ #
# Indexing
# ------------------------------------------------------------------ #

@router.post(
    "/companies/{company_id}/products/{product_id}/reindex",
    response_model=APIResponse[ReindexResult],
    summary="Index / re-index a single product into Weaviate",
)
async def reindex_product(
    company_id: UUID,
    product_id: UUID,
    _auth: UUID = Depends(require_portal_company_access),
    svc: ProductService = Depends(_get_product_service),
) -> Any:
    """
    Generate the product's text chunk and upsert it into Weaviate.
    Safe to call multiple times (idempotent upsert).
    """
    product = await svc.get_product(product_id, company_id)
    result = await svc.index_product(product)
    return APIResponse(
        success=result.success,
        data=result,
        message=result.message,
    )


@router.post(
    "/companies/{company_id}/products/reindex-all",
    response_model=APIResponse[BulkReindexResponse],
    summary="Re-index all active products for a company",
)
async def reindex_all_products(
    company_id: UUID,
    _auth: UUID = Depends(require_portal_company_access),
    svc: ProductService = Depends(_get_product_service),
) -> Any:
    """
    Reindex every active product for the company.  Runs synchronously
    (may take a few seconds for large catalogs); call from a background
    job for very large catalogs.
    """
    result = await svc.reindex_all(company_id)
    return APIResponse(success=True, data=result, message=result.message)


# ------------------------------------------------------------------ #
# Analytics
# ------------------------------------------------------------------ #

@router.get(
    "/companies/{company_id}/analytics/products",
    response_model=APIResponse[ProductAnalyticsResponse],
    summary="Product analytics (retrieved / suggested counts)",
)
async def product_analytics(
    company_id: UUID,
    period_days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    _auth: UUID = Depends(require_portal_company_access),
    svc: ProductService = Depends(_get_product_service),
) -> Any:
    """
    Return how many times each product was retrieved (appeared in RAG
    search results) and suggested (LLM gave a real, non-fallback answer
    that included the product's chunks) in the given period.
    """
    data = await svc.get_analytics(company_id, period_days=period_days, limit=limit)
    return APIResponse(success=True, data=data)
