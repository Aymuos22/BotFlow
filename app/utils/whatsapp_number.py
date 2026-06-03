"""
Normalize user-entered phone values to ``whatsapp:+<E.164 digits>`` for storage and APIs.
"""

from __future__ import annotations

import re


def normalize_whatsapp_destination(raw: str) -> str:
    """
    Convert messy input into canonical ``whatsapp:+<digits>``.

    Accepts e.g. ``+1 (555) 123-4567``, ``15551234567``, ``whatsapp:+91 98765 43210``.

    Raises:
        ValueError: Empty input, no digits, invalid length, or leading national trunk 0.
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("WhatsApp number is empty.")

    lower = s.lower()
    if lower.startswith("whatsapp:"):
        s = s[len("whatsapp:") :].strip()

    s = s.split("@", 1)[0].strip()
    digits = re.sub(r"\D", "", s)
    if not digits:
        raise ValueError("WhatsApp number must contain digits.")

    if digits[0] == "0":
        raise ValueError(
            "Use international format with country code (omit leading 0). "
            "Example: India +91…, US +1…."
        )

    if len(digits) < 8 or len(digits) > 15:
        raise ValueError(
            "WhatsApp number must be 8–15 digits including country code."
        )

    return f"whatsapp:+{digits}"
