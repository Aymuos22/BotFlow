"""
Small helper for encrypting/decrypting per-tenant secrets stored in the DB.

We intentionally use symmetric encryption (Fernet) so secrets can be displayed
back to admins if needed, and to support provider signature validation.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    """
    Derive a stable Fernet key from Settings.secret_key.

    Fernet requires a 32-byte urlsafe base64-encoded key.
    """
    secret = (get_settings().secret_key or "").encode("utf-8")
    digest = hashlib.sha256(secret).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: Optional[str]) -> Optional[str]:
    if plaintext is None:
        return None
    pt = plaintext.strip()
    if not pt:
        return None
    token = _fernet().encrypt(pt.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: Optional[str]) -> Optional[str]:
    if ciphertext is None:
        return None
    ct = ciphertext.strip()
    if not ct:
        return None
    try:
        pt = _fernet().decrypt(ct.encode("utf-8"))
    except InvalidToken:
        # Avoid raising during DB loads; treat as missing / corrupted.
        return None
    return pt.decode("utf-8")

