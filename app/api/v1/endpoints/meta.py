"""
Public metadata endpoints.

No authentication required — used by admin / portal UIs to render language
pickers in sync with backend validation (``SUPPORTED_LANGUAGES``).
"""
from typing import List

from fastapi import APIRouter

from app.core.response import APIResponse
from app.schemas.common import LANGUAGE_CATALOG, LanguageOptionRead

router = APIRouter(prefix="/meta", tags=["Meta"])


@router.get(
    "/languages",
    response_model=APIResponse[List[LanguageOptionRead]],
    summary="Supported reply languages (codes + labels)",
)
async def get_language_catalog() -> APIResponse[List[LanguageOptionRead]]:
    """Return every language code the API accepts for ``supported_languages``."""
    return APIResponse(success=True, data=list(LANGUAGE_CATALOG))
