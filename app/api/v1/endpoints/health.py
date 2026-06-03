"""
Health check endpoints.

GET /health          – root-level liveness probe
GET /api/v1/health   – versioned alias

Both return the same structured response and require no authentication.
Used by load balancers, container orchestrators, and monitoring tools.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.response import APIResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=APIResponse[dict],
    summary="Liveness probe",
    description="Returns HTTP 200 while the service is running.",
)
async def health_check() -> APIResponse[dict]:
    """Minimal health check – always returns OK while the process is live."""
    return APIResponse(
        success=True,
        message="Service is running.",
        data={
            "status": "ok",
            "version": settings.app_version,
            "environment": settings.app_env,
        },
    )
