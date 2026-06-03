"""Helpers for Meta WhatsApp message template payloads (Business Management API)."""
from __future__ import annotations

import re
from typing import Any


def positional_placeholder_count(body: str) -> int:
    """
    Count positional placeholders {{1}}, {{2}}, … in template body text.

    Meta requires contiguous indices starting at 1 (no gaps).
    """
    nums = sorted({int(m.group(1)) for m in re.finditer(r"\{\{(\d+)\}\}", body)})
    if not nums:
        return 0
    expected = list(range(1, len(nums) + 1))
    if nums != expected:
        raise ValueError(
            "Body placeholders must be contiguous positional variables "
            "{{1}}, {{2}}, … with no gaps (Meta requirement)."
        )
    return len(nums)


def build_simple_template_create_payload(
    *,
    name: str,
    category: str,
    language: str,
    body_text: str,
    footer_text: str | None,
    header_text: str | None,
    body_example_values: list[str],
) -> dict[str, Any]:
    """
    Build JSON body for POST /{waba-id}/message_templates.

    Supports TEXT header/body/footer only; positional parameters in BODY only.
    """
    if header_text and "{{" in header_text:
        raise ValueError("Header text cannot contain template variables in this flow.")

    if footer_text and "{{" in footer_text:
        raise ValueError("Footer cannot contain template variables.")

    n_vars = positional_placeholder_count(body_text)

    components: list[dict[str, Any]] = []

    if header_text and header_text.strip():
        ht = header_text.strip()
        components.append(
            {
                "type": "header",
                "format": "TEXT",
                "text": ht,
                "example": {"header_text": [ht[:80]]},
            }
        )

    body_comp: dict[str, Any] = {"type": "body", "text": body_text.strip()}
    if n_vars > 0:
        if len(body_example_values) != n_vars:
            raise ValueError(
                f"Body has {n_vars} placeholder(s); provide exactly {n_vars} "
                "example value(s) in order."
            )
        body_comp["example"] = {"body_text": [body_example_values]}
    components.append(body_comp)

    if footer_text and footer_text.strip():
        components.append({"type": "footer", "text": footer_text.strip()})

    payload: dict[str, Any] = {
        "name": name,
        "language": language.strip(),
        "category": category.strip().lower(),
        "components": components,
    }
    if n_vars > 0:
        payload["parameter_format"] = "positional"

    return payload
