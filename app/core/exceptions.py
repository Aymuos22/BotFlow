"""
Domain exception hierarchy for the MindoraxAI backend.

All custom exceptions extend ``AppException`` so the global FastAPI
exception handler can produce consistent structured JSON responses.
"""
from typing import Optional


class AppException(Exception):
    """
    Base exception for all application-level errors.

    Attributes:
        message:     Human-readable error description.
        status_code: HTTP status code to return to the client.
        code:        Machine-readable error code for client handling.
        detail:      Optional additional context (not shown in prod).
    """

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        code: str = "APP_ERROR",
        detail: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.detail = detail


# ------------------------------------------------------------------ #
# 4xx Client Errors
# ------------------------------------------------------------------ #


class NotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} '{identifier}' not found.",
            status_code=404,
            code="NOT_FOUND",
        )


class ConflictError(AppException):
    """Raised when a resource already exists or state conflict is detected."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=409, code="CONFLICT")


class ValidationError(AppException):
    """Raised when domain-level validation fails (business rules)."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=422, code="VALIDATION_ERROR")


class ForbiddenError(AppException):
    """Raised when the requested operation is not permitted."""

    def __init__(self, message: str = "Operation not permitted.") -> None:
        super().__init__(message=message, status_code=403, code="FORBIDDEN")


class PreconditionFailedError(AppException):
    """Raised when required pre-conditions for an action are not met."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message, status_code=412, code="PRECONDITION_FAILED"
        )


# ------------------------------------------------------------------ #
# 5xx Server / Integration Errors
# ------------------------------------------------------------------ #


class ExternalServiceError(AppException):
    """Raised when a downstream service (e.g. Twilio, Weaviate) fails."""

    def __init__(self, service: str, message: str) -> None:
        super().__init__(
            message=f"[{service}] {message}",
            status_code=502,
            code="EXTERNAL_SERVICE_ERROR",
        )


class DatabaseError(AppException):
    """Raised for unexpected database-level errors."""

    def __init__(self, message: str = "A database error occurred.") -> None:
        super().__init__(message=message, status_code=500, code="DATABASE_ERROR")
