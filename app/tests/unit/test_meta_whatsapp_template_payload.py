import pytest

from app.utils.meta_whatsapp_template import (
    build_simple_template_create_payload,
    positional_placeholder_count,
)


def test_positional_placeholder_count_plain() -> None:
    assert positional_placeholder_count("Hello") == 0


def test_positional_placeholder_count_ordered() -> None:
    assert positional_placeholder_count("Hi {{1}}, order {{2}}, thanks {{3}}") == 3


def test_positional_placeholder_gap_raises() -> None:
    with pytest.raises(ValueError):
        positional_placeholder_count("Hi {{1}}, {{3}}")


def test_build_payload_body_only() -> None:
    p = build_simple_template_create_payload(
        name="lead_followup_v1",
        category="utility",
        language="en_US",
        body_text="Still need help with your inquiry?",
        footer_text=None,
        header_text=None,
        body_example_values=[],
    )
    assert p["name"] == "lead_followup_v1"
    assert p["category"] == "utility"
    assert p["language"] == "en_US"
    assert "parameter_format" not in p
    assert len(p["components"]) == 1
    assert p["components"][0]["type"] == "body"


def test_build_payload_with_variables() -> None:
    p = build_simple_template_create_payload(
        name="tpl_v2",
        category="marketing",
        language="en_IN",
        body_text="Hi {{1}}, reply YES if you still want updates.",
        footer_text="Company name",
        header_text=None,
        body_example_values=["Raj"],
    )
    assert p["parameter_format"] == "positional"
    body = [c for c in p["components"] if c["type"] == "body"][0]
    assert body["example"]["body_text"] == [["Raj"]]
    footers = [c for c in p["components"] if c["type"] == "footer"]
    assert len(footers) == 1
