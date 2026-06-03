"""Unit tests for lead warmth JSON parsing (no LLM)."""
import pytest

from app.services import lead_classification_service as lcs


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"warmth":"hot"}', "hot"),
        ("```\n{ \"warmth\": \"cold\" }\n```", "cold"),  # still finds embedded JSON
        ('Text {"warmth":"warm"}', "warm"),
        ("nope", None),
    ],
)
def test_parse_warmth(raw, expected):
    assert lcs._parse_warmth(raw) == expected
