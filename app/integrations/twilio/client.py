"""
Twilio WhatsApp integration client.

Wraps Twilio's REST Messages API for sending WhatsApp messages:
  - Async httpx with Basic Auth (AccountSid / AuthToken)
  - Consistent error handling → ExternalServiceError
  - Configurable timeout and sender number

Inbound messages arrive as form-encoded POST webhooks; this client
only handles the outbound (send) direction.

Credentials (Account SID, Auth Token, sender number) are stored per-company
in CompanyConfig — there is no global/env fallback.
"""
import logging
from typing import Any, Dict

import httpx

from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_TWILIO_MESSAGES_URL = (
    "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
)
_TWILIO_TYPING_INDICATOR_URL = "https://messaging.twilio.com/v2/Indicators/Typing.json"


class TwilioClient:
    """
    Async HTTP client for sending WhatsApp messages via Twilio.

    Designed to be mockable: ``send_text`` returns a plain ``dict``
    so tests can substitute AsyncMock instances without complex hierarchies.

    Args:
        account_sid:  Twilio Account SID (ACxxxxxxxx…).
        auth_token:   Twilio Auth Token.
        from_number:  Sender WhatsApp number in ``whatsapp:+<E.164>`` format,
                      e.g. ``whatsapp:+14155238886`` (Sandbox) or a verified
                      business number.
        timeout:      HTTP request timeout in seconds.
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        timeout: int = 30,
    ) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        # Normalise: ensure the number has the whatsapp: prefix.
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"
        self.from_number = from_number
        self.timeout = timeout
        self._messages_url = _TWILIO_MESSAGES_URL.format(account_sid=account_sid)

    def _raise_for_status(self, response: httpx.Response, operation: str) -> None:
        """Map non-2xx Twilio responses to ExternalServiceError."""
        if response.is_error:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise ExternalServiceError(
                service="Twilio",
                message=f"{operation} failed (HTTP {response.status_code}): {detail}",
            )

    async def send_text(
        self,
        to_number: str,
        text: str,
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp text message via Twilio.

        POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json

        Args:
            to_number:  Recipient phone number.  Accepted formats:
                          - ``whatsapp:+911234567890``  (already prefixed)
                          - ``+911234567890``           (E.164, prefix added automatically)
                          - ``911234567890@c.us``       (legacy ``@c.us`` id, converted automatically)
            text:       Message body.

        Returns:
            Twilio API response dict (contains ``sid``, ``status``, etc.).

        Raises:
            ExternalServiceError: On any non-2xx HTTP response.
        """
        to_wa = _normalise_to_whatsapp(to_number)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._messages_url,
                auth=(self.account_sid, self.auth_token),
                data={
                    "From": self.from_number,
                    "To": to_wa,
                    "Body": text,
                },
            )

        self._raise_for_status(response, "send_text")
        logger.info(
            "Twilio message sent",
            extra={"to": to_wa, "from": self.from_number},
        )
        return response.json()

    async def send_image(
        self,
        to_number: str,
        image_url: str,
        caption: str | None = None,
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp image message via Twilio using a public media URL.
        """
        to_wa = _normalise_to_whatsapp(to_number)
        payload = {
            "From": self.from_number,
            "To": to_wa,
            "MediaUrl": image_url,
        }
        if caption:
            payload["Body"] = caption

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._messages_url,
                auth=(self.account_sid, self.auth_token),
                data=payload,
            )

        self._raise_for_status(response, "send_image")
        logger.info(
            "Twilio image message sent",
            extra={"to": to_wa, "from": self.from_number},
        )
        return response.json()

    async def send_typing_indicator(self, message_id: str) -> Dict[str, Any]:
        """
        Send WhatsApp typing indicator using the inbound Twilio MessageSid.
        """
        sid = (message_id or "").strip()
        if not sid:
            raise ExternalServiceError(
                service="Twilio",
                message="send_typing_indicator failed: empty message_id.",
            )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                _TWILIO_TYPING_INDICATOR_URL,
                auth=(self.account_sid, self.auth_token),
                data={
                    "messageId": sid,
                    "channel": "whatsapp",
                },
            )

        self._raise_for_status(response, "send_typing_indicator")
        logger.info("Twilio typing indicator sent", extra={"message_id": sid})
        try:
            return response.json()
        except Exception:
            return {}


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _normalise_to_whatsapp(number: str) -> str:
    """
    Convert any WhatsApp number representation to ``whatsapp:+<E.164>``.

    Handles:
      - ``whatsapp:+911234567890``  → unchanged
      - ``+911234567890``           → ``whatsapp:+911234567890``
      - ``911234567890``            → ``whatsapp:+911234567890``
      - ``911234567890@c.us``       → ``whatsapp:+911234567890``
    """
    if number.startswith("whatsapp:"):
        return number
    # Strip ``@c.us`` suffix if present
    number = number.split("@")[0]
    # Ensure leading +
    if not number.startswith("+"):
        number = f"+{number}"
    return f"whatsapp:{number}"


