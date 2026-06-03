"""API tests for portal routes."""
import json
import uuid

import pytest


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_get_config_overview(client, sample_company_id):
    """Portal config read uses same open auth as chat in tests."""
    r = await client.get(
        f"/api/v1/portal/companies/{sample_company_id}/config/overview",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["company_id"] == str(sample_company_id)
    assert "system_prompt" in data["prompt"] or data["prompt"].get("system_prompt") is None
    assert "global_defaults" in data["rag"]
    assert data["rag"]["global_defaults"]["top_k"] >= 1
    assert "weaviate_collection" in data["integration"]
    assert "language_catalog" in data
    assert len(data["language_catalog"]) == 3
    assert {x["code"] for x in data["language_catalog"]} == {
        "english",
        "hindi",
        "hinglish",
    }
    integ = data["integration"]
    assert "has_twilio_auth_token" in integ
    assert "twilio_credentials_complete" in integ
    assert "twilio_credentials_save_path" in integ
    assert str(sample_company_id) in integ["twilio_credentials_save_path"]
    assert integ["twilio_credentials_complete"] is True
    assert integ["has_twilio_auth_token"] is True
    assert "handoff_staff_notify_configured" in integ
    assert integ["handoff_staff_notify_configured"] is False


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_get_prompt_and_rag_slices(client, sample_company_id):
    pr = await client.get(
        f"/api/v1/portal/companies/{sample_company_id}/config/prompt",
    )
    assert pr.status_code == 200
    assert "supported_languages" in pr.json()["data"]
    rr = await client.get(
        f"/api/v1/portal/companies/{sample_company_id}/config/rag",
    )
    assert rr.status_code == 200
    assert "rag_config_json" in rr.json()["data"]


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_chat_returns_answer(client, sample_company_id, mock_llm_client):
    """Without PORTAL_COMPANY_KEYS_JSON, chat is open (dev mode)."""
    r = await client.post(
        "/api/v1/portal/chat",
        json={
            "company_id": str(sample_company_id),
            "message": "What is your return policy?",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert "answer" in data
    assert data["response_type"] in ("rag", "fallback")
    mock_llm_client.generate_answer.assert_called()


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_chat_accepts_x_admin_key(
    client, sample_company_id, mock_llm_client
):
    """SPA sends X-Admin-Key on all apiFetch calls; chat must honor it."""
    from app.core import config

    s = config.settings
    s.portal_admin_api_key = "chat-admin-key"
    try:
        r = await client.post(
            "/api/v1/portal/chat",
            json={
                "company_id": str(sample_company_id),
                "message": "Hello",
            },
            headers={
                "Authorization": "Bearer ignored-when-admin-key-matches",
                "X-Admin-Key": "chat-admin-key",
            },
        )
        assert r.status_code == 200
        assert r.json()["success"] is True
    finally:
        s.portal_admin_api_key = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_chat_rejects_wrong_company_key(
    client, sample_company_id, mock_llm_client
):
    from app.core import config

    s = config.settings
    s.portal_company_keys_json = json.dumps(
        {str(sample_company_id): "correct-secret"}
    )
    try:
        r = await client.post(
            "/api/v1/portal/chat",
            json={
                "company_id": str(sample_company_id),
                "message": "Hello",
            },
            headers={"X-Portal-Company-Key": "wrong-secret"},
        )
        assert r.status_code == 403
    finally:
        s.portal_company_keys_json = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_admin_companies_requires_admin_key(
    client, sample_company_id
):
    from app.core import config

    s = config.settings
    s.portal_admin_api_key = "super-admin"
    try:
        r = await client.get("/api/v1/portal/admin/companies")
        assert r.status_code == 403

        r2 = await client.get(
            "/api/v1/portal/admin/companies",
            headers={"X-Admin-Key": "super-admin"},
        )
        assert r2.status_code == 200
        data = r2.json()["data"]
        assert len(data) >= 1
        assert any(str(sample_company_id) == c["id"] for c in data)
    finally:
        s.portal_admin_api_key = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_bootstrap_first_admin_then_conflict(client):
    from app.core import config

    s = config.settings
    s.portal_bootstrap_secret = "bootstrap-test-secret"
    try:
        r = await client.post(
            "/api/v1/portal/auth/bootstrap-first-admin",
            json={
                "username": "rootadmin",
                "password": "longpassword1",
                "bootstrap_secret": "bootstrap-test-secret",
            },
        )
        assert r.status_code == 201
        r2 = await client.post(
            "/api/v1/portal/auth/bootstrap-first-admin",
            json={
                "username": "other",
                "password": "longpassword2",
                "bootstrap_secret": "bootstrap-test-secret",
            },
        )
        assert r2.status_code == 409
    finally:
        s.portal_bootstrap_secret = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_login_and_bearer_admin_companies(client, sample_company_id):
    from app.core import config

    s = config.settings
    s.portal_bootstrap_secret = "bsecret"
    s.portal_admin_api_key = "x-only-key"
    try:
        await client.post(
            "/api/v1/portal/auth/bootstrap-first-admin",
            json={
                "username": "adm",
                "password": "longpassw0rd",
                "bootstrap_secret": "bsecret",
            },
        )
        r = await client.post(
            "/api/v1/portal/auth/login",
            json={"username": "adm", "password": "longpassw0rd"},
        )
        assert r.status_code == 200
        token = r.json()["data"]["access_token"]
        rdeny = await client.get("/api/v1/portal/admin/companies")
        assert rdeny.status_code == 403
        rok = await client.get(
            "/api/v1/portal/admin/companies",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rok.status_code == 200
        assert any(
            str(sample_company_id) == c["id"] for c in rok.json()["data"]
        )
    finally:
        s.portal_bootstrap_secret = None
        s.portal_admin_api_key = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_tenant_user_chat_bearer_wrong_company_forbidden(
    client, sample_company_id, mock_llm_client
):
    from app.core import config

    s = config.settings
    s.portal_bootstrap_secret = "bs1"
    try:
        await client.post(
            "/api/v1/portal/auth/bootstrap-first-admin",
            json={
                "username": "adm2",
                "password": "longpassw0rd",
                "bootstrap_secret": "bs1",
            },
        )
        adm = await client.post(
            "/api/v1/portal/auth/login",
            json={"username": "adm2", "password": "longpassw0rd"},
        )
        adm_tok = adm.json()["data"]["access_token"]
        cu = await client.post(
            "/api/v1/portal/admin/users",
            headers={"Authorization": f"Bearer {adm_tok}"},
            json={
                "username": "tenant1",
                "password": "longpassw0rd",
                "role": "user",
                "company_id": str(sample_company_id),
            },
        )
        assert cu.status_code == 201
        tr = await client.post(
            "/api/v1/portal/auth/login",
            json={"username": "tenant1", "password": "longpassw0rd"},
        )
        ttok = tr.json()["data"]["access_token"]
        other = str(uuid.uuid4())
        bad = await client.post(
            "/api/v1/portal/chat",
            json={"company_id": other, "message": "hi"},
            headers={"Authorization": f"Bearer {ttok}"},
        )
        assert bad.status_code == 403
        ok = await client.post(
            "/api/v1/portal/chat",
            json={"company_id": str(sample_company_id), "message": "hi"},
            headers={"Authorization": f"Bearer {ttok}"},
        )
        assert ok.status_code == 200
    finally:
        s.portal_bootstrap_secret = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_create_user_rejects_bcrypt_password_over_72_bytes(
    client, sample_company_id
):
    from app.core import config

    s = config.settings
    s.portal_bootstrap_secret = "bs-long-password"
    try:
        await client.post(
            "/api/v1/portal/auth/bootstrap-first-admin",
            json={
                "username": "adm_long_password",
                "password": "longpassw0rd",
                "bootstrap_secret": "bs-long-password",
            },
        )
        adm = await client.post(
            "/api/v1/portal/auth/login",
            json={"username": "adm_long_password", "password": "longpassw0rd"},
        )
        adm_tok = adm.json()["data"]["access_token"]
        r = await client.post(
            "/api/v1/portal/admin/users",
            headers={"Authorization": f"Bearer {adm_tok}"},
            json={
                "username": "tenant_long_password",
                "password": "x" * 73,
                "role": "user",
                "company_id": str(sample_company_id),
            },
        )
        assert r.status_code == 422
        assert "72 bytes" in r.json()["error"]
    finally:
        s.portal_bootstrap_secret = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_chat_admin_bearer_skips_company_key(
    client, sample_company_id, mock_llm_client
):
    from app.core import config

    s = config.settings
    s.portal_company_keys_json = json.dumps(
        {str(sample_company_id): "tenant-secret"}
    )
    s.portal_bootstrap_secret = "bs2"
    try:
        await client.post(
            "/api/v1/portal/auth/bootstrap-first-admin",
            json={
                "username": "adm3",
                "password": "longpassw0rd",
                "bootstrap_secret": "bs2",
            },
        )
        lr = await client.post(
            "/api/v1/portal/auth/login",
            json={"username": "adm3", "password": "longpassw0rd"},
        )
        tok = lr.json()["data"]["access_token"]
        r = await client.post(
            "/api/v1/portal/chat",
            json={
                "company_id": str(sample_company_id),
                "message": "hello",
            },
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
    finally:
        s.portal_bootstrap_secret = None
        s.portal_company_keys_json = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_admin_twilio_requires_auth_token_first_time(
    client, valid_onboarding_payload
):
    """First Twilio save must include auth token; later updates may omit it."""
    from app.core import config

    s = config.settings
    s.portal_admin_api_key = "twilio-admin-test"
    try:
        uid = uuid.uuid4().hex[:10]
        n = abs(hash(uid)) % 9000000000 + 1000000000
        payload = {
            **valid_onboarding_payload,
            "company_name": f"tw-co-{uid}",
            "phone_number": f"+91{n}",
        }
        ob = await client.post(
            "/api/v1/onboarding/company/full",
            json=payload,
            headers={"X-Admin-Key": "twilio-admin-test"},
        )
        assert ob.status_code == 201, ob.text
        summary = ob.json()["data"]
        company_id = summary["company"]["id"]
        url = f"/api/v1/portal/admin/companies/{company_id}/twilio"
        hdr = {"X-Admin-Key": "twilio-admin-test"}
        wa = f"whatsapp:+1786555{n % 10000:04d}"
        bad = await client.post(
            url,
            headers=hdr,
            json={
                "twilio_whatsapp_number": wa,
                "twilio_account_sid": "AC" + "a" * 32,
                "enable_twilio_provider": True,
            },
        )
        assert bad.status_code == 422
        ok = await client.post(
            url,
            headers=hdr,
            json={
                "twilio_whatsapp_number": wa,
                "twilio_account_sid": "AC" + "b" * 32,
                "twilio_auth_token": "first-time-token-ok-32chars!!",
                "enable_twilio_provider": True,
            },
        )
        assert ok.status_code == 200
        assert ok.json()["data"]["has_twilio_auth_token"] is True
        keep = await client.post(
            url,
            headers=hdr,
            json={
                "twilio_whatsapp_number": wa,
                "twilio_account_sid": "AC" + "c" * 32,
                "enable_twilio_provider": True,
            },
        )
        assert keep.status_code == 200
        assert keep.json()["data"]["has_twilio_auth_token"] is True
        assert keep.json()["data"]["twilio_account_sid"] == "AC" + "c" * 32
    finally:
        s.portal_admin_api_key = None


@pytest.mark.asyncio
@pytest.mark.api
async def test_get_company_config_shows_twilio_flags(client, sample_company_id):
    r = await client.get(f"/api/v1/companies/{sample_company_id}/config")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["has_twilio_auth_token"] is True
    assert d["twilio_whatsapp_number"] is not None


@pytest.mark.asyncio
@pytest.mark.api
async def test_portal_inbox_lists_threads_and_patch_lead(
    client, db_session, sample_company_id
):
    from app.models.base import new_uuid
    from app.models.conversation import Conversation
    from app.models.message import Message

    cid = new_uuid()
    db_session.add(
        Conversation(
            id=cid,
            company_id=sample_company_id,
            customer_phone="+919876543210",
            current_mode="bot",
            status="active",
            lead_warmth=None,
            inquiry_complete=False,
        )
    )
    db_session.add(
        Message(
            id=new_uuid(),
            conversation_id=cid,
            company_id=sample_company_id,
            sender_type="customer",
            message_text="Need product price",
        )
    )
    await db_session.flush()

    r = await client.get(
        f"/api/v1/portal/companies/{sample_company_id}/inbox/conversations",
    )
    assert r.status_code == 200
    rows = r.json()["data"]
    assert len(rows) == 1
    assert rows[0]["customer_phone"] == "+919876543210"
    assert "price" in (rows[0].get("last_message_preview") or "").lower()

    pr = await client.patch(
        f"/api/v1/portal/companies/{sample_company_id}/inbox/conversations/{cid}",
        json={"lead_warmth": "hot", "inquiry_complete": True},
    )
    assert pr.status_code == 200
    body = pr.json()["data"]
    assert body["lead_warmth"] == "hot"
    assert body["lead_warmth_locked"] is True
    assert body["inquiry_complete"] is True
    assert body["inquiry_completed_at"] is not None

    clear = await client.patch(
        f"/api/v1/portal/companies/{sample_company_id}/inbox/conversations/{cid}",
        json={"lead_warmth": None},
    )
    assert clear.status_code == 200
    assert clear.json()["data"]["lead_warmth"] is None
    assert clear.json()["data"]["lead_warmth_locked"] is False

    open_only = await client.get(
        f"/api/v1/portal/companies/{sample_company_id}/inbox/conversations",
        params={"inquiry": "open"},
    )
    assert open_only.status_code == 200
    assert open_only.json()["data"] == []
