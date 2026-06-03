"""
Opt-out detection and acknowledgement messages.

Detects when a customer asks to stop receiving messages and returns
the appropriate single-language acknowledgement to send back.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Opt-out phrase patterns (English, Hindi, Hinglish)
# ---------------------------------------------------------------------------

_OPT_OUT_PATTERNS: list[re.Pattern[str]] = [
    # English
    re.compile(r"\bstop\b", re.I),
    re.compile(r"\bunsubscribe\b", re.I),
    re.compile(r"\bdo\s+not\s+(message|contact|text|call|whatsapp)\b", re.I),
    re.compile(r"\bdon'?t\s+(message|contact|text|call|whatsapp)\b", re.I),
    re.compile(r"\bno\s+more\s+messages?\b", re.I),
    re.compile(r"\bremove\s+me\b", re.I),
    re.compile(r"\bopt\s*[\-\s]?out\b", re.I),
    re.compile(r"\bplease\s+stop\b", re.I),
    re.compile(r"\bstop\s+messaging\b", re.I),
    re.compile(r"\bstop\s+sending\b", re.I),
    re.compile(r"\bi\s+don'?t\s+want\s+(any\s+)?messages?\b", re.I),
    re.compile(r"\bleave\s+me\s+alone\b", re.I),
    re.compile(r"\bblock\s+me\b", re.I),
    re.compile(r"\bdo\s+not\s+disturb\b", re.I),
    re.compile(r"\bdnd\b", re.I),
    # Hindi / Hinglish
    re.compile(r"mat\s+bhejo", re.I),
    re.compile(r"message\s+mat\s+karo", re.I),
    re.compile(r"message\s+band\s+karo", re.I),
    re.compile(r"band\s+karo", re.I),
    re.compile(r"nahi\s+chahiye", re.I),
    re.compile(r"nah?in\s+chahiye", re.I),
    re.compile(r"rok\s*o", re.I),
    re.compile(r"hatao", re.I),
    re.compile(r"pareshan\s+mat\s+karo", re.I),
    re.compile(r"disturb\s+mat\s+karo", re.I),
    re.compile(r"message\s+mat\s+bhejo", re.I),
    re.compile(r"mujhe\s+mat\s+bhejo", re.I),
    re.compile(r"iska\s+zaroorat\s+nahi", re.I),
    re.compile(r"koi\s+message\s+nahi", re.I),
    re.compile(r"send\s+mat\s+karo", re.I),
]

# ---------------------------------------------------------------------------
# Acknowledgement messages by language
# ---------------------------------------------------------------------------

_ACK: dict[str, str] = {
    "english": (
        "You have been unsubscribed. We will not send you any more messages. "
        "If you ever want to hear from us again, just say *Hi* and we'll be happy to help! 😊"
    ),
    "hindi": (
        "आपको अनसब्सक्राइब कर दिया गया है। हम आपको अब कोई संदेश नहीं भेजेंगे। "
        "अगर कभी भी आपको हमारी सहायता चाहिए, बस *Hi* लिखें। 😊"
    ),
    "hinglish": (
        "Aapko unsubscribe kar diya gaya hai. Hum aapko ab koi message nahi bhejenge. "
        "Agar kabhi zaroorat ho, bas *Hi* likhiye aur hum help karne ke liye ready hain! 😊"
    ),
}
_ACK_DEFAULT = _ACK["english"]


def is_opt_out_message(text: str) -> bool:
    """Return True if the message is clearly a request to stop messaging."""
    t = (text or "").strip()
    if not t:
        return False
    # Ignore very long messages — opt-out requests are short
    if len(t) > 200:
        return False
    for pattern in _OPT_OUT_PATTERNS:
        if pattern.search(t):
            return True
    return False


def opt_out_ack(language: str | None) -> str:
    """Return the opt-out acknowledgement in the customer's language."""
    lang = (language or "english").lower().strip()
    return _ACK.get(lang, _ACK_DEFAULT)
