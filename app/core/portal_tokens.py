"""Signed portal access tokens (first-party API clients)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from itsdangerous import URLSafeTimedSerializer

from app.core.config import get_settings

_TOKEN_SALT = "portal-auth-v1"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt=_TOKEN_SALT)


def create_portal_token(
    user_id: str, role: str, company_id: Optional[str]
) -> str:
    payload: Dict[str, Any] = {"sub": user_id, "role": role, "cid": company_id}
    return _serializer().dumps(payload)


def decode_portal_token(token: str) -> Dict[str, Optional[str]]:
    """
    Validate signature and max_age; return claims with keys:
    sub (user id), role, company_id (or None).
    """
    raw = _serializer().loads(
        token, max_age=get_settings().portal_token_max_age_seconds
    )
    return {
        "sub": str(raw["sub"]),
        "role": str(raw["role"]),
        "company_id": raw.get("cid"),
    }
