"""
Pydantic schemas for the Product domain.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


def normalize_synonyms(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        raw_items = v.replace("\n", ",").split(",")
    elif isinstance(v, list):
        raw_items = v
    else:
        raise ValueError("synonyms must be a list of strings")
    out: List[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if item is None:
            continue
        text = " ".join(str(item).strip().split())
        if not text:
            continue
        if len(text) > 120:
            raise ValueError("each synonym must be 120 characters or fewer")
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=500, description="Product name")
    sku: Optional[str] = Field(
        default=None, max_length=200, description="Stock-keeping unit (unique per company)"
    )
    category: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(
        default=None,
        description="Full product description – this text is embedded for RAG search",
    )
    price_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description='e.g. {"amount": 999, "currency": "INR", "unit": "per month"}',
    )
    attributes_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arbitrary key-value attributes (color, size, warranty…)",
    )
    synonyms: List[str] = Field(
        default_factory=list,
        description="Alternate names and search phrases for this product",
    )
    is_active: bool = Field(default=True)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("synonyms", mode="before")
    @classmethod
    def normalize_synonyms_field(cls, v: Any) -> List[str]:
        return normalize_synonyms(v)


class ProductCreate(ProductBase):
    """Body for POST /companies/{id}/products."""
    pass


class ProductUpdate(BaseModel):
    """Body for PUT /companies/{id}/products/{pid} – all fields optional."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    sku: Optional[str] = Field(default=None, max_length=200)
    category: Optional[str] = None
    description: Optional[str] = None
    price_json: Optional[Dict[str, Any]] = None
    attributes_json: Optional[Dict[str, Any]] = None
    synonyms: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @field_validator("synonyms", mode="before")
    @classmethod
    def normalize_update_synonyms(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        return normalize_synonyms(v)


class ProductRead(ProductBase):
    """Full product representation returned by read endpoints."""
    id: uuid.UUID
    company_id: uuid.UUID
    weaviate_indexed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    products: List[ProductRead]
    total: int


# ── Analytics ────────────────────────────────────────────────────────

class ProductAnalyticsItem(BaseModel):
    product_id: str
    name: str
    sku: Optional[str]
    category: Optional[str]
    retrieved_count: int
    suggested_count: int
    unique_conversations: int
    suggestion_rate_pct: float


class ProductAnalyticsPoint(BaseModel):
    date: str
    retrieved_count: int
    suggested_count: int


class ProductAnalyticsResponse(BaseModel):
    period_days: int
    total_events: int
    items: List[ProductAnalyticsItem]
    top_retrieved: List[ProductAnalyticsItem]
    top_suggested: List[ProductAnalyticsItem]
    series: List[ProductAnalyticsPoint]


# ── Reindex ──────────────────────────────────────────────────────────

class ReindexResult(BaseModel):
    product_id: str
    name: str
    success: bool
    message: str


class BulkReindexResponse(BaseModel):
    queued: int
    message: str
