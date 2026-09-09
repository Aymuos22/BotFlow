"""
Webhook endpoints for WhatsApp (Twilio, AiSensy, Meta Cloud API).

Twilio – POST /api/v1/webhooks/twilio/messages
AiSensy – POST /api/v1/webhooks/aisensy/messages
Meta – GET/POST /api/v1/webhooks/meta/whatsapp

Design rules
------------
1. **Always return 200** – non-200 causes the provider to retry indefinitely.
   All internal errors are caught and logged; only an acknowledgement is
   returned.

2. **Idempotency** – Twilio ``MessageSid`` is stored in ``Message.external_message_id``
   so duplicate deliveries are silently ignored.

3. **Conversation mode** – if ``current_mode == "agent"`` the message is
   stored but RAG does NOT run and no auto-reply is sent.

4. **Human-request detection** – if the message contains a recognised
   human-request phrase, a Handoff is created and an acknowledgement is sent;
   RAG is NOT run.

5. **Low-confidence escalation** – if RAG returns a score below the configured
   threshold AND ``handoff_on_low_confidence`` is enabled, a Handoff is
   created instead of the fallback message.

6. **Media** – Twilio ``NumMedia > 0`` messages without text are currently
   acknowledged but not replied to (text-only support).
"""
import asyncio
import hashlib
import hmac as _hmac
import json
import logging
import re
from collections import deque
from datetime import datetime, timezone
from typing import Awaitable, Callable, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.embeddings.client import get_embedding_client
from app.integrations.llm.client import LLMClientProtocol, get_llm_client
from app.integrations.aisensy.client import AisensyClient
from app.integrations.aisensy.inbound import iter_aisensy_inbound_events
from app.integrations.meta_whatsapp.client import MetaWhatsAppClient
from app.integrations.meta_whatsapp.inbound import (
    extract_phone_number_id_from_meta_payload,
    iter_meta_inbound_events,
)
from app.integrations.meta_whatsapp.signature import is_valid_meta_webhook_body
from app.integrations.twilio.client import TwilioClient
from app.integrations.twilio.signature import is_valid_twilio_request
from app.integrations.weaviate.client import WeaviateClient, get_weaviate_client
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.handoff_repository import HandoffRepository
from app.repositories.message_repository import MessageRepository
from app.services.conversation_service import ConversationService
from app.services.fallback_service import FallbackService
from app.services.handoff_service import HandoffService
from app.services.language_service import (
    detect_language,
    normalize_query,
    resolve_reply_language,
)
from app.services.lead_classification_service import run_lead_warmth_after_inbound
from app.services.audio_transcription_service import (
    download_meta_audio,
    download_twilio_audio,
    is_audio_content_type,
    transcribe_audio,
)
from app.services.rag_service import RAGService
from app.services.whatsapp_campaign_service import is_opt_out_text, WhatsAppCampaignService
from app.services.whatsapp_outbound import send_company_whatsapp_image
from app.utils.bot_detection import block_conversation, is_bot_flood
from app.utils.handoff_keywords import get_handoff_acknowledgement, is_human_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

# Detects when a customer explicitly asks to see images / photos.
_IMAGE_REQUEST_RE = re.compile(
    r"\b(image|images|photo|photos|pic\b|pics|picture|pictures|"
    r"show\s+me|dikhao|dikha|dekh\b|bhejo|dikh)\b|"
    r"(तस्वीर|फोटो|दिखाओ)",
    re.IGNORECASE,
)


def _customer_asks_for_image(query: str) -> bool:
    """True when the customer explicitly requests product images or photos."""
    return bool(_IMAGE_REQUEST_RE.search((query or "").strip()))


def _filter_new_products_for_images(
    recommended_products: List[dict],
    prior_msgs: List,
) -> List[dict]:
    """
    Return only products whose names haven't appeared in prior bot messages.

    Products already introduced earlier in the conversation don't need their
    image resent — that would be repetitive and spam-like for the customer.
    """
    if not recommended_products:
        return []

    prior_bot_text = " ".join(
        (getattr(m, "message_text", None) or "").lower()
        for m in (prior_msgs or [])
        if getattr(m, "sender_type", "") == "bot"
    )

    if not prior_bot_text.strip():
        # No prior bot messages → every product is being introduced for the first time
        return recommended_products

    new_products = []
    for item in recommended_products:
        name = (item.get("name") or "").strip().lower()
        if not name or name not in prior_bot_text:
            new_products.append(item)
    return new_products


# TwiML empty response — tells Twilio we handled the message (no reply via TwiML).
_TWIML_ACK = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'

# AiSensy expects a quick JSON acknowledgement (always HTTP 200).
_AISENSY_ACK = {"ok": True}

# Meta webhook POST acknowledgement (always HTTP 200 for delivery success).
_META_ACK = {"ok": True}


def _fire_and_forget(
    coro: Awaitable[object],
    *,
    operation: str,
    context: Optional[dict] = None,
) -> None:
    """
    Run a best-effort background coroutine without blocking the reply path.
    """
    task = asyncio.create_task(coro)

    def _done(t: asyncio.Task[object]) -> None:
        try:
            t.result()
        except Exception as exc:
            logger.warning(
                "%s failed (background); continuing",
                operation,
                extra={**(context or {}), "error": str(exc)},
            )

    task.add_done_callback(_done)


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


