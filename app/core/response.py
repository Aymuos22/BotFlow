"""
Standardised API response models.

All endpoints return one of these shapes so clients have a consistent
contract regardless of route or domain.

Shapes
------
APIResponse[T]   – success wrapper with typed ``data`` payload
ErrorResponse    – failure wrapper with ``error`` + ``code``
PaginatedResponse[T] – paginated list wrapper
"""
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """
    Unified success response envelope.

    Example::

        {
            "success": true,
            "message": "Company created.",
            "data": { ... }
        }
    """

    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None

    model_config = {"arbitrary_types_allowed": True}


class ErrorResponse(BaseModel):
    """
    Unified error response envelope.

    Example::

        {
            "success": false,
            "error": "Company 'xyz' not found.",
            "code": "NOT_FOUND"
        }
    """

    success: bool = False
    error: str
    code: str = "ERROR"
    detail: Optional[str] = None


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Paginated list response envelope.

    Example::

        {
            "success": true,
            "data": [...],
            "pagination": { "total": 50, "page": 1, ... }
        }
    """

    success: bool = True
    data: List[T]
    pagination: PaginationMeta

    model_config = {"arbitrary_types_allowed": True}


def ok(data: T, message: Optional[str] = None) -> APIResponse[T]:
    """Shorthand helper to build a success response."""
    return APIResponse(success=True, data=data, message=message)


def created(data: T, message: Optional[str] = None) -> APIResponse[T]:
    """Shorthand helper for a 201-style success response."""
    return APIResponse(success=True, data=data, message=message or "Created successfully.")


def error(message: str, code: str = "ERROR", detail: Optional[str] = None) -> ErrorResponse:
    """Shorthand helper to build an error response."""
    return ErrorResponse(success=False, error=message, code=code, detail=detail)
