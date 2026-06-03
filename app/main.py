"""
FastAPI application factory.

``create_app()`` builds and returns the FastAPI instance.
A module-level ``app`` is also exported so uvicorn can run it directly:

    uvicorn app.main:app --reload

Architecture notes:
  - All exception handlers return consistent ErrorResponse JSON.
  - Versioned API routing under /api/v1.
  - Root /health is registered on the app directly so it works
    without any /api/v1 prefix (useful for load balancer probes).
  - Correlation ID middleware: every request gets an X-Correlation-ID
    header (generated if absent) that flows through all log lines.
"""
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import mimetypes
# Ensure image MIME types are registered on Linux where they may be absent
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/jpeg", ".jpg")
mimetypes.add_type("image/jpeg", ".jpeg")
mimetypes.add_type("image/png", ".png")

from app.api.v1.router import router as api_v1_router
from app.api.v1.endpoints.health import router as health_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging_config import setup_logging
from app.core.response import ErrorResponse
from app.utils.correlation_id import (
    HEADER_NAME,
    get_correlation_id,
    set_correlation_id,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    yield
    try:
        from app.integrations.embeddings.client import close_embedding_client
        from app.integrations.weaviate.client import close_weaviate_client

        await close_weaviate_client()
        await close_embedding_client()
    except Exception:
        logger.warning("Infrastructure client shutdown failed", exc_info=True)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Called once at import time (module-level ``app = create_app()``)
    and also in tests to get a fresh instance with dependency overrides.
    """
    setup_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Multi-tenant WhatsApp RAG SaaS backend. "
            "Phases 1-3: Company onboarding, document management, "
            "RAG-powered WhatsApp bot, human handoff, and analytics."
        ),
        version=settings.app_version,
        lifespan=_app_lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        contact={
            "name": "MindoraxAI",
            "url": "https://mindorax.ai",
        },
    )

    # ------------------------------------------------------------------ #
    # Correlation ID middleware (Phase 3)
    # ------------------------------------------------------------------ #
    # Register this *before* CORSMiddleware. FastAPI uses insert(0) per
    # add_middleware, so the *last* add_middleware wraps the stack outermost.
    # CORS must be outermost so OPTIONS preflight is answered with ACAO headers
    # before BaseHTTPMiddleware (correlation) runs — otherwise browsers see
    # “No Access-Control-Allow-Origin” on preflight.

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        """
        Attach a unique correlation ID to every request.

        Reads ``X-Correlation-ID`` from the request header; generates a
        UUID4 if absent.  Stores it in a ``contextvars.ContextVar`` so
        it is accessible in service/logging code without explicit passing.
        Always echoes it back in the response header.
        """
        cid = request.headers.get(HEADER_NAME) or str(uuid.uuid4())
        set_correlation_id(cid)
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers[HEADER_NAME] = cid
        return response

    # ------------------------------------------------------------------ #
    # CORS — add *after* correlation so CORSMiddleware is the outer layer
    # ------------------------------------------------------------------ #
    _cors_raw = (settings.cors_origins or "").strip()
    if settings.cors_allow_all or _cors_raw == "*":
        _cors_origins: list[str] = ["*"]
        _cors_credentials = False
    else:
        _cors_origins = list(settings.cors_origins_list)
        _cors_credentials = bool(_cors_origins)

    # Starlette treats allow_origins=() as "deny every Origin": preflight returns
    # 400 without Access-Control-Allow-Origin — browsers report exactly that.
    if not _cors_origins:
        logger.warning(
            "CORS allow_origins is empty; allowing all origins (*). "
            "Set CORS_ALLOW_ALL=true or CORS_ORIGINS explicitly."
        )
        _cors_origins = ["*"]
        _cors_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=_cors_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(
        "CORS enabled",
        extra={
            "allow_origins": _cors_origins,
            "allow_credentials": _cors_credentials,
        },
    )

    # ------------------------------------------------------------------ #
    # Exception handlers
    # ------------------------------------------------------------------ #

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        """Map domain exceptions → structured JSON error responses."""
        cid = getattr(request.state, "correlation_id", get_correlation_id())
        logger.warning(
            "AppException",
            extra={
                "exc_code": exc.code,
                "exc_message": exc.message,
                "path": str(request.url),
                "correlation_id": cid,
            },
        )
        resp = JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                success=False,
                error=exc.message,
                code=exc.code,
                detail=exc.detail if settings.debug else None,
            ).model_dump(),
        )
        resp.headers[HEADER_NAME] = cid
        return resp

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Map Pydantic validation errors → 422 JSON responses."""
        # Build a readable summary of all validation issues
        messages = []
        for err in exc.errors():
            field = " → ".join(str(loc) for loc in err["loc"] if loc != "body")
            messages.append(f"{field}: {err['msg']}" if field else err["msg"])
        error_detail = "; ".join(messages)

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                success=False,
                error=error_detail,
                code="VALIDATION_ERROR",
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all for unexpected exceptions – return 500."""
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error="An unexpected error occurred.",
                code="INTERNAL_ERROR",
                detail=(
                    str(exc)
                    if settings.debug or settings.expose_internal_error_detail
                    else None
                ),
            ).model_dump(),
        )

    # ------------------------------------------------------------------ #
    # Routers
    # ------------------------------------------------------------------ #

    # Root-level health (no /api/v1 prefix)
    app.include_router(health_router)

    # All versioned API routes
    app.include_router(api_v1_router)

    # ------------------------------------------------------------------ #
    # Static files — product images served at /static/
    # Structure: /static/product-images/<company_id>/<filename>
    # Set PUBLIC_BASE_URL in .env so image URLs are publicly reachable.
    # ------------------------------------------------------------------ #
    _static_dir = Path(__file__).resolve().parent / "static"
    _static_dir.mkdir(exist_ok=True)
    (_static_dir / "product-images").mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
    logger.info("Static files mounted", extra={"path": str(_static_dir)})

    logger.info(
        "FastAPI app created",
        extra={"env": settings.app_env, "version": settings.app_version},
    )
    return app


# Module-level app instance used by uvicorn and tests
app = create_app()
