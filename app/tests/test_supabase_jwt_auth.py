"""Supabase Auth JWT acceptance alongside legacy portal tokens."""
import json
import time

import jwt
import pytest


@pytest.mark.asyncio
@pytest.mark.api
async def test_supabase_jwt_admin_company_list(client, sample_company_id):
    from app.core import config

    s = config.settings
    secret = "test-supabase-jwt-secret-hs256"
    s.supabase_jwt_secret = secret
    s.portal_admin_api_key = "x-admin-only"
    try:
        tok = jwt.encode(
            {
                "sub": "11111111-1111-1111-1111-111111111111",
                "aud": "authenticated",
                "exp": int(time.time()) + 600,
                "app_metadata": {"role": "admin"},
            },
            secret,
            algorithm="HS256",
        )
        rdeny = await client.get("/api/v1/portal/admin/companies")
        assert rdeny.status_code == 403

        rok = await client.get(
            "/api/v1/portal/admin/companies",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert rok.status_code == 200
        ids = [c["id"] for c in rok.json()["data"]]
        assert str(sample_company_id) in ids
    finally:
        s.supabase_jwt_secret = None
        s.portal_admin_api_key = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_supabase_jwt_user_portal_chat(client, sample_company_id, mock_llm_client):
    from app.core import config

    s = config.settings
    secret = "test-supabase-jwt-secret-hs256"
    s.supabase_jwt_secret = secret
    s.portal_company_keys_json = json.dumps({str(sample_company_id): "tenant-secret"})
    try:
        tok = jwt.encode(
            {
                "sub": "22222222-2222-2222-2222-222222222222",
                "aud": "authenticated",
                "exp": int(time.time()) + 600,
                "app_metadata": {
                    "role": "user",
                    "company_id": str(sample_company_id),
                },
            },
            secret,
            algorithm="HS256",
        )
        bad = await client.post(
            "/api/v1/portal/chat",
            json={"company_id": str(sample_company_id), "message": "hi"},
        )
        assert bad.status_code == 403

        other = str(__import__("uuid").uuid4())
        wrong = await client.post(
            "/api/v1/portal/chat",
            json={"company_id": other, "message": "hi"},
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert wrong.status_code == 403

        ok = await client.post(
            "/api/v1/portal/chat",
            json={"company_id": str(sample_company_id), "message": "hello"},
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert ok.status_code == 200
        assert ok.json()["success"] is True
    finally:
        s.supabase_jwt_secret = None
        s.portal_company_keys_json = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_supabase_jwt_user_with_x_admin_key_allows_admin_route(
    client, sample_company_id
):
    """X-Admin-Key is checked before Bearer role — SPA can send Supabase token + key."""
    from app.core import config

    s = config.settings
    secret = "test-supabase-jwt-secret-hs256"
    s.supabase_jwt_secret = secret
    s.portal_admin_api_key = "shared-admin-key"
    try:
        tok = jwt.encode(
            {
                "sub": "44444444-4444-4444-4444-444444444444",
                "aud": "authenticated",
                "exp": int(time.time()) + 600,
                "app_metadata": {
                    "role": "user",
                    "company_id": str(sample_company_id),
                },
            },
            secret,
            algorithm="HS256",
        )
        r = await client.get(
            "/api/v1/portal/admin/companies",
            headers={
                "Authorization": f"Bearer {tok}",
                "X-Admin-Key": "shared-admin-key",
            },
        )
        assert r.status_code == 200
    finally:
        s.supabase_jwt_secret = None
        s.portal_admin_api_key = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_supabase_jwt_user_denied_admin_route(client, sample_company_id):
    from app.core import config

    s = config.settings
    secret = "test-supabase-jwt-secret-hs256"
    s.supabase_jwt_secret = secret
    try:
        tok = jwt.encode(
            {
                "sub": "33333333-3333-3333-3333-333333333333",
                "aud": "authenticated",
                "exp": int(time.time()) + 600,
                "app_metadata": {
                    "role": "user",
                    "company_id": str(sample_company_id),
                },
            },
            secret,
            algorithm="HS256",
        )
        r = await client.get(
            "/api/v1/portal/admin/companies",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 403
    finally:
        s.supabase_jwt_secret = None
