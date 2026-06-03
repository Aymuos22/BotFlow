"""
Best-effort parsing of AiSensy / Project API inbound webhook JSON.

AiSensy may deliver Meta-compatible shapes or a flatter JSON object.
This module normalises those into simple records for the shared RAG pipeline.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AisensyInboundMessage:
    external_message_id: Optional[str]
    customer_phone_e164: str
    business_routing_key: Optional[str]
    text: str


def routing_whatsapp_key(phone: Optional[str]) -> Optional[str]:
    """Normalise a business or customer id to ``whatsapp:+<E.164>`` for DB lookup."""
    if phone is None:
        return None
    s = str(phone).strip()
    if not s:
        return None
    if s.startswith("whatsapp:"):
        rest = s[len("whatsapp:") :].strip()
    else:
        rest = s
    rest = rest.split("@")[0].strip()
    if not rest:
        return None
    digits = re.sub(r"\D", "", rest)
    if not digits:
        return None
    return f"whatsapp:+{digits}"


def customer_e164_from_sender(phone: Optional[str]) -> Optional[str]:
    if phone is None:
        return None
    s = str(phone).strip()
    if not s:
        return None
    if s.startswith("whatsapp:"):
        s = s[len("whatsapp:") :].strip()
    s = s.split("@")[0].strip()
    if not s:
        return None
    if s.startswith("+"):
        return s
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None
    return f"+{digits}"


def _extract_text_from_message(msg: dict) -> str:
    if not msg:
        return ""
    mtype = (msg.get("type") or "").lower()
    if mtype == "text":
        body = msg.get("text") or {}
        if isinstance(body, dict):
            return str(body.get("body") or "").strip()
        return str(body or "").strip()
    if "text" in msg and isinstance(msg["text"], dict):
        return str(msg["text"].get("body") or "").strip()
    for key in ("body", "message", "content", "text"):
        v = msg.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _events_from_meta_envelope(data: dict) -> List[AisensyInboundMessage]:
    out: List[AisensyInboundMessage] = []
    for entry in data.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            biz = (
                metadata.get("display_phone_number")
                or metadata.get("phone_number_id")
            )
            routing = routing_whatsapp_key(biz) if biz else None
            for msg in value.get("messages") or []:
                if not isinstance(msg, dict):
                    continue
                ext_id = msg.get("id") or msg.get("messageId")
                from_raw = msg.get("from")
                cust = customer_e164_from_sender(from_raw)
                txt = _extract_text_from_message(msg)
                if not cust:
                    continue
                out.append(
                    AisensyInboundMessage(
                        external_message_id=str(ext_id) if ext_id else None,
                        customer_phone_e164=cust,
                        business_routing_key=routing,
                        text=txt,
                    )
                )
    return out


def _events_from_flat_dict(data: dict) -> List[AisensyInboundMessage]:
    out: List[AisensyInboundMessage] = []
    biz_raw = (
        data.get("to")
        or data.get("recipient")
        or data.get("businessPhone")
        or data.get("display_phone_number")
        or (data.get("metadata") or {}).get("display_phone_number")
    )
    routing = routing_whatsapp_key(biz_raw)

    msg_block = data.get("message")
    if isinstance(msg_block, dict):
        candidates = [msg_block]
    else:
        candidates = [data]

    for block in candidates:
        if not isinstance(block, dict):
            continue
        ext_id = (
            block.get("messageId")
            or block.get("id")
            or block.get("message_id")
            or data.get("messageId")
            or data.get("id")
        )
        from_raw = (
            block.get("from")
            or block.get("sender")
            or block.get("customerPhone")
            or data.get("from")
            or data.get("sender")
        )
        cust = customer_e164_from_sender(from_raw)
        txt = (
            block.get("body")
            or block.get("message")
            or block.get("text")
            or data.get("body")
            or data.get("message")
            or data.get("text")
        )
        if isinstance(txt, dict):
            txt = txt.get("body") or txt.get("text")
        txt = str(txt or "").strip()
        if not cust:
            continue
        out.append(
            AisensyInboundMessage(
                external_message_id=str(ext_id) if ext_id else None,
                customer_phone_e164=cust,
                business_routing_key=routing,
                text=txt,
            )
        )
    return out


def iter_aisensy_inbound_events(payload: Any) -> Iterator[AisensyInboundMessage]:
    """
    Yield zero or more inbound user text events from a webhook payload.

    Unsupported or empty payloads yield nothing (caller should log).
    """
    if payload is None:
        return
    if isinstance(payload, list):
        for item in payload:
            yield from iter_aisensy_inbound_events(item)
        return
    if not isinstance(payload, dict):
        logger.warning("AiSensy webhook ignored: root JSON is not an object")
        return

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload

    if isinstance(data, dict) and data.get("entry"):
        for ev in _events_from_meta_envelope(data):
            yield ev
        return

    if isinstance(data, dict):
        nested = data.get("message")
        if isinstance(nested, dict) and nested.get("sender"):
            sender = nested.get("sender") or {}
            user = sender.get("user") if isinstance(sender, dict) else None
            from_raw = None
            if isinstance(user, dict):
                from_raw = user.get("phone") or user.get("wa_id") or user.get("id")
            biz_raw = nested.get("to") or data.get("to")
            routing = routing_whatsapp_key(biz_raw)
            ext_id = nested.get("id") or data.get("id")
            txt = (
                nested.get("text")
                or nested.get("body")
                or (nested.get("content") or "")
            )
            if isinstance(txt, dict):
                txt = txt.get("body") or ""
            txt = str(txt or "").strip()
            cust = customer_e164_from_sender(from_raw)
            if cust:
                yield AisensyInboundMessage(
                    external_message_id=str(ext_id) if ext_id else None,
                    customer_phone_e164=cust,
                    business_routing_key=routing,
                    text=txt,
                )
                return

        for ev in _events_from_flat_dict(data):
            yield ev
