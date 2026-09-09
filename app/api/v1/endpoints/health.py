"""
Health check endpoints.

GET /health              – liveness probe (always fast, no external calls)
GET /health/ready        – readiness probe (pings every external dependency)
GET /api/v1/health       – versioned alias for liveness
GET /api/v1/health/ready – versioned alias for readiness

Liveness  → used by Render / load balancers to know if the process is alive.
Readiness → used to verify all integrations are reachable before serving traffic.
"""
import asyncio
import time
import logging
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings

router = APIRouter(tags=["Health"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Liveness probe  (kept ultra-light — no I/O)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns HTTP 200 while the process is running. No external calls.",
)
async def health_check():
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.app_env,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Individual service checkers
# ─────────────────────────────────────────────────────────────────────────────

async def _check_database() -> Dict[str, Any]:
    """Run SELECT 1 against Supabase Postgres."""
    t0 = time.monotonic()
    try:
        from sqlalchemy import text
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000)}
    except Exception as exc:
        logger.warning("Health: database check failed", exc_info=exc)
        return {
            "status": "error",
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "error": str(exc),
        }


async def _check_weaviate() -> Dict[str, Any]:
    """Ping Weaviate's liveness endpoint."""
    t0 = time.monotonic()
    try:
        import httpx

        url = settings.weaviate_url.rstrip("/") + "/v1/.well-known/ready"
        headers = {}
        if settings.weaviate_api_key:
            headers["Authorization"] = f"Bearer {settings.weaviate_api_key}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        return {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000)}
    except Exception as exc:
        logger.warning("Health: Weaviate check failed", exc_info=exc)
        return {
            "status": "error",
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "error": str(exc),
        }


async def _check_groq() -> Dict[str, Any]:
    """List Groq models — zero token usage, confirms API key works."""
    t0 = time.monotonic()
    if not settings.groq_api_key:
        return {"status": "error", "error": "GROQ_API_KEY not configured"}
    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=settings.groq_api_key, timeout=10)
        models = await client.models.list()
        model_count = len(models.data) if hasattr(models, "data") else "?"
        return {
            "status": "ok",
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "models_available": model_count,
        }
    except Exception as exc:
        logger.warning("Health: Groq check failed", exc_info=exc)
        return {
            "status": "error",
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "error": str(exc),
        }


async def _check_embeddings() -> Dict[str, Any]:
    """Embed a single short string via VoyageAI to confirm the key works."""
    t0 = time.monotonic()
    if not settings.rag_embeddings_enabled:
        return {"status": "disabled", "note": "RAG_EMBEDDINGS_ENABLED=false"}
    if not (settings.voyage_api_key or settings.embedding_api_key):
        return {"status": "error", "error": "VOYAGE_API_KEY not configured"}
    try:
        import voyageai

        client = voyageai.AsyncClient(
            api_key=(settings.voyage_api_key or settings.embedding_api_key)
        )
        result = await client.embed(
            ["health check"], model=settings.embedding_model, input_type="query"
        )
        dims = len(result.embeddings[0]) if result.embeddings else 0
        return {
            "status": "ok",
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "model": settings.embedding_model,
            "dimensions": dims,
        }
    except Exception as exc:
        logger.warning("Health: VoyageAI embeddings check failed", exc_info=exc)
        return {
            "status": "error",
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "error": str(exc),
        }


async def _check_storage() -> Dict[str, Any]:
    """List the root of the Supabase Storage bucket (confirms key + bucket exist)."""
    t0 = time.monotonic()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return {"status": "error", "error": "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured"}
    try:
        import asyncio
        from supabase import create_client

        def _list_bucket():
            client = create_client(settings.supabase_url, settings.supabase_service_role_key)
            return client.storage.from_(settings.supabase_storage_bucket).list("")

        files = await asyncio.to_thread(_list_bucket)
        return {
            "status": "ok",
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "bucket": settings.supabase_storage_bucket,
            "objects_at_root": len(files) if isinstance(files, list) else "?",
        }
    except Exception as exc:
        logger.warning("Health: Supabase Storage check failed", exc_info=exc)
        return {
            "status": "error",
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "error": str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Readiness probe
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/health/ready",
    summary="Readiness probe",
    description=(
        "Pings every external dependency concurrently: Supabase Postgres, "
        "Weaviate, Groq, VoyageAI embeddings (if enabled), and Supabase Storage. "
        "Returns 200 if all required services are reachable, 503 otherwise."
    ),
)
async def readiness_check():
    # Run all checks concurrently
    (
        db_result,
        weaviate_result,
        groq_result,
        embeddings_result,
        storage_result,
    ) = await asyncio.gather(
        _check_database(),
        _check_weaviate(),
        _check_groq(),
        _check_embeddings(),
        _check_storage(),
        return_exceptions=False,
    )

    services = {
        "database":   db_result,
        "weaviate":   weaviate_result,
        "groq":       groq_result,
        "embeddings": embeddings_result,
        "storage":    storage_result,
    }

    # Required services (embeddings is optional when disabled)
    required = ["database", "weaviate", "groq", "storage"]
    if settings.rag_embeddings_enabled:
        required.append("embeddings")

    failed = [
        name for name in required
        if services[name].get("status") == "error"
    ]

    overall = "healthy" if not failed else "unhealthy"
    http_status = 200 if not failed else 503

    body = {
        "status": overall,
        "version": settings.app_version,
        "environment": settings.app_env,
        "services": services,
    }
    if failed:
        body["failed"] = failed

    return JSONResponse(content=body, status_code=http_status)
