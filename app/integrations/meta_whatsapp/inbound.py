"""
Parse Meta WhatsApp Cloud API webhook JSON into simple inbound records.

See: https://developers.facebook.com/docs/graph-api/webhooks/getting-started
and WhatsApp ``messages`` field payloads.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetaInboundMessage:
    phone_number_id: str
    external_message_id: Optional[str]
    customer_wa_id: str
    text: str
    message_type: str = "text"
    media_id: Optional[str] = None
    media_mime_type: Optional[str] = None

    @property
    def customer_phone_e164(self) -> str:
        e = _customer_e164_from_wa_id(self.customer_wa_id)
        return e or f"+{self.customer_wa_id}"


def _digits_customer_id(wa_id: Optional[str]) -> Optional[str]:
    if wa_id is None:
        return None
    s = str(wa_id).strip()
    if not s:
        return None
    digits = re.sub(r"\D", "", s.split("@")[0])
    return digits or None


def _customer_e164_from_wa_id(wa_id: Optional[str]) -> Optional[str]:
    digits = _digits_customer_id(wa_id)
    if not digits:
        return None
    return f"+{digits}"


def _text_from_message(msg: dict) -> str:
    if not msg:
        return ""
    mtype = (msg.get("type") or "").lower()
    if mtype == "text":
        body = msg.get("text") or {}
        if isinstance(body, dict):
            return str(body.get("body") or "").strip()
    if isinstance(msg.get("text"), dict):
        return str(msg["text"].get("body") or "").strip()
    return ""


def _audio_from_message(msg: dict) -> tuple[Optional[str], Optional[str]]:
    if not msg:
        return None, None
    mtype = (msg.get("type") or "").lower()
    audio = msg.get("audio") if mtype == "audio" else None
    if not isinstance(audio, dict):
        return None, None
    media_id = str(audio.get("id") or "").strip() or None
    mime_type = str(audio.get("mime_type") or "").strip() or None
    return media_id, mime_type


def _events_from_payload(data: dict) -> List[MetaInboundMessage]:
    out: List[MetaInboundMessage] = []
    if (data.get("object") or "") != "whatsapp_business_account":
        return out
    for entry in data.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            if (change.get("field") or "") != "messages":
                continue
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            meta = value.get("metadata") or {}
            pid = meta.get("phone_number_id") if isinstance(meta, dict) else None
            if not pid:
                continue
            phone_number_id = str(pid).strip()
            for msg in value.get("messages") or []:
                if not isinstance(msg, dict):
                    continue
                ext_id = msg.get("id")
                from_raw = msg.get("from")
                cust = _customer_e164_from_wa_id(from_raw)
                txt = _text_from_message(msg)
                message_type = str(msg.get("type") or "").strip().lower() or "text"
                media_id, media_mime = _audio_from_message(msg)
                if not cust:
                    continue
                out.append(
                    MetaInboundMessage(
                        phone_number_id=phone_number_id,
                        external_message_id=str(ext_id) if ext_id else None,
                        customer_wa_id=str(from_raw).strip(),
                        text=txt,
                        message_type=message_type,
                        media_id=media_id,
                        media_mime_type=media_mime,
                    )
                )
    return out


def iter_meta_inbound_events(payload: Any) -> Iterator[MetaInboundMessage]:
    if not isinstance(payload, dict):
        return
    for ev in _events_from_payload(payload):
        yield ev


def extract_phone_number_id_from_meta_payload(data: dict) -> Optional[str]:
    """First ``phone_number_id`` in a WhatsApp webhook payload (messages or otherwise)."""
    if (data.get("object") or "") != "whatsapp_business_account":
        return None
    for entry in data.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            meta = value.get("metadata") or {}
            if isinstance(meta, dict):
                pid = meta.get("phone_number_id")
                if pid:
                    return str(pid).strip()
    return None