def _build_conv_service(db: AsyncSession) -> ConversationService:
    return ConversationService(
        conversation_repo=ConversationRepository(db),
        message_repo=MessageRepository(db),
    )


def _build_handoff_service(db: AsyncSession) -> HandoffService:
    return HandoffService(
        handoff_repo=HandoffRepository(db),
        conversation_repo=ConversationRepository(db),
        message_repo=MessageRepository(db),
        company_config_repo=CompanyConfigRepository(db),
        company_repo=CompanyRepository(db),
    )


async def _send_recommended_product_images(
    *,
    config,
    customer_phone: str,
    recommended_products: object,
    send_reply: Callable[[str], Awaitable[None]],
    customer_query: str = "",
    prior_msgs: Optional[List] = None,
) -> None:
    if config is None or not isinstance(recommended_products, list):
        return

    if _customer_asks_for_image(customer_query):
        products_to_send = recommended_products
    else:
        products_to_send = _filter_new_products_for_images(
            recommended_products, prior_msgs or []
        )

    if not products_to_send:
        return

    seen_urls: set[str] = set()
    for item in products_to_send:
        if not isinstance(item, dict):
            continue
        image_url = str(item.get("image_url") or "").strip()
        if not image_url or image_url in seen_urls:
            continue
        seen_urls.add(image_url)
        name = str(item.get("name") or item.get("image_alt") or "Product image").strip()
        caption = name[:1024]
        try:
            await send_company_whatsapp_image(
                config=config,
                to_number=customer_phone,
                image_url=image_url,
                caption=caption,
            )
        except Exception as exc:
            logger.warning(
                "Product image media send failed; falling back to image URL text",
                extra={
                    "company_id": str(getattr(config, "company_id", "")),
                    "to": customer_phone,
                    "image_url": image_url,
                    "error": str(exc),
                },
            )
            try:
                await send_reply(f"{name}: {image_url}")
            except Exception as fallback_exc:
                logger.error(
                    "Product image URL fallback send failed",
                    extra={
                        "company_id": str(getattr(config, "company_id", "")),
                        "to": customer_phone,
                        "image_url": image_url,
                        "error": str(fallback_exc),
                    },
                )


def _is_low_confidence(top_score, threshold: float) -> bool:
    """Return True when top_score is None or below the threshold."""
    return top_score is None or float(top_score) < threshold


def _customer_handoff_reason(
    trigger: str,
    message_text: str,
    *,
    extra: str | None = None,
) -> str:
    """
    Handoff reason shown in the DB and in staff WhatsApp alerts.

    Includes a truncated one-line snapshot of what the customer wrote.
    """
    snippet = (message_text or "").strip()
    snippet = " ".join(snippet.split())
    if len(snippet) > 280:
        snippet = snippet[:277] + "..."
    parts = [trigger]
    if snippet:
        parts.append(f'customer: "{snippet}"')
    if extra:
        parts.append(extra)
    return " — ".join(parts)


async def _maybe_resume_bot_mode_if_inactive(
    *,
    db: AsyncSession,
    conversation,
    inactivity_minutes: int,
) -> bool:
    """
    If conversation is in agent mode but the human hasn't sent any messages
    recently, switch back to bot mode.
    """
    if getattr(conversation, "current_mode", None) != "agent":
        return False

    msg_repo = MessageRepository(db)
    recent = await msg_repo.list_recent_for_conversation(conversation.id, limit=30)
    last_agent_ts = None
    for m in reversed(recent or []):
        if getattr(m, "sender_type", None) == "agent":
            last_agent_ts = getattr(m, "created_at", None)
            break

    if last_agent_ts is None:
        conv_repo = ConversationRepository(db)
        await conv_repo.update(conversation, {"current_mode": "bot"})
        conversation.current_mode = "bot"
        return True

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    elapsed = (now - last_agent_ts).total_seconds() / 60.0
    if elapsed >= inactivity_minutes:
        conv_repo = ConversationRepository(db)
        await conv_repo.update(conversation, {"current_mode": "bot"})
        conversation.current_mode = "bot"
        logger.info(
            "Agent inactive; bot resumed",
            extra={
                "conversation_id": str(conversation.id),
                "inactive_minutes": round(elapsed, 2),
                "threshold_minutes": inactivity_minutes,
            },
        )
        return True

    return False


