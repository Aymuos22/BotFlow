"""Normalize LLM Markdown into plain, WhatsApp-friendly text."""
from __future__ import annotations

import re

_MARKDOWN_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*\n][^*\n]*?)\*\*")
_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_REFERENCE_LABELS = {
    "buy here",
    "click here",
    "here",
    "link",
    "view here",
    "view product",
}


def _replace_markdown_link(match: re.Match[str]) -> str:
    label = " ".join(match.group(1).strip().split())
    url = match.group(2).strip()
    if label.lower() in _REFERENCE_LABELS:
        return url
    return f"{label}: {url}"


def whatsapp_friendly_text(text: str) -> str:
    """
    Convert common Markdown artifacts into text that reads cleanly in WhatsApp.

    WhatsApp uses single asterisks for bold, while LLMs often emit Markdown
    double-asterisk bold. Markdown links are also not rendered by WhatsApp, so
    expose the real URL directly.
    """
    if not text:
        return text
    out = text.replace("\r\n", "\n").replace("\r", "\n")
    out = _MARKDOWN_LINK_RE.sub(_replace_markdown_link, out)
    out = _BOLD_RE.sub(r"*\1*", out)
    out = _HEADER_RE.sub("", out)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()
