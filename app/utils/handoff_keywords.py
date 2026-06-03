"""
Human-request keyword detection.

Used by the webhook handler to decide whether an incoming customer
message is requesting a human agent rather than a bot answer.

Keyword matching is simple substring search (case-insensitive).
Companies can extend the default list via ``handoff_config_json`` stored
in ``company_configs``:

    {
        "human_request_keywords": ["my custom keyword", "escalate please"]
    }

This is intentionally rule-based – no ML required.  False positives are
acceptable (a customer who accidentally triggers a handoff can simply
type again once the conversation is resumed via the resume-bot API).
"""
from typing import List, Optional

# Default phrases that strongly signal the user wants a human
DEFAULT_HUMAN_KEYWORDS: List[str] = [
    # English
    "talk to human",
    "speak to human",
    "human agent",
    "real person",
    "talk to agent",
    "speak to agent",
    "connect me to agent",
    "need a human",
    "want a human",
    "human support",
    "agent please",
    "live agent",
    "customer support representative",
    "customer representative",
    "talk to representative",
    "speak to representative",
    "human representative",
    "transfer to agent",
    "escalate",
    # Hindi (Devanagari)
    "मानव से बात",
    "एजेंट से बात",
    "इंसान से बात",
    # Hinglish (Roman Hindi)
    "agent chahiye",
    "human chahiye",
    "agent se baat",
    "insaan se baat",
    "mujhe agent chahiye",
    "real agent chahiye",
    "help chahiye human",
]


def is_human_request(
    text: str,
    custom_keywords: Optional[List[str]] = None,
) -> bool:
    """
    Return True if *text* contains a human-escalation signal.

    Args:
        text:            Customer message text.
        custom_keywords: Company-specific extra keywords from config.

    Returns:
        True if any keyword is found (case-insensitive substring match).
    """
    if not text:
        return False

    text_lower = text.lower()
    all_keywords = DEFAULT_HUMAN_KEYWORDS + (custom_keywords or [])

    return any(kw.lower() in text_lower for kw in all_keywords)


def get_handoff_acknowledgement(
    handoff_config: Optional[dict],
    language: str,
) -> str:
    """
    Return the company-configured or default handoff acknowledgement text.

    Args:
        handoff_config: Company's ``handoff_config_json`` (may be None).
        language:       Detected output language.

    Returns:
        Acknowledgement message text.
    """
    _defaults = {
        "english": (
            "I'm connecting you to a human agent. "
            "Please wait a moment – they will be with you shortly."
        ),
        "hindi": (
            "मैं आपको एक मानव एजेंट से जोड़ रहा हूँ। "
            "कृपया एक क्षण प्रतीक्षा करें।"
        ),
        "hinglish": (
            "Aapko ek human agent se connect kar raha hoon. "
            "Please thoda wait karein."
        ),
    }

    if handoff_config:
        ack_map = handoff_config.get("handoff_acknowledgement", {})
        msg = ack_map.get(language) or ack_map.get("english")
        if msg:
            return str(msg)

    return _defaults.get(language, _defaults["english"])