async def _process_inbound_message(
    *,
    company_id,
    customer_phone: str,
    message_text: str,
    external_message_id: Optional[str],
    db: AsyncSession,
    weaviate_client: WeaviateClient,
    llm_client: LLMClientProtocol,
    send_reply: Callable[[str], Awaitable[None]],
    background_tasks: Optional[BackgroundTasks] = None,
) -> None:
    """
    Shared processing core for inbound WhatsApp messages (all providers).

    Handles conversation management, deduplication, language detection,
    RAG retrieval, handoff creation, and reply delivery.
    """
    conv_svc = _build_conv_service(db)
    conv = await conv_svc.create_or_get_conversation(company_id, customer_phone)
    sticky_reply_lang = conv.detected_language

    if getattr(conv, "is_blocked", False):
        logger.info(
            "Inbound message from blocked sender ignored",
            extra={
                "conversation_id": str(conv.id),
                "company_id": str(company_id),
                "customer_phone": customer_phone,
                "block_reason": getattr(conv, "block_reason", None),
            },
        )
        return

    if getattr(conv, "opted_out", False):
        logger.info(
            "Inbound message from opted-out sender ignored",
            extra={
                "conversation_id": str(conv.id),
                "company_id": str(company_id),
                "customer_phone": customer_phone,
            },
        )
        return

    if external_message_id:
        msg_repo = MessageRepository(db)
        existing = await msg_repo.get_by_external_id(external_message_id)
        if existing is not None:
            logger.debug(
                "Duplicate message ignored",
                extra={"external_message_id": external_message_id},
            )
            return

    lang = detect_language(message_text)

    customer_msg = await conv_svc.append_message(
        conversation_id=conv.id,
        company_id=company_id,
        sender_type="customer",
        message_text=message_text,
        normalized_text=normalize_query(message_text, lang),
        language=lang,
        external_message_id=external_message_id,
    )

    s = get_settings()
    if s.bot_protection_enabled:
        _msg_repo_bot = MessageRepository(db)
        recent_customer_msgs = await _msg_repo_bot.list_recent_customer_messages(
            conv.id, limit=20
        )
        block_reason = is_bot_flood(
            recent_customer_msgs,
            window_seconds=s.bot_rate_window_seconds,
            max_messages=s.bot_max_messages_per_window,
            max_identical=s.bot_max_identical_messages,
            burst_count=s.bot_burst_count,
            burst_interval_seconds=s.bot_burst_interval_seconds,
        )
        if block_reason:
            await block_conversation(conv, block_reason, db)
            return

    if background_tasks is not None:
        background_tasks.add_task(
            run_lead_warmth_after_inbound, str(conv.id), str(company_id)
        )

    config_repo = CompanyConfigRepository(db)
    config = await config_repo.get_by_company(company_id)
    if is_opt_out_text(message_text):
        from app.utils.opt_out import opt_out_ack
        conv_repo = ConversationRepository(db)
        await conv_repo.update(conv, {
            "opted_out": True,
            "opted_out_at": datetime.now(timezone.utc),
        })
        if config:
            await WhatsAppCampaignService(db).suppress_phone(
                company_id,
                customer_phone,
                reason="opt_out",
                source="whatsapp",
            )
        ack = opt_out_ack(conv.detected_language)
        try:
            await send_reply(ack)
        except Exception as exc:
            logger.error("Failed to send opt-out acknowledgement", extra={"error": str(exc)})
        logger.info(
            "Customer opted out",
            extra={"conversation_id": str(conv.id), "customer_phone": customer_phone},
        )
        return
    supported = list((config.supported_languages or ["english"]) if config else ["english"])
    default_lang = (config.default_language or "english") if config else "english"
    reply_lang = resolve_reply_language(
        message_text,
        sticky_reply_lang,
        supported,
        default_lang,
    )
    await conv_svc.refresh_reply_language_after_customer_message(conv, message_text)

    inactivity_minutes = int(s.whatsapp_agent_inactivity_minutes or 15)
    if config and getattr(config, "whatsapp_agent_inactivity_minutes", None) is not None:
        try:
            inactivity_minutes = int(config.whatsapp_agent_inactivity_minutes)
        except Exception:
            pass

    if conv.current_mode == "agent":
        await _maybe_resume_bot_mode_if_inactive(
            db=db,
            conversation=conv,
            inactivity_minutes=inactivity_minutes,
        )
    if conv.current_mode == "agent":
        logger.info(
            "Conversation in agent mode; skipping RAG",
            extra={"conversation_id": str(conv.id)},
        )
        return

    handoff_config = (config.handoff_config_json or {}) if config else {}
    custom_keywords = handoff_config.get("human_request_keywords", [])

    if is_human_request(message_text, custom_keywords=custom_keywords):
        await _handle_handoff_and_reply(
            reason=_customer_handoff_reason("human_request", message_text),
            message_text=message_text,
            conv=conv,
            company_id=company_id,
            lang=reply_lang,
            handoff_config=handoff_config,
            db=db,
            send_reply=send_reply,
        )
        return

    s = get_settings()
    msg_repo_for_hist = MessageRepository(db)
    prior_limit = max(6, s.rag_conversation_turns + 2)
    prior_msgs = await msg_repo_for_hist.list_recent_for_conversation(
        conv.id, limit=prior_limit
    )
    if prior_msgs and prior_msgs[-1].id == customer_msg.id:
        prior_msgs = prior_msgs[:-1]

    rag_svc = _build_rag_service(db, weaviate_client, llm_client)
    rag_result = await rag_svc.process_query(
        company_id=company_id,
        query=message_text,
        conversation_id=conv.id,
        message_id=customer_msg.id,
        conversation_messages=prior_msgs,
        conversation_reply_language=sticky_reply_lang,
    )

    answer = rag_result["answer"]
    response_type = rag_result["response_type"]
    top_score = rag_result.get("top_score")

    if rag_result.get("fallback_triggered"):
        handoff_on_low_conf = handoff_config.get("handoff_on_low_confidence", False)
        low_conf_threshold = handoff_config.get("low_confidence_handoff_threshold", 0.2)
        if handoff_on_low_conf and _is_low_confidence(top_score, low_conf_threshold):
            await _handle_handoff_and_reply(
                reason=_customer_handoff_reason(
                    "low_confidence",
                    message_text,
                    extra=f"score={top_score}",
                ),
                message_text=message_text,
                conv=conv,
                company_id=company_id,
                lang=reply_lang,
                handoff_config=handoff_config,
                db=db,
                send_reply=send_reply,
            )
            return

    append_task = asyncio.create_task(
        conv_svc.append_message(
            conversation_id=conv.id,
            company_id=company_id,
            sender_type="bot",
            message_text=answer,
            language=rag_result.get("language"),
            response_type=response_type,
        )
    )
    send_task = asyncio.create_task(send_reply(answer))

    send_exc: Exception | None = None
    try:
        await send_task
    except Exception as exc:
        send_exc = exc
        logger.error(
            "Failed to send reply",
            extra={"company_id": str(company_id), "error": str(exc)},
        )

    try:
        await append_task
    except Exception as exc:
        logger.error(
            "Failed to persist bot message",
            extra={"company_id": str(company_id), "error": str(exc)},
        )
        if send_exc is None:
            raise

    if send_exc is None:
        await _send_recommended_product_images(
            config=config,
            customer_phone=customer_phone,
            recommended_products=rag_result.get("recommended_products"),
            send_reply=send_reply,
            customer_query=message_text,
            prior_msgs=prior_msgs,
        )


