"""
Portal authentication helpers for first-party API clients.

Bearer tokens may be:

- **Supabase Auth** access JWTs when ``SUPABASE_JWT_SECRET`` is set (see
  ``app_metadata.role``: ``admin`` | ``user``, and ``company_id`` for users).
- **Legacy portal** tokens from ``POST /portal/auth/login`` (signed with
  ``SECRET_KEY``).

``PORTAL_COMPANY_KEYS_JSON`` maps each company UUID to a shared secret for
``X-Portal-Company-Key`` on chat when no Bearer is used.

``PORTAL_ADMIN_API_KEY`` protects admin-only routes when set. If the client
sends a matching ``X-Admin-Key`` header, that is accepted **before** the Bearer
token is checked — so the Vite app can send Supabase ``Authorization`` plus
``X-Admin-Key`` without putting ``SUPABASE_JWT_SECRET`` on the API. Otherwise a
Bearer with ``role: admin`` (Supabase or legacy portal) is required.
"""
import logging
import secrets
from typing import Optional
from uuid import UUID

from fastapi import Header, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired

from app.core.config import get_settings
from app.core.portal_tokens import decode_portal_token
from app.core.supabase_jwt import decode_supabase_access_token
from app.schemas.portal import PortalChatRequest

logger = logging.getLogger(__name__)


def verify_portal_company_key(company_id: UUID, portal_key: Optional[str]) -> None:
    """Raise 403 unless the portal company key matches configuration."""
    settings = get_settings()
    keys = settings.portal_company_keys

    if not keys:
        logger.warning(
            "Portal chat request with no PORTAL_COMPANY_KEYS_JSON — allowing "
            "(configure keys before production)"
        )
        return

    cid = str(company_id)
    expected = keys.get(cid)
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Portal access is not configured for this company.",
        )
    if not portal_key or not secrets.compare_digest(expected, portal_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid portal company key.",
        )


def _claims_from_bearer_authorization(
    authorization: Optional[str],
) -> Optional[dict]:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    if not token:
        return None
    settings = get_settings()
    if settings.supabase_jwt_secret:
        sup = decode_supabase_access_token(token)
        if sup is not None:
            return sup
        # HS256 JWT shape but not a valid portal Supabase session
        if False and token.count(".") == 2:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Supabase token is not valid for this API: set the user's "
                    "app_metadata.role to admin or user in Supabase (and "
                    "app_metadata.company_id for tenant users), and ensure "
                    "SUPABASE_JWT_SECRET on the API matches Project Settings → "
                    "JWT Secret."
                ),
            )
    try:
        return decode_portal_token(token)
    except (BadSignature, SignatureExpired):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired token.",
        )


async def verify_portal_admin(
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
) -> None:
    """
    Allow access if:

    1. ``X-Admin-Key`` matches ``PORTAL_ADMIN_API_KEY`` (checked first so a
       non-admin Supabase Bearer does not block this path), or
    2. Bearer decodes to an admin (Supabase JWT with ``SUPABASE_JWT_SECRET``,
       or legacy portal token), or
    3. ``PORTAL_ADMIN_API_KEY`` is unset (open admin in dev — avoid in prod).
    """
    expected = get_settings().portal_admin_api_key
    if expected and x_admin_key and secrets.compare_digest(expected, x_admin_key):
        return

    claims = _claims_from_bearer_authorization(authorization)
    if claims is not None:
        if claims.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required.",
            )
        return

    if not expected:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid or missing admin API key.",
    )


def _authorize_portal_for_company(
    company_id: UUID,
    authorization: Optional[str],
    x_portal_company_key: Optional[str],
) -> None:
    """
    Authorize access to *company_id* using Bearer (admin/user) or
    ``X-Portal-Company-Key``. Does not check ``X-Admin-Key`` (handled by callers).
    """
    claims = _claims_from_bearer_authorization(authorization)
    if claims is not None:
        role = claims.get("role")
        cid = claims.get("company_id")
        if role == "admin":
            return
        if role == "user":
            if not cid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Portal user has no company assigned.",
                )
            if str(company_id) != str(cid):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Token not valid for this company.",
                )
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid portal token.",
        )

    verify_portal_company_key(company_id, x_portal_company_key)


async def require_portal_company_access(
    company_id: UUID,
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    x_portal_company_key: Optional[str] = Header(None, alias="X-Portal-Company-Key"),
) -> UUID:
    """
    Dependency: same rules as portal chat — admin key, then Bearer, then company key.

    Returns *company_id* when authorized.
    """
    expected = get_settings().portal_admin_api_key
    if expected and x_admin_key and secrets.compare_digest(expected, x_admin_key):
        return company_id
    _authorize_portal_for_company(company_id, authorization, x_portal_company_key)
    return company_id


async def portal_chat_body_with_auth(
    body: PortalChatRequest,
    authorization: Optional[str] = Header(None),
    x_portal_company_key: Optional[str] = Header(
        None, alias="X-Portal-Company-Key"
    ),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
) -> PortalChatRequest:
    """
    Allow chat if:

    1. ``X-Admin-Key`` matches ``PORTAL_ADMIN_API_KEY`` (same as admin APIs;
       required when the SPA sends a Supabase Bearer the API cannot verify).
    2. Bearer decodes to admin (any company) or user (body.company_id must match).
    3. No Bearer: ``X-Portal-Company-Key`` when ``PORTAL_COMPANY_KEYS_JSON`` is set,
       or open mode when company keys are unset (dev only).
    """
    expected = get_settings().portal_admin_api_key
    if expected and x_admin_key and secrets.compare_digest(expected, x_admin_key):
        return body

    _authorize_portal_for_company(
        body.company_id, authorization, x_portal_company_key
    )
    return body


verify_onboarding_admin = verify_portal_admin
