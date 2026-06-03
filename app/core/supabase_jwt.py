"""Validate Supabase Auth access tokens (HS256 JWT) for API authorization."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

import jwt

from app.core.config import get_settings


def decode_supabase_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify Supabase-issued JWT and return claims compatible with portal auth:
    ``sub``, ``role`` (admin|user), ``company_id`` (string UUID or None).

    Required Supabase setup: set ``app_metadata`` on each user, e.g.::

        {"role": "admin"}

    or ::

        {"role": "user", "company_id": "<company-uuid>"}

    Returns None if ``SUPABASE_JWT_SECRET`` is unset or the token is invalid.
    """
    secret = get_settings().supabase_jwt_secret
    if not secret:
        return None
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
    except jwt.PyJWTError:
        return None

    meta = payload.get("app_metadata")
    if not isinstance(meta, dict):
        return None
    role = meta.get("role")
    if role not in ("admin", "user"):
        return None

    company_id = meta.get("company_id")
    if role == "user":
        if company_id is None:
            return None
        try:
            UUID(str(company_id))
        except ValueError:
            return None

    sub = payload.get("sub")
    if not sub:
        return None

    out: Dict[str, Any] = {
        "sub": str(sub),
        "role": role,
        "company_id": str(company_id) if company_id else None,
    }
    return out