async def _handle_handoff_and_reply(
    *,
    reason: str,
    message_text: str,
    conv,
    company_id,
    lang: str,
    handoff_config: dict,
    db: AsyncSession,
    send_reply: Callable[[str], Awaitable[None]],
) -> None:
    """Create a handoff and send an acknowledgement via the provider's send_reply."""
    handoff_svc = _build_handoff_service(db)
    try:
        await handoff_svc.request_handoff(
            company_id=company_id,
            conversation=conv,
            reason=reason,
            requested_by="customer",
        )
    except Exception as exc:
        logger.error("Failed to create handoff", extra={"error": str(exc)})

    ack_text = get_handoff_acknowledgement(handoff_config, lang)
    try:
        await send_reply(ack_text)
    except Exception as exc:
        logger.error(
            "Failed to send handoff acknowledgement",
            extra={"error": str(exc)},
        )


@router.post(
    "/twilio/messages",
    summary="Receive Twilio WhatsApp webhook events",
)
async def receive_twilio_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    MessageSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(default=""),
    NumMedia: int = Form(default=0),
    x_twilio_signature: str | None = Header(
        default=None, alias="X-Twilio-Signature"
    ),
    db: AsyncSession = Depends(get_db),
    weaviate_client: WeaviateClient = Depends(get_weaviate_client),
    llm_client: LLMClientProtocol = Depends(get_llm_client),
) -> Response:
    """
    Handle inbound WhatsApp messages delivered by Twilio.

    Twilio posts ``application/x-www-form-urlencoded`` to this URL when a
    customer sends a WhatsApp message to your Twilio number.

    Response is an empty TwiML ``<Response/>`` (HTTP 200) so Twilio does not
    retry.  The actual reply is sent asynchronously via the Twilio Messages API
    by ``TwilioClient.send_text``.

    Routing:
        ``To`` (Twilio sender number) → ``CompanyConfig.twilio_whatsapp_number``
        → company_id.

    Media messages (NumMedia > 0) are acknowledged but not replied to
    (text-only bot support).
    """
    try:
        s = get_settings()
        form = await request.form()
        if s.twilio_validate_signature:
            to_wa = To if To.startswith("whatsapp:") else f"whatsapp:{To}"
            config_repo = CompanyConfigRepository(db)
            cfg = await config_repo.get_by_twilio_number(to_wa)
            token = cfg.twilio_auth_token if cfg else None
            if not token:
                raise RuntimeError(
                    f"No per-company Twilio auth token configured for {to_wa!r}; "
                    "save credentials via the portal before enabling signature validation."
                )

            params = {str(k): str(v) for k, v in form.items()}

            proto = request.headers.get("x-forwarded-proto") or request.url.scheme
            host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
            url = f"{proto}://{host}{request.url.path}"
            if request.url.query:
                url = f"{url}?{request.url.query}"

            if not is_valid_twilio_request(
                url=url,
                params=params,
                auth_token=token,
                provided_signature=x_twilio_signature,
            ):
                logger.warning(
                    "Invalid Twilio signature; webhook ignored",
                    extra={"to": to_wa},
                )
                return Response(content=_TWIML_ACK, media_type="application/xml")

        await _handle_twilio_event(
            message_sid=MessageSid,
            from_number=From,
            to_number=To,
            body=Body,
            num_media=NumMedia,
            media_url=str(form.get("MediaUrl0") or ""),
            media_content_type=str(form.get("MediaContentType0") or ""),
            db=db,
            weaviate_client=weaviate_client,
            llm_client=llm_client,
            background_tasks=background_tasks,
        )
    except Exception as exc:
        logger.error(
            "Twilio webhook processing error (suppressed)",
            extra={
                "MessageSid": MessageSid,
                "From": From,
                "To": To,
                "error": str(exc)},
        )

    return Response(content=_TWIML_ACK, media_type="application/xml")


