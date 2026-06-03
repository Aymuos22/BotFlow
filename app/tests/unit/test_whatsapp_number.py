"""Tests for app.utils.whatsapp_number."""

import pytest

from app.utils.whatsapp_number import normalize_whatsapp_destination


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+15551234567", "whatsapp:+15551234567"),
        ("15551234567", "whatsapp:+15551234567"),
        ("whatsapp:+15551234567", "whatsapp:+15551234567"),
        ("WhatsApp:+15551234567", "whatsapp:+15551234567"),
        ("+1 (555) 123-4567", "whatsapp:+15551234567"),
        ("+91 98765 43210", "whatsapp:+919876543210"),
        ("919876543210", "whatsapp:+919876543210"),
        ("+441234567890", "whatsapp:+441234567890"),
    ],
)
def test_normalize_whatsapp_destination_ok(raw: str, expected: str) -> None:
    assert normalize_whatsapp_destination(raw) == expected


def test_normalize_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_whatsapp_destination("   ")


def test_normalize_rejects_leading_zero_trunk() -> None:
    with pytest.raises(ValueError, match="leading 0"):
        normalize_whatsapp_destination("09876543210")


def test_normalize_rejects_too_short() -> None:
    with pytest.raises(ValueError, match="8"):
        normalize_whatsapp_destination("+123456")


def test_normalize_strips_c_us_suffix() -> None:
    assert normalize_whatsapp_destination("919876543210@c.us") == "whatsapp:+919876543210"


def test_company_config_schema_normalizes_staff_notify() -> None:
    from app.schemas.company_config import CompanyConfigUpdate

    m = CompanyConfigUpdate.model_validate(
        {"handoff_staff_notify_whatsapp": "+1 (415) 555-1212"}
    )
    assert m.handoff_staff_notify_whatsapp == "whatsapp:+14155551212"
