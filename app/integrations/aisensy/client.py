"""
AiSensy Project API client — outbound WhatsApp text.

The exact HTTP path and JSON body depend on the AiSensy Project API version
documented in their Stoplight workspace. Use AISENSY_API_BASE_URL and
AISENSY_SEND_TEXT_PATH to align with your account.

This client sends a compact JSON envelope that matches common Project API
examples (project id + destination + message text). If AiSensy returns 4xx,
adjust env vars or contact AiSensy support with the response body.
"""
import logging
import re
from typing import Any, Dict
from urllib.parse import urljoin

import httpx

from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class AisensyClient:
    """
    Async HTTP client for sending WhatsApp session text via AiSensy.

    Args:
        api_key:      Project API key (``Authorization: Bearer …``).
        project_id:   AiSensy project id from the dashboard.
        base_url:     API host, e.g. ``https://api.aisensy.com``.
        send_path:    Path segment for send-text, e.g. ``/project-apis/v1/...``.
        timeout:      HTTP timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        project_id: str,
        base_url: str,
        send_path: str,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.project_id = project_id
        self.timeout = timeout
        root = base_url.rstrip("/") + "/"
        path = send_path if send_path.startswith("/") else f"/{send_path}"
        self._url = urljoin(root, path.lstrip("/"))

    def _raise_for_status(self, response: httpx.Response, operation: str) -> None:
        if response.is_error:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise ExternalServiceError(
                service="AiSensy",
                message=f"{operation} failed (HTTP {response.status_code}): {detail}",
            )

    async def send_text(self, to_number: str, text: str) -> Dict[str, Any]:
        """
        Send a WhatsApp text message to a customer (session / service window).

        ``to_number`` may be ``+E.164``, ``whatsapp:+E.164``, or digits-only.
        """
        dest_digits = _digits_only(to_number)
        if not dest_digits:
            raise ExternalServiceError(
                service="AiSensy",
                message="send_text requires a non-empty destination phone number.",
            )

        payload = {
            "projectId": self.project_id,
            "phoneNumber": dest_digits,
            "message": text,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._url,
                headers=headers,
                json=payload,
            )

        self._raise_for_status(response, "send_text")
        logger.info(
            "AiSensy message sent",
            extra={"to": dest_digits, "url": self._url},
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
        """
        Best-effort AiSensy image send using the configured Project API path.

        AiSensy account/API variants differ here, so callers should catch
        provider errors and fall back to sending the public image link as text.
        """
        dest_digits = _digits_only(to_number)
        if not dest_digits:
            raise ExternalServiceError(
                service="AiSensy",
                message="send_image requires a non-empty destination phone number.",
            )

        payload = {
            "projectId": self.project_id,
            "phoneNumber": dest_digits,
            "type": "image",
            "mediaUrl": image_url,
            "imageUrl": image_url,
        }
        if caption:
            payload["caption"] = caption
            payload["message"] = caption

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._url,
                headers=headers,
                json=payload,
            )

        self._raise_for_status(response, "send_image")
        logger.info(
            "AiSensy image message sent",
            extra={"to": dest_digits, "url": self._url},
        )
        try:
            return response.json()
        except Exception:
            return {}


def _digits_only(number: str) -> str:
    s = number.strip()
    if s.startswith("whatsapp:"):
        s = s[len("whatsapp:") :]
    s = s.split("@")[0]
    return re.sub(r"\D", "", s)