async def _handle_twilio_event(
    *,
    message_sid: str,
    from_number: str,
    to_number: str,
    body: str,
    num_media: int,
    media_url: str,
    media_content_type: str,
    db: AsyncSession,
    weaviate_client: WeaviateClient,
    llm_client: LLMClientProtocol,
    background_tasks: Optional[BackgroundTasks] = None,
) -> None:
    """Core handler for a Twilio inbound message."""
    customer_phone = _twilio_number_to_e164(from_number)

    to_wa = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"

    config_repo = CompanyConfigRepository(db)
    cfg = await config_repo.get_by_twilio_number(to_wa)
    if cfg is None:
        logger.warning(
            "No company found for Twilio number",
            extra={"to": to_wa},
        )
        return

    company_id = cfg.company_id

    s = get_settings()
    account_sid = cfg.twilio_account_sid
    auth_token = cfg.twilio_auth_token
    if not account_sid or not auth_token:
        raise RuntimeError(
            f"Twilio credentials not configured for company {company_id}. "
            "Set Account SID and Auth Token via the portal."
        )

    from_wa = cfg.twilio_whatsapp_number
    if not from_wa:
        raise RuntimeError(
            f"No Twilio WhatsApp sender number configured for company {company_id}."
        )

    twilio_client = TwilioClient(
        account_sid=account_sid,
        auth_token=auth_token,
        from_number=from_wa,
        timeout=s.twilio_timeout_seconds,
    )
    twilio_typing_sent = False

    async def _twilio_send_reply(text: str) -> None:
        nonlocal twilio_typing_sent
        if not twilio_typing_sent:
            twilio_typing_sent = True
            _fire_and_forget(
                twilio_client.send_typing_indicator(message_sid),
                operation="Twilio typing indicator",
                context={
                    "company_id": str(company_id),
                    "message_sid": message_sid,
                },
            )
        await twilio_client.send_text(to_number=customer_phone, text=text)

    message_text = body.strip()
    if num_media > 0 and not message_text:
        if (
            not get_settings().whatsapp_audio_transcription_enabled
            or not media_url
            or not is_audio_content_type(media_content_type)
        ):
            logger.info(
                "Twilio non-audio/media-only message ignored",
                extra={
                    "MessageSid": message_sid,
                    "NumMedia": num_media,
                    "content_type": media_content_type,
                },
            )
            return
        try:
            audio = await download_twilio_audio(
                media_url=media_url,
                content_type=media_content_type,
                account_sid=account_sid,
                auth_token=auth_token,
                timeout_seconds=s.twilio_timeout_seconds,
            )
            message_text = await transcribe_audio(audio)
        except Exception as exc:
            logger.error(
                "Twilio audio transcription failed",
                extra={"MessageSid": message_sid, "error": str(exc)},
            )
            await _twilio_send_reply("Sorry, I could not understand this audio. Please send it again or type your message.")
            return

    await _process_inbound_message(
        company_id=company_id,
        customer_phone=customer_phone,
        message_text=message_text,
        external_message_id=message_sid,
        db=db,
        weaviate_client=weaviate_client,
        llm_client=llm_client,
        send_reply=_twilio_send_reply,
        background_tasks=background_tasks,
    )


