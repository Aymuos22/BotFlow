"""
Twilio request signature validation.

Twilio signs webhooks with X-Twilio-Signature:
  base64( HMAC-SHA1( AuthToken, URL + concatenated(sorted(params)) ) )

This module is intentionally tiny so it can be unit-tested without FastAPI.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Mapping, Optional


def compute_twilio_signature(
    *,
    url: str,
    params: Mapping[str, str],
    auth_token: str,
) -> str:
    """
    Compute the expected X-Twilio-Signature for a form-encoded webhook.

    Args:
        url: Full URL Twilio requested (scheme + host + path + query).
        params: Form params as strings.
        auth_token: Twilio Auth Token for the sending account.
    """
    pieces = [url]
    for k in sorted(params.keys()):
        pieces.append(k)
        pieces.append(params[k] or "")
    payload = "".join(pieces).encode("utf-8")
    mac = hmac.new(auth_token.encode("utf-8"), payload, hashlib.sha1).digest()
    return base64.b64encode(mac).decode("utf-8")


def is_valid_twilio_request(
    *,
    url: str,
    params: Mapping[str, str],
    auth_token: str,
    provided_signature: Optional[str],
) -> bool:
    if not provided_signature:
        return False
    expected = compute_twilio_signature(url=url, params=params, auth_token=auth_token)
    return hmac.compare_digest(expected, provided_signature.strip())

