"""Verify Meta / WhatsApp ``X-Hub-Signature-256`` webhook signatures."""
from __future__ import annotations

import hashlib
import hmac


def is_valid_meta_webhook_body(
    *,
    app_secret: str,
    raw_body: bytes,
    signature_header: str | None,
) -> bool:
    if not signature_header or not signature_header.strip():
        return False
    if not app_secret or not app_secret.strip():
        return False
    expected = (
        "sha256="
        + hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
    )
    provided = signature_header.strip()
    return hmac.compare_digest(expected, provided)
