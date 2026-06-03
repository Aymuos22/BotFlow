"""
Portal API — company-scoped RAG chat and admin helpers for first-party clients.

POST /api/v1/portal/chat
    Body: { company_id, message }
    Header: Authorization: Bearer <Supabase or portal token>, and/or
        X-Admin-Key (must match PORTAL_ADMIN_API_KEY when set — same as admin UI),
        OR X-Portal-Company-Key when PORTAL_COMPANY_KEYS_JSON is set without Bearer.

GET /api/v1/portal/companies/{company_id}/config
GET /api/v1/portal/companies/{company_id}/config/overview
GET /api/v1/portal/companies/{company_id}/config/prompt
GET /api/v1/portal/companies/{company_id}/config/rag
GET /api/v1/portal/companies/{company_id}/config/escalation
    Same auth as chat: admin key, Bearer (admin/user), or X-Portal-Company-Key.

POST /api/v1/portal/auth/login — DB-backed portal users.
POST /api/v1/portal/auth/bootstrap-first-admin — first admin (requires PORTAL_BOOTSTRAP_SECRET).

GET /api/v1/portal/admin/companies
GET/POST /api/v1/portal/admin/users
    Header: X-Admin-Key or Bearer (admin), when PORTAL_ADMIN_API_KEY is set.
"""
import secrets
import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.portal_auth import (
    portal_chat_body_with_auth,
    require_portal_company_access,
    verify_portal_admin,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.passwords import hash_password, verify_password
from app.core.portal_tokens import create_portal_token
from app.core.exceptions import NotFoundError
from app.core.response import APIResponse
from app.integrations.embeddings.client import get_embedding_client
from app.integrations.llm.client import LLMClientProtocol, get_llm_client
from app.integrations.weaviate.client import WeaviateClient, get_weaviate_client
from app.models.company import Company
from app.models.portal_user import PortalUser
from app.repositories.company_channel_repository import CompanyChannelRepository
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.portal_user_repository import PortalUserRepository
from app.services.google_sheets_sync_service import GoogleSheetsSyncService
from app.services.language_service import last_decisive_user_language_from_history
from app.schemas.common import LANGUAGE_CATALOG
from app.schemas.company_config import CompanyConfigRead
from app.schemas.portal import (
    PortalAuthLoginRequest,
    PortalAuthLoginResponse,
    PortalBootstrapRequest,
    PortalChatRequest,
    PortalChatResponse,
    PortalCompanySummary,
    PortalConfigOverviewResponse,
    PortalFallbackHandoffResponse,
    PortalIntegrationSummary,
    PortalPromptConfigResponse,
    PortalRagConfigResponse,
    PortalRagDefaultsResponse,
    PortalUserCreateRequest,
    PortalUserPasswordResetRequest,
    PortalUserPublic,
    RagSourceItem,
    PortalAisensyConfigUpdateRequest,
    PortalAisensyConfigUpdateResponse,
    PortalMetaWhatsappConfigUpdateRequest,
    PortalMetaWhatsappConfigUpdateResponse,
    PortalTwilioConfigUpdateRequest,
    PortalTwilioConfigUpdateResponse,
)
from app.services.fallback_service import FallbackService
from app.services.rag_service import RAGService

router = APIRouter(prefix="/portal", tags=["Portal"])


def _portal_rag_defaults() -> PortalRagDefaultsResponse:
    s = get_settings()
    return PortalRagDefaultsResponse(
        score_threshold=s.rag_score_threshold,
        top_k=s.rag_top_k,
        hybrid_alpha=s.rag_hybrid_alpha,
        rag_embeddings_enabled=s.rag_embeddings_enabled,
        rag_conversation_turns=s.rag_conversation_turns,
        rag_augment_search_with_history=s.rag_augment_search_with_history,
    )


async def _get_company_config_or_404(
    db: AsyncSession, company_id: uuid.UUID
):
    company_repo = CompanyRepository(db)
    config_repo = CompanyConfigRepository(db)
    company = await company_repo.get(company_id)
    if not company:
        raise NotFoundError("Company", str(company_id))
    config = await config_repo.get_by_company(company_id)
    if not config:
        raise NotFoundError("CompanyConfig", str(company_id))
    return config


def _portal_user_public(user: PortalUser) -> PortalUserPublic:
    return PortalUserPublic(
        id=user.id,
        username=user.username,
        role=user.role,  # type: ignore[arg-type]
        company_id=user.company_id,
        is_active=user.is_active,
    )


def _build_rag_service(
    db: AsyncSession,
    weaviate: WeaviateClient,
    llm: LLMClientProtocol,
) -> RAGService:
    s = get_settings()
    return RAGService(
        config_repo=CompanyConfigRepository(db),
        weaviate_client=weaviate,
        llm_client=llm,
        fallback_service=FallbackService(),
        default_top_k=s.rag_top_k,
        default_score_threshold=s.rag_score_threshold,
        default_hybrid_alpha=s.rag_hybrid_alpha,
        default_conversation_turns=s.rag_conversation_turns,
        augment_search_with_history=s.rag_augment_search_with_history,
        embedding_client=get_embedding_client(),
    )


# ------------------------------------------------------------------ #
# Company config (read) — same auth as portal chat
# ------------------------------------------------------------------ #


@router.get(
    "/companies/{company_id}/config",
    response_model=APIResponse[CompanyConfigRead],
    summary="Get full company config (portal)",
)
async def portal_get_company_config(
    company_id: uuid.UUID,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Return the same payload as ``GET /companies/{id}/config`` with portal auth."""
    config = await _get_company_config_or_404(db, company_id)
    return APIResponse(success=True, data=CompanyConfigRead.model_validate(config))


@router.get(
    "/companies/{company_id}/config/overview",
    response_model=APIResponse[PortalConfigOverviewResponse],
    summary="Get prompt, RAG, escalation, integration summary (portal)",
)
async def portal_get_config_overview(
    company_id: uuid.UUID,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """One response grouping prompt, RAG JSON, escalation JSON, and integration IDs."""
    config = await _get_company_config_or_404(db, company_id)
    channel_repo = CompanyChannelRepository(db)
    primary = await channel_repo.get_primary_by_company(company_id, "whatsapp")
    channel_key: Optional[str] = primary.session_name if primary else None
    g = _portal_rag_defaults()
    data = PortalConfigOverviewResponse(
        company_id=config.company_id,
        updated_at=config.updated_at,
        prompt=PortalPromptConfigResponse(
            system_prompt=config.system_prompt,
            default_language=config.default_language,
            supported_languages=list(config.supported_languages or ["english"]),
        ),
        rag=PortalRagConfigResponse(
            rag_config_json=config.rag_config_json,
            global_defaults=g,
        ),
        escalation=PortalFallbackHandoffResponse(
            fallback_config_json=config.fallback_config_json,
            handoff_config_json=config.handoff_config_json,
            business_hours_json=config.business_hours_json,
        ),
        integration=PortalIntegrationSummary(
            weaviate_collection=config.weaviate_collection,
            whatsapp_channel_key=channel_key,
            whatsapp_provider=getattr(config, "whatsapp_provider", None),
            twilio_whatsapp_number=getattr(config, "twilio_whatsapp_number", None),
            twilio_account_sid=getattr(config, "twilio_account_sid", None),
            has_twilio_auth_token=bool(
                getattr(config, "has_stored_twilio_auth_token", False)
            ),
            twilio_credentials_complete=bool(
                getattr(config, "twilio_whatsapp_number", None)
                and getattr(config, "twilio_account_sid", None)
                and getattr(config, "has_stored_twilio_auth_token", False)
            ),
            handoff_staff_notify_configured=bool(
                getattr(config, "handoff_staff_notify_whatsapp", None)
            ),
            twilio_credentials_save_path=(
                f"/api/v1/portal/admin/companies/{company_id}/twilio"
            ),
            aisensy_whatsapp_number=getattr(
                config, "aisensy_whatsapp_number", None
            ),
            aisensy_project_id=getattr(config, "aisensy_project_id", None),
            has_aisensy_api_key=bool(
                getattr(config, "has_stored_aisensy_api_key", False)
            ),
            aisensy_credentials_complete=bool(
                getattr(config, "aisensy_whatsapp_number", None)
                and getattr(config, "aisensy_project_id", None)
                and getattr(config, "has_stored_aisensy_api_key", False)
            ),
            aisensy_credentials_save_path=(
                f"/api/v1/portal/admin/companies/{company_id}/aisensy"
            ),
            meta_phone_number_id=getattr(config, "meta_phone_number_id", None),
            meta_waba_id=getattr(config, "meta_waba_id", None),
            has_meta_graph_token=bool(
                getattr(config, "has_stored_meta_graph_token", False)
            ),
            meta_credentials_complete=bool(
                getattr(config, "meta_phone_number_id", None)
                and getattr(config, "has_stored_meta_graph_token", False)
                and getattr(config, "has_stored_meta_webhook_verify_token", False)
            ),
            meta_credentials_save_path=(
                f"/api/v1/portal/admin/companies/{company_id}/meta-whatsapp"
            ),
            is_active=config.is_active,
        ),
        language_catalog=list(LANGUAGE_CATALOG),
    )
    return APIResponse(success=True, data=data)


@router.get(
    "/companies/{company_id}/config/prompt",
    response_model=APIResponse[PortalPromptConfigResponse],
    summary="Get system prompt and language settings (portal)",
)
async def portal_get_prompt_config(
    company_id: uuid.UUID,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    config = await _get_company_config_or_404(db, company_id)
    data = PortalPromptConfigResponse(
        system_prompt=config.system_prompt,
        default_language=config.default_language,
        supported_languages=list(config.supported_languages or ["english"]),
    )
    return APIResponse(success=True, data=data)


@router.get(
    "/companies/{company_id}/config/rag",
    response_model=APIResponse[PortalRagConfigResponse],
    summary="Get RAG JSON + server defaults (portal)",
)
async def portal_get_rag_config(
    company_id: uuid.UUID,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    config = await _get_company_config_or_404(db, company_id)
    data = PortalRagConfigResponse(
        rag_config_json=config.rag_config_json,
        global_defaults=_portal_rag_defaults(),
    )
    return APIResponse(success=True, data=data)


@router.get(
    "/companies/{company_id}/config/escalation",
    response_model=APIResponse[PortalFallbackHandoffResponse],
    summary="Get fallback, handoff, business hours JSON (portal)",
)
async def portal_get_escalation_config(
    company_id: uuid.UUID,
    _: uuid.UUID = Depends(require_portal_company_access),
    db: AsyncSession = Depends(get_db),
) -> Any:
    config = await _get_company_config_or_404(db, company_id)
    data = PortalFallbackHandoffResponse(
        fallback_config_json=config.fallback_config_json,
        handoff_config_json=config.handoff_config_json,
        business_hours_json=config.business_hours_json,
    )
    return APIResponse(success=True, data=data)


@router.post(
    "/chat",
    response_model=APIResponse[PortalChatResponse],
    summary="Run RAG for a company (portal)",
)
async def portal_chat(
    body: PortalChatRequest = Depends(portal_chat_body_with_auth),
    db: AsyncSession = Depends(get_db),
    weaviate_client: WeaviateClient = Depends(get_weaviate_client),
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Any:
    """
    GPT-style backend: one question, one answer, against the company's Weaviate
    collection and config.  Does not create a conversation row (stateless).
    """
    rag = _build_rag_service(db, weaviate_client, llm_client)
    transcript: Optional[str] = None
    if body.history:
        lines: List[str] = []
        for turn in body.history:
            label = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{label}: {turn.content}")
        transcript = "\n".join(lines[-5:])[:2000]

    sticky = last_decisive_user_language_from_history(body.history)
    raw = await rag.process_query(
        company_id=body.company_id,
        query=body.message,
        conversation_id=None,
        message_id=None,
        background_tasks=background_tasks,  # retrieval log runs after HTTP response is sent
        conversation_transcript=transcript,
        conversation_reply_language=sticky,
    )
    sources = [
        RagSourceItem(
            file_name=s.get("file_name") or "",
            document_id=s.get("document_id"),
            chunk_index=s.get("chunk_index"),
            score=s.get("score"),
        )
        for s in (raw.get("sources") or [])
    ]
    data = PortalChatResponse(
        answer=raw["answer"],
        response_type=raw["response_type"],
        language=raw["language"],
        detected_language=raw["detected_language"],
        top_score=raw.get("top_score"),
        sources=sources or None,
        recommended_products=raw.get("recommended_products") or None,
    )
    return APIResponse(success=True, data=data)


@router.post(
    "/auth/login",
    response_model=APIResponse[PortalAuthLoginResponse],
    summary="Portal login (DB user)",
)
async def portal_login(
    body: PortalAuthLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    repo = PortalUserRepository(db)
    user = await repo.get_by_username(body.username.strip())
    settings = get_settings()
    if (
        not user
        or not user.is_active
        or not verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    token = create_portal_token(
        str(user.id),
        user.role,
        str(user.company_id) if user.company_id else None,
    )
    data = PortalAuthLoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.portal_token_max_age_seconds,
        user=_portal_user_public(user),
    )
    return APIResponse(success=True, data=data)


@router.post(
    "/auth/bootstrap-first-admin",
    response_model=APIResponse[PortalUserPublic],
    status_code=status.HTTP_201_CREATED,
    summary="Create first portal admin (empty portal_users table only)",
)
async def portal_bootstrap_first_admin(
    body: PortalBootstrapRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    settings = get_settings()
    if not settings.portal_bootstrap_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Portal bootstrap is disabled (set PORTAL_BOOTSTRAP_SECRET).",
        )
    if not secrets.compare_digest(
        settings.portal_bootstrap_secret, body.bootstrap_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid bootstrap secret.",
        )
    repo = PortalUserRepository(db)
    if await repo.count_all() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Portal users already exist; bootstrap is no longer allowed.",
        )
    if await repo.get_by_username(body.username.strip()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists.",
        )
    user = await repo.create(
        {
            "username": body.username.strip(),
            "password_hash": hash_password(body.password),
            "role": "admin",
            "company_id": None,
            "is_active": True,
        }
    )
    return APIResponse(success=True, data=_portal_user_public(user))


@router.get(
    "/admin/users",
    response_model=APIResponse[List[PortalUserPublic]],
    summary="List portal users",
)
async def portal_admin_list_users(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_portal_admin),
) -> Any:
    repo = PortalUserRepository(db)
    rows = await repo.list_all(limit=500)
    return APIResponse(
        success=True, data=[_portal_user_public(u) for u in rows]
    )


@router.post(
    "/admin/users",
    response_model=APIResponse[PortalUserPublic],
    status_code=status.HTTP_201_CREATED,
    summary="Create portal user",
)
async def portal_admin_create_user(
    body: PortalUserCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_portal_admin),
) -> Any:
    if body.role == "user":
        company = await db.get(Company, body.company_id)
        if company is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found.",
            )
    repo = PortalUserRepository(db)
    username = body.username.strip()
    if await repo.get_by_username(username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists.",
        )
    user = await repo.create(
        {
            "username": username,
            "password_hash": hash_password(body.password),
            "role": body.role,
            "company_id": body.company_id,
            "is_active": True,
        }
    )
    return APIResponse(success=True, data=_portal_user_public(user))


@router.post(
    "/admin/users/{user_id}/reset-password",
    response_model=APIResponse[PortalUserPublic],
    summary="Reset portal user password",
)
async def portal_admin_reset_user_password(
    user_id: uuid.UUID,
    body: PortalUserPasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_portal_admin),
) -> Any:
    repo = PortalUserRepository(db)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portal user not found.",
        )
    user.password_hash = hash_password(body.password)
    await db.flush()
    return APIResponse(success=True, data=_portal_user_public(user))


@router.get(
    "/admin/companies",
    response_model=APIResponse[List[PortalCompanySummary]],
    summary="List companies (portal admin)",
    status_code=status.HTTP_200_OK,
)
async def portal_admin_list_companies(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_portal_admin),
) -> Any:
    """Minimal company list for admin clients (e.g. onboarding tools)."""
    repo = CompanyRepository(db)
    rows = await repo.get_all(limit=500, offset=0)
    data = [
        PortalCompanySummary(
            id=c.id,
            name=c.name,
            display_name=c.display_name,
            status=c.status,
        )
        for c in rows
    ]
    return APIResponse(success=True, data=data)


@router.post(
    "/admin/google-sheets/provision",
    response_model=APIResponse[List[dict]],
    summary="Create/initialize Google Sheets for all companies",
    status_code=status.HTTP_200_OK,
)
async def portal_admin_provision_google_sheets(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_portal_admin),
) -> Any:
    repo = CompanyRepository(db)
    rows = await repo.get_all(limit=500, offset=0)
    sync = GoogleSheetsSyncService(db)
    data: list[dict] = []
    for company in rows:
        result = await sync.provision_company_sheet(company.id)
        if result:
            data.append(result)
    return APIResponse(success=True, data=data)


@router.post(
    "/admin/companies/{company_id}/twilio",
    response_model=APIResponse[PortalTwilioConfigUpdateResponse],
    summary="Configure Twilio WhatsApp for a company (admin)",
)
async def portal_admin_configure_twilio(
    company_id: uuid.UUID,
    body: PortalTwilioConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_portal_admin),
) -> Any:
    """
    Store per-company Twilio credentials and WhatsApp number.

    This enables multi-tenant Twilio where each company brings its own Twilio account.
    """
    cfg = await _get_company_config_or_404(db, company_id)

    twilio_number = body.twilio_whatsapp_number.strip()
    if not twilio_number.startswith("whatsapp:"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="twilio_whatsapp_number must start with 'whatsapp:'.",
        )

    # Enforce uniqueness at API-level too (DB unique index also exists).
    config_repo = CompanyConfigRepository(db)
    existing = await config_repo.get_by_twilio_number(twilio_number)
    if existing is not None and str(existing.company_id) != str(company_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Twilio WhatsApp number is already assigned to another company.",
        )

    # Apply updates (token stored encrypted by ORM property setter).
    cfg.twilio_whatsapp_number = twilio_number
    cfg.twilio_account_sid = body.twilio_account_sid.strip()
    token_in = (body.twilio_auth_token or "").strip()
    if token_in:
        cfg.twilio_auth_token = token_in
    elif not cfg._twilio_auth_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "twilio_auth_token is required when no token is stored yet. "
                "Omit the field only to keep an existing token when updating number or SID."
            ),
        )
    if body.enable_twilio_provider:
        cfg.whatsapp_provider = "twilio"

    await db.commit()
    await db.refresh(cfg)

    data = PortalTwilioConfigUpdateResponse(
        company_id=cfg.company_id,
        whatsapp_provider=cfg.whatsapp_provider,
        twilio_whatsapp_number=cfg.twilio_whatsapp_number,
        twilio_account_sid=cfg.twilio_account_sid,
        has_twilio_auth_token=bool(cfg.twilio_auth_token),
    )
    return APIResponse(success=True, data=data, message="Twilio configuration saved.")


@router.post(
    "/admin/companies/{company_id}/aisensy",
    response_model=APIResponse[PortalAisensyConfigUpdateResponse],
    summary="Configure AiSensy WhatsApp for a company (admin)",
)
async def portal_admin_configure_aisensy(
    company_id: uuid.UUID,
    body: PortalAisensyConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_portal_admin),
) -> Any:
    """
    Store per-company AiSensy Project API credentials and business WhatsApp number.

    Inbound webhooks are routed via ``aisensy_whatsapp_number``; outbound replies
    use the Project API (see ``AISENSY_SEND_TEXT_PATH`` / ``AISENSY_API_BASE_URL``).
    """
    cfg = await _get_company_config_or_404(db, company_id)

    aisensy_number = body.aisensy_whatsapp_number.strip()
    if not aisensy_number.startswith("whatsapp:"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="aisensy_whatsapp_number must start with 'whatsapp:'.",
        )

    config_repo = CompanyConfigRepository(db)
    existing = await config_repo.get_by_aisensy_number(aisensy_number)
    if existing is not None and str(existing.company_id) != str(company_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This AiSensy WhatsApp number is already assigned to another company.",
        )

    cfg.aisensy_whatsapp_number = aisensy_number
    cfg.aisensy_project_id = body.aisensy_project_id.strip()
    key_in = (body.aisensy_api_key or "").strip()
    if key_in:
        cfg.aisensy_api_key = key_in
    elif not cfg._aisensy_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "aisensy_api_key is required when no key is stored yet. "
                "Omit the field only to keep an existing key when updating number or project id."
            ),
        )
    if body.enable_aisensy_provider:
        cfg.whatsapp_provider = "aisensy"

    await db.commit()
    await db.refresh(cfg)

    data = PortalAisensyConfigUpdateResponse(
        company_id=cfg.company_id,
        whatsapp_provider=cfg.whatsapp_provider,
        aisensy_whatsapp_number=cfg.aisensy_whatsapp_number,
        aisensy_project_id=cfg.aisensy_project_id,
        has_aisensy_api_key=bool(cfg.aisensy_api_key),
    )
    return APIResponse(success=True, data=data, message="AiSensy configuration saved.")


@router.post(
    "/admin/companies/{company_id}/meta-whatsapp",
    response_model=APIResponse[PortalMetaWhatsappConfigUpdateResponse],
    summary="Configure Meta WhatsApp Cloud API for a company (admin)",
)
async def portal_admin_configure_meta_whatsapp(
    company_id: uuid.UUID,
    body: PortalMetaWhatsappConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_portal_admin),
) -> Any:
    """
    Store per-company Meta Cloud API credentials (Graph token, phone_number_id).

    Inbound webhooks route by ``metadata.phone_number_id`` to this tenant.
    """
    cfg = await _get_company_config_or_404(db, company_id)
    config_repo = CompanyConfigRepository(db)
    phone_id = body.meta_phone_number_id.strip()
    existing = await config_repo.get_by_meta_phone_number_id(phone_id)
    if existing is not None and str(existing.company_id) != str(company_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Meta phone_number_id is already assigned to another company.",
        )

    cfg.meta_phone_number_id = phone_id

    waba_in = (body.meta_waba_id or "").strip()
    if waba_in:
        cfg.meta_waba_id = waba_in

    token_in = (body.meta_graph_access_token or "").strip()
    if token_in:
        cfg.meta_graph_access_token = token_in
    elif not cfg._meta_graph_access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "meta_graph_access_token is required when no token is stored yet."
            ),
        )

    secret_in = (body.meta_app_secret or "").strip()
    if secret_in:
        cfg.meta_app_secret = secret_in

    verify_in = (body.meta_webhook_verify_token or "").strip()
    if verify_in:
        cfg.meta_webhook_verify_token = verify_in
    elif not cfg._meta_webhook_verify_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "meta_webhook_verify_token is required when no verify token is stored yet "
                "(Meta GET webhook check)."
            ),
        )

    if body.enable_meta_provider:
        cfg.whatsapp_provider = "meta"

    await db.commit()
    await db.refresh(cfg)

    data = PortalMetaWhatsappConfigUpdateResponse(
        company_id=cfg.company_id,
        whatsapp_provider=cfg.whatsapp_provider,
        meta_phone_number_id=cfg.meta_phone_number_id,
        meta_waba_id=getattr(cfg, "meta_waba_id", None),
        has_meta_graph_token=bool(cfg.meta_graph_access_token),
        has_meta_app_secret=bool(cfg.meta_app_secret),
        has_meta_webhook_verify_token=bool(cfg.meta_webhook_verify_token),
    )
    return APIResponse(success=True, data=data, message="Meta WhatsApp configuration saved.")