@router.post(
    "/aisensy/messages",
    summary="Receive AiSensy Project API webhook events (JSON)",
)
async def receive_aisensy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    weaviate_client: WeaviateClient = Depends(get_weaviate_client),
    llm_client: LLMClientProtocol = Depends(get_llm_client),
) -> JSONResponse:
    """
    Inbound messages from AiSensy (Project webhook).

    Configure the AiSensy dashboard to POST JSON to this URL. The payload shape
    can follow Meta WABA webhooks or a flatter Project API object; see
    ``iter_aisensy_inbound_events`` for supported fields.

    Always returns HTTP 200 with a small JSON body so AiSensy does not retry
    aggressively; reply delivery uses ``AisensyClient`` + Project API.
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(content=_AISENSY_ACK)

    try:
        s = get_settings()
        config_repo = CompanyConfigRepository(db)
        for event in iter_aisensy_inbound_events(payload):
            if not event.text.strip():
                logger.info(
                    "AiSensy non-text or empty message ignored",
                    extra={"external_id": event.external_message_id},
                )
                continue

            routing = event.business_routing_key
            if not routing:
                logger.warning(
                    "AiSensy webhook missing business phone; cannot route tenant",
                    extra={"external_id": event.external_message_id},
                )
                continue

            cfg = await config_repo.get_by_aisensy_number(routing)
            if cfg is None:
                logger.warning(
                    "No company found for AiSensy business number",
                    extra={"to": routing},
                )
                continue

            if (cfg.whatsapp_provider or "twilio").lower() != "aisensy":
                logger.warning(
                    "AiSensy webhook ignored: company not on aisensy provider",
                    extra={
                        "company_id": str(cfg.company_id),
                        "whatsapp_provider": cfg.whatsapp_provider,
                    },
                )
                continue

            company_id = cfg.company_id
            key = cfg.aisensy_api_key
            project_id = (cfg.aisensy_project_id or "").strip()
            if not key or not project_id:
                logger.error(
                    "AiSensy credentials missing for company",
                    extra={"company_id": str(company_id)},
                )
                continue

            client = AisensyClient(
                api_key=key,
                project_id=project_id,
                base_url=s.aisensy_api_base_url,
                send_path=s.aisensy_send_text_path,
                timeout=s.aisensy_timeout_seconds,
            )

            def _aisensy_reply_factory(
                c: AisensyClient, to_num: str
            ) -> Callable[[str], Awaitable[None]]:
                async def _send(text: str) -> None:
                    await c.send_text(to_number=to_num, text=text)

                return _send

            await _process_inbound_message(
                company_id=company_id,
                customer_phone=event.customer_phone_e164,
                message_text=event.text,
                external_message_id=event.external_message_id,
                db=db,
                weaviate_client=weaviate_client,
                llm_client=llm_client,
                send_reply=_aisensy_reply_factory(
                    client, event.customer_phone_e164
                ),
                background_tasks=background_tasks,
            )
    except Exception as exc:
        logger.error(
            "AiSensy webhook processing error (suppressed)",
            extra={"error": str(exc)},
        )

    return JSONResponse(content=_AISENSY_ACK)


@router.get(
    "/meta/whatsapp",
    summary="Meta WhatsApp Cloud API webhook verification (GET)",
)
async def verify_meta_whatsapp_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if (hub_mode or "").strip() != "subscribe" or not hub_challenge:
        return Response(status_code=403)
    token_in = (hub_verify_token or "").strip()
    if not token_in:
        return Response(status_code=403)
    s = get_settings()
    if s.meta_webhook_verify_token and token_in == s.meta_webhook_verify_token.strip():
        return PlainTextResponse(content=hub_challenge)
    config_repo = CompanyConfigRepository(db)
    for cfg in await config_repo.list_configs_with_meta_phone_number():
        stored = (cfg.meta_webhook_verify_token or "").strip()
        if stored and token_in == stored:
            return PlainTextResponse(content=hub_challenge)
    logger.warning("Meta webhook verify_token did not match any company or env")
    return Response(status_code=403)


@router.post(
    "/meta/whatsapp",
    summary="Receive Meta WhatsApp Cloud API webhook events (JSON)",
)
async def receive_meta_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(
        default=None, alias="X-Hub-Signature-256"
    ),
    db: AsyncSession = Depends(get_db),
    weaviate_client: WeaviateClient = Depends(get_weaviate_client),
    llm_client: LLMClientProtocol = Depends(get_llm_client),
) -> JSONResponse:
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        logger.warning(
            "Meta webhook JSON parse failed; ack only",
            extra={"error": str(exc), "body_len": len(raw)},
        )
        return JSONResponse(content=_META_ACK)

    if not isinstance(payload, dict):
        logger.warning("Meta webhook body is not a JSON object; ack only")
        return JSONResponse(content=_META_ACK)

    config_repo = CompanyConfigRepository(db)
    pid = extract_phone_number_id_from_meta_payload(payload)
    cfg_for_sig = await config_repo.get_by_meta_phone_number_id(pid) if pid else None
    app_secret = (cfg_for_sig.meta_app_secret or "").strip() if cfg_for_sig else ""
    sig = (x_hub_signature_256 or "").strip()
    if sig and app_secret:
        if not is_valid_meta_webhook_body(
            app_secret=app_secret,
            raw_body=raw,
            signature_header=sig,
        ):
            logger.warning(
                "Invalid Meta X-Hub-Signature-256; webhook rejected",
                extra={"phone_number_id": pid},
            )
            return JSONResponse(content={"ok": False}, status_code=403)
    elif sig and not app_secret:
        logger.warning(
            "Meta webhook signed but no app secret stored for phone_number_id",
            extra={"phone_number_id": pid},
        )

    try:
        s = get_settings()
        events = list(iter_meta_inbound_events(payload))
        logger.info(
            "Meta webhook POST",
            extra={
                "object": payload.get("object"),
                "phone_number_id_hint": pid,
                "inbound_events": len(events),
                "body_bytes": len(raw),
            },
        )
        if not events:
            # Log any status updates (sent/delivered/read/failed) for diagnostics
            try:
                for entry in payload.get("entry", []):
                    for change in entry.get("changes", []):
                        for status in change.get("value", {}).get("statuses", []):
                            logger.info(
                                "Meta webhook status update",
                                extra={
                                    "status": status.get("status"),
                                    "message_id": status.get("id"),
                                    "recipient": status.get("recipient_id"),
                                    "errors": status.get("errors"),
                                },
                            )
            except Exception:
                pass
            logger.warning(
                "Meta webhook: no message events parsed "
                "(expect object=whatsapp_business_account, field=messages, value.messages[])",
                extra={"object": payload.get("object")},
            )
        for event in events:
            cfg = await config_repo.get_by_meta_phone_number_id(event.phone_number_id)
            if cfg is None:
                logger.warning(
                    "No company for Meta phone_number_id",
                    extra={"phone_number_id": event.phone_number_id},
                )
                continue
            if (cfg.whatsapp_provider or "twilio").lower() != "meta":
                logger.warning(
                    "Meta webhook ignored: company not on meta provider",
                    extra={
                        "company_id": str(cfg.company_id),
                        "whatsapp_provider": cfg.whatsapp_provider,
                    },
                )
                continue
            token = cfg.meta_graph_access_token
            phone_id = (cfg.meta_phone_number_id or "").strip()
            if not token or not phone_id:
                logger.error(
                    "Meta Cloud API credentials missing for company",
                    extra={"company_id": str(cfg.company_id)},
                )
                continue
            client = MetaWhatsAppClient(
                access_token=token,
                phone_number_id=phone_id,
                graph_base_url=s.meta_graph_api_base_url,
                graph_version=s.meta_graph_api_version,
                timeout=s.meta_webhook_timeout_seconds,
            )

            def _meta_reply_factory(
                c: MetaWhatsAppClient,
                to_num: str,
                external_message_id: Optional[str],
            ) -> Callable[[str], Awaitable[None]]:
                typing_sent = False

                async def _send(text: str) -> None:
                    nonlocal typing_sent
                    if not typing_sent and external_message_id:
                        typing_sent = True
                        _fire_and_forget(
                            c.send_typing_indicator(external_message_id),
                            operation="Meta typing indicator",
                            context={
                                "company_id": str(cfg.company_id),
                                "phone_number_id": phone_id,
                                "external_message_id": external_message_id,
                            },
                        )
                    await c.send_text(to_number=to_num, text=text)

                return _send

            message_text = event.text.strip()
            if not message_text:
                if (
                    event.message_type != "audio"
                    or not event.media_id
                    or not s.whatsapp_audio_transcription_enabled
                ):
                    logger.info(
                        "Meta non-text message ignored",
                        extra={
                            "message_type": event.message_type,
                            "external_message_id": event.external_message_id,
                        },
                    )
                    continue
                try:
                    audio = await download_meta_audio(
                        media_id=event.media_id,
                        access_token=token,
                        graph_base_url=s.meta_graph_api_base_url,
                        graph_version=s.meta_graph_api_version,
                        timeout_seconds=s.meta_webhook_timeout_seconds,
                        content_type=event.media_mime_type,
                    )
                    message_text = await transcribe_audio(audio)
                except Exception as exc:
                    logger.error(
                        "Meta audio transcription failed",
                        extra={
                            "company_id": str(cfg.company_id),
                            "external_message_id": event.external_message_id,
                            "error": str(exc),
                        },
                    )
                    try:
                        await client.send_text(
                            to_number=event.customer_phone_e164,
                            text="Sorry, I could not understand this audio. Please send it again or type your message.",
                        )
                    except Exception as send_exc:
                        logger.error(
                            "Meta audio failure acknowledgement failed",
                            extra={"error": str(send_exc)},
                        )
                    continue

            await _process_inbound_message(
                company_id=cfg.company_id,
                customer_phone=event.customer_phone_e164,
                message_text=message_text,
                external_message_id=event.external_message_id,
                db=db,
                weaviate_client=weaviate_client,
                llm_client=llm_client,
                send_reply=_meta_reply_factory(
                    client, event.customer_phone_e164, event.external_message_id
                ),
                background_tasks=background_tasks,
            )
    except Exception as exc:
        logger.error(
            "Meta webhook processing error (suppressed)",
            extra={"error": str(exc)},
        )

    return JSONResponse(content=_META_ACK)


def _twilio_number_to_e164(number: str) -> str:
    """
    Convert a Twilio-formatted WhatsApp number to E.164.

    ``whatsapp:+911234567890`` → ``+911234567890``
    """
    if number.startswith("whatsapp:"):
        number = number[len("whatsapp:"):]
    if not number.startswith("+"):
        number = f"+{number}"
    return number


# ─────────────────────────────────────────────────────────────────────────────
# BOTFLOW post-call webhook
# POST /api/v1/webhooks/BOTFLOW/{company_id}
# ─────────────────────────────────────────────────────────────────────────────

# Bounded in-memory idempotency store: prevents duplicate sends when
# BOTFLOW retries a webhook that already received 200 from us.
_BOTFLOW_SEEN: deque[str] = deque(maxlen=1_000)
_BOTFLOW_SEEN_SET: set[str] = set()


def _BOTFLOW_mark_seen(call_id: str) -> bool:
    """Return True if call_id was already processed (duplicate). Otherwise register it."""
    if call_id in _BOTFLOW_SEEN_SET:
        return True
    if len(_BOTFLOW_SEEN) == _BOTFLOW_SEEN.maxlen:
        # deque is full — evict the oldest entry from the set too
        _BOTFLOW_SEEN_SET.discard(_BOTFLOW_SEEN[0])
    _BOTFLOW_SEEN.append(call_id)
    _BOTFLOW_SEEN_SET.add(call_id)
    return False


async def _process_BOTFLOW_event(
    company_id: UUID,
    call_id: str,
    data: dict,
    weaviate_client: WeaviateClient,
    llm_client: LLMClientProtocol,
) -> None:
    """
    Background task: look up the product in this company's Weaviate collection
    using RAG and send the result as a WhatsApp message to the caller.

    Runs after the endpoint has already returned 200 to BOTFLOW.
    """
    if _BOTFLOW_mark_seen(call_id):
        logger.info(
            "BOTFLOW duplicate call_id — skipped",
            extra={"call_id": call_id},
        )
        return

    entities = data.get("entities") or {}
    if entities.get("product_details_requested") != "yes":
        logger.info(
            "BOTFLOW event skipped — product_details_requested != yes",
            extra={"call_id": call_id, "entities": entities},
        )
        return

    phone_number = (data.get("phone_number") or "").strip()
    product_name = (entities.get("product_name") or "").strip()

    if not phone_number:
        logger.warning(
            "BOTFLOW webhook missing phone_number — cannot send WhatsApp",
            extra={"call_id": call_id, "company_id": str(company_id)},
        )
        return

    from app.core.database import AsyncSessionLocal
    from app.services.whatsapp_outbound import (
        company_can_send_whatsapp,
        send_company_whatsapp_text,
    )

    try:
        async with AsyncSessionLocal() as db:
            config = await CompanyConfigRepository(db).get_by_company(company_id)
            if not config:
                logger.warning(
                    "BOTFLOW: no CompanyConfig found",
                    extra={"company_id": str(company_id), "call_id": call_id},
                )
                return
            if not company_can_send_whatsapp(config):
                logger.warning(
                    "BOTFLOW: company WhatsApp not configured",
                    extra={"company_id": str(company_id), "call_id": call_id},
                )
                return

            # Build the RAG query from the product the caller asked about.
            # Fall back to the transcript excerpt when no product name was extracted.
            if product_name:
                query = product_name
            else:
                transcript = (data.get("transcript") or "").strip()
                query = transcript[:500] if transcript else "product details"

            rag_svc = _build_rag_service(db, weaviate_client, llm_client)
            rag_result = await rag_svc.process_query(
                company_id=company_id,
                query=query,
            )
            message = (rag_result.get("answer") or "").strip()
            if not message:
                logger.warning(
                    "BOTFLOW: RAG returned empty answer — WhatsApp not sent",
                    extra={"call_id": call_id, "query": query},
                )
                return

            await send_company_whatsapp_text(
                config=config,
                to_number=phone_number,
                text=message,
            )
            logger.info(
                "BOTFLOW WhatsApp sent",
                extra={
                    "call_id": call_id,
                    "company_id": str(company_id),
                    "to": phone_number,
                    "product": product_name or "(from transcript)",
                },
            )
    except Exception:
        logger.exception(
            "BOTFLOW background task failed",
            extra={"call_id": call_id, "company_id": str(company_id)},
        )


@router.post(
    "/BOTFLOW/{company_id}",
    status_code=200,
    summary="BOTFLOW post-call webhook",
    tags=["webhooks"],
)
async def BOTFLOW_webhook(
    company_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    weaviate_client: WeaviateClient = Depends(get_weaviate_client),
    llm_client: LLMClientProtocol = Depends(get_llm_client),
) -> dict:
    """
    Receive ``call_postprocessing`` events from BOTFLOW.

    Flow
    ----
    1. Verify ``X-Webhook-Signature: sha256=<hmac>`` using ``BOTFLOW_WEBHOOK_SECRET``.
    2. Return ``{"status": "accepted"}`` immediately (BOTFLOW expects < 10 s).
    3. Background task:
       a. Idempotency check on ``call_id``.
       b. Skip if ``entities.product_details_requested != "yes"``.
       c. RAG search using ``entities.product_name`` in this company's Weaviate collection.
       d. LLM composes a WhatsApp-friendly product detail message.
       e. Send to ``data.phone_number`` via the company's WhatsApp provider.

    Company isolation
    -----------------
    The ``{company_id}`` path parameter determines which tenant's config and
    Weaviate collection are used — no cross-tenant data access is possible.
    """
    body_bytes = await request.body()

    s = get_settings()
    secret = (s.botflow_webhook_secret or "").strip()
    if secret:
        sig_header = request.headers.get("x-webhook-signature", "")
        computed = "sha256=" + _hmac.new(
            secret.encode(), body_bytes, hashlib.sha256
        ).hexdigest()
        if not _hmac.compare_digest(sig_header, computed):
            logger.warning(
                "BOTFLOW invalid signature rejected",
                extra={"company_id": str(company_id)},
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("event")
    call_id = str(payload.get("call_id") or "")
    data: dict = payload.get("data") or {}

    if event != "call_postprocessing":
        return {"status": "ignored", "reason": f"unhandled event: {event}"}

    background_tasks.add_task(
        _process_BOTFLOW_event,
        company_id,
        call_id,
        data,
        weaviate_client,
        llm_client,
    )
    return {"status": "accepted"}
