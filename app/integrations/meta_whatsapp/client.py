"""Meta WhatsApp Cloud API — send text messages via Graph API."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict
from urllib.parse import quote

import httpx

from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


def _to_recipient_digits(to_number: str) -> str:
    s = (to_number or "").strip()
    if s.startswith("whatsapp:"):
        s = s[len("whatsapp:") :].strip()
    s = re.sub(r"\D", "", s.split("@")[0])
    if not s:
        raise ExternalServiceError(
            service="MetaWhatsApp",
            message="Empty or invalid destination phone for Cloud API send.",
        )
    return s


class MetaWhatsAppClient:
    """
    Async client for ``POST /vNN.N/{phone-number-id}/messages``.
    """

    def __init__(
        self,
        *,
        access_token: str,
        phone_number_id: str,
        graph_base_url: str,
        graph_version: str,
        timeout: int = 30,
    ) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id.strip()
        self.timeout = timeout
        base = graph_base_url.rstrip("/")
        ver = graph_version.strip().lstrip("/")
        pn_q = quote(self.phone_number_id, safe="")
        self._graph_root = f"{base}/{ver}"
        self._messages_url = f"{self._graph_root}/{pn_q}/messages"
        self._phone_node_url = f"{self._graph_root}/{pn_q}"

    def _raise_for_status(self, response: httpx.Response, operation: str) -> None:
        if response.is_error:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise ExternalServiceError(
                service="MetaWhatsApp",
                message=f"{operation} failed (HTTP {response.status_code}): {detail}",
            )

    async def send_text(self, to_number: str, text: str) -> Dict[str, Any]:
        to_digits = _to_recipient_digits(to_number)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_digits,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._messages_url,
                headers=headers,
                json=payload,
            )
        self._raise_for_status(response, "send_text")
        logger.info(
            "Meta WhatsApp message sent",
            extra={"to": to_digits, "url": self._messages_url},
        )
        try:
            return response.json()
        except Exception:
            return {}

    async def send_image(
        self,
        to_number: str,
        image_url: str,
        caption: str | None = None,
    ) -> Dict[str, Any]:
        to_digits = _to_recipient_digits(to_number)
        image: Dict[str, Any] = {"link": image_url}
        if caption:
            image["caption"] = caption[:1024]
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_digits,
            "type": "image",
            "image": image,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._messages_url,
                headers=headers,
                json=payload,
            )
        self._raise_for_status(response, "send_image")
        logger.info(
            "Meta WhatsApp image sent",
            extra={"to": to_digits, "url": self._messages_url},
        )
        try:
            return response.json()
        except Exception:
            return {}

    async def send_template(
        self,
        *,
        to_number: str,
        template_name: str,
        language_code: str,
        body_variables: list[str] | None = None,
        header_media_url: str | None = None,
    ) -> Dict[str, Any]:
        to_digits = _to_recipient_digits(to_number)
        components: list[Dict[str, Any]] = []
        if header_media_url:
            components.append(
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"link": header_media_url},
                        }
                    ],
                }
            )
        vars_clean = [str(v) for v in (body_variables or [])]
        if vars_clean:
            components.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": v} for v in vars_clean],
                }
            )
        template: Dict[str, Any] = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if components:
            template["components"] = components
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_digits,
            "type": "template",
            "template": template,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self._messages_url, headers=headers, json=payload)
        self._raise_for_status(response, "send_template")
        logger.info(
            "Meta WhatsApp template sent",
            extra={"to": to_digits, "template": template_name},
        )
        try:
            return response.json()
        except Exception:
            return {}

    async def list_message_templates(self, *, waba_id: str) -> list[Dict[str, Any]]:
        waba = (waba_id or "").strip()
        if not waba:
            return []
        url = f"{self._graph_root}/{quote(waba, safe='')}/message_templates"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"fields": "name,language,status,category,components", "limit": 100}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers, params=params)
        self._raise_for_status(response, "list_message_templates")
        try:
            data = response.json()
        except Exception:
            return []
        items = data.get("data")
        return items if isinstance(items, list) else []

    async def fetch_whatsapp_business_account_id(self) -> str | None:
        """
        Resolve WABA id from the configured Cloud API phone_number_id node.

        Required for Business Management APIs such as listing/creating templates.
        """
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"fields": "whatsapp_business_account"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                self._phone_node_url,
                headers=headers,
                params=params,
            )
        self._raise_for_status(response, "fetch_whatsapp_business_account_id")
        try:
            data = response.json()
        except Exception:
            return None
        waba = data.get("whatsapp_business_account")
        if isinstance(waba, dict):
            wid = waba.get("id")
            if isinstance(wid, str) and wid.strip():
                return wid.strip()
        return None

    async def create_message_template(
        self,
        *,
        waba_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        waba = (waba_id or "").strip()
        if not waba:
            raise ExternalServiceError(
                service="MetaWhatsApp",
                message="create_message_template failed: empty WhatsApp Business Account id.",
            )
        url = f"{self._graph_root}/{quote(waba, safe='')}/message_templates"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
        self._raise_for_status(response, "create_message_template")
        logger.info(
            "Meta WhatsApp template submitted",
            extra={"waba_id": waba, "template_name": payload.get("name")},
        )
        try:
            return response.json()
        except Exception:
            return {}

    async def subscribe_waba_to_app(self, *, waba_id: str) -> Dict[str, Any]:
        """
        Subscribe a WhatsApp Business Account to this Meta App so that webhook
        events (messages, statuses, etc.) are delivered to the registered
        callback URL.

        Graph API call::

            POST /{version}/{waba_id}/subscribed_apps
            Authorization: Bearer {access_token}

        Returns ``{"success": true}`` on success.
        Must be called once per WABA; safe to re-call (idempotent on Meta's side).
        """
        waba = (waba_id or "").strip()
        if not waba:
            raise ExternalServiceError(
                service="MetaWhatsApp",
                message="subscribe_waba_to_app failed: empty waba_id.",
            )
        url = f"{self._graph_root}/{quote(waba, safe='')}/subscribed_apps"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers)
        self._raise_for_status(response, "subscribe_waba_to_app")
        logger.info(
            "Meta WABA subscribed to app",
            extra={"waba_id": waba},
        )
        try:
            return response.json()
        except Exception:
            return {}

    async def send_typing_indicator(self, message_id: str) -> Dict[str, Any]:
        """
        Send WhatsApp Cloud API typing indicator using a message id context.
        """
        sid = (message_id or "").strip()
        if not sid:
            raise ExternalServiceError(
                service="MetaWhatsApp",
                message="send_typing_indicator failed: empty message_id.",
            )
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": sid,
            "typing_indicator": {"type": "text"},
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._messages_url,
                headers=headers,
                json=payload,
            )
        self._raise_for_status(response, "send_typing_indicator")
        logger.info(
            "Meta WhatsApp typing indicator sent",
            extra={"message_id": sid, "url": self._messages_url},
        )
        try:
            return response.json()
        except Exception:
            return {}
