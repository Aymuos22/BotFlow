"""
Send WhatsApp messages using the company's active provider (Twilio, AiSensy, Meta Cloud API).
"""
import logging

from app.core.config import get_settings
from app.integrations.aisensy.client import AisensyClient
from app.integrations.meta_whatsapp.client import MetaWhatsAppClient
from app.integrations.twilio.client import TwilioClient
from app.models.company_config import CompanyConfig

logger = logging.getLogger(__name__)


def company_can_send_whatsapp(config: CompanyConfig) -> bool:
    """True when outbound WhatsApp can be attempted for this company."""
    provider = (config.whatsapp_provider or "twilio").strip().lower()
    if provider == "aisensy":
        return bool(
            config.aisensy_api_key and (config.aisensy_project_id or "").strip()
        )
    if provider == "meta":
        return bool(
            config.meta_graph_access_token
            and (config.meta_phone_number_id or "").strip()
        )
    return bool(
        config.twilio_account_sid
        and config.twilio_auth_token
        and config.twilio_whatsapp_number
    )


async def send_company_whatsapp_text(
    *,
    config: CompanyConfig,
    to_number: str,
    text: str,
) -> None:
    """
    Deliver ``text`` to ``to_number`` using per-company credentials.

    Raises:
        ExternalServiceError: When the downstream provider rejects the request.
    """
    provider = (config.whatsapp_provider or "twilio").strip().lower()
    if provider == "aisensy":
        s = get_settings()
        key = config.aisensy_api_key
        project_id = (config.aisensy_project_id or "").strip()
        if not key or not project_id:
            raise RuntimeError(
                "AiSensy API key and project id must be configured for this company."
            )
        client = AisensyClient(
            api_key=key,
            project_id=project_id,
            base_url=s.aisensy_api_base_url,
            send_path=s.aisensy_send_text_path,
            timeout=s.aisensy_timeout_seconds,
        )
        await client.send_text(to_number=to_number, text=text)
        return

    if provider == "meta":
        s = get_settings()
        token = config.meta_graph_access_token
        phone_id = (config.meta_phone_number_id or "").strip()
        if not token or not phone_id:
            raise RuntimeError(
                "Meta Graph access token and phone_number_id must be configured."
            )
        client = MetaWhatsAppClient(
            access_token=token,
            phone_number_id=phone_id,
            graph_base_url=s.meta_graph_api_base_url,
            graph_version=s.meta_graph_api_version,
            timeout=s.meta_webhook_timeout_seconds,
        )
        await client.send_text(to_number=to_number, text=text)
        return

    account_sid = (config.twilio_account_sid or "").strip()
    token = config.twilio_auth_token
    from_num = (config.twilio_whatsapp_number or "").strip()
    if not account_sid or not token or not from_num:
        raise RuntimeError(
            "Twilio credentials are incomplete for this company "
            "(account_sid, auth_token, whatsapp number)."
        )
    s = get_settings()
    twilio = TwilioClient(
        account_sid=account_sid,
        auth_token=token,
        from_number=from_num,
        timeout=s.twilio_timeout_seconds,
    )
    await twilio.send_text(to_number=to_number, text=text)


async def send_company_whatsapp_image(
    *,
    config: CompanyConfig,
    to_number: str,
    image_url: str,
    caption: str | None = None,
) -> None:
    """
    Deliver an image to ``to_number`` using per-company credentials.

    Raises when the active provider rejects media sends. Callers can then
    fall back to a plain image URL message.
    """
    provider = (config.whatsapp_provider or "twilio").strip().lower()
    if provider == "aisensy":
        s = get_settings()
        key = config.aisensy_api_key
        project_id = (config.aisensy_project_id or "").strip()
        if not key or not project_id:
            raise RuntimeError(
                "AiSensy API key and project id must be configured for this company."
            )
        client = AisensyClient(
            api_key=key,
            project_id=project_id,
            base_url=s.aisensy_api_base_url,
            send_path=s.aisensy_send_text_path,
            timeout=s.aisensy_timeout_seconds,
        )
        await client.send_image(to_number=to_number, image_url=image_url, caption=caption)
        return

    if provider == "meta":
        s = get_settings()
        token = config.meta_graph_access_token
        phone_id = (config.meta_phone_number_id or "").strip()
        if not token or not phone_id:
            raise RuntimeError(
                "Meta Graph access token and phone_number_id must be configured."
            )
        client = MetaWhatsAppClient(
            access_token=token,
            phone_number_id=phone_id,
            graph_base_url=s.meta_graph_api_base_url,
            graph_version=s.meta_graph_api_version,
            timeout=s.meta_webhook_timeout_seconds,
        )
        await client.send_image(to_number=to_number, image_url=image_url, caption=caption)
        return

    account_sid = (config.twilio_account_sid or "").strip()
    token = config.twilio_auth_token
    from_num = (config.twilio_whatsapp_number or "").strip()
    if not account_sid or not token or not from_num:
        raise RuntimeError(
            "Twilio credentials are incomplete for this company "
            "(account_sid, auth_token, whatsapp number)."
        )
    s = get_settings()
    twilio = TwilioClient(
        account_sid=account_sid,
        auth_token=token,
        from_number=from_num,
        timeout=s.twilio_timeout_seconds,
    )
    await twilio.send_image(to_number=to_number, image_url=image_url, caption=caption)


async def send_company_whatsapp_text_best_effort(
    *,
    config: CompanyConfig,
    to_number: str,
    text: str,
    log_context: dict,
) -> None:
    """Same as ``send_company_whatsapp_text`` but logs failures instead of raising."""
    try:
        await send_company_whatsapp_text(
            config=config, to_number=to_number, text=text
        )
    except Exception:
        logger.exception(
            "WhatsApp outbound failed",
            extra=log_context,
        )
