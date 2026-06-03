"""
Unit tests for app.services.fallback_service.
"""
import pytest

from app.services.fallback_service import FallbackService


@pytest.fixture
def svc():
    return FallbackService()


class TestShouldFallbackTop:
    def test_low_score_triggers_fallback(self, svc):
        assert svc.should_fallback([0.1], threshold=0.4, strategy="top") is True

    def test_score_at_threshold_no_fallback(self, svc):
        assert svc.should_fallback([0.4], threshold=0.4, strategy="top") is False

    def test_score_above_threshold_no_fallback(self, svc):
        assert svc.should_fallback([0.8], threshold=0.4, strategy="top") is False

    def test_empty_scores_triggers_fallback(self, svc):
        assert svc.should_fallback([], threshold=0.4, strategy="top") is True

    def test_zero_score_triggers_fallback(self, svc):
        assert svc.should_fallback([0.0], threshold=0.4, strategy="top") is True


class TestShouldFallbackAnyAbove:
    def test_one_good_score_ok(self, svc):
        assert (
            svc.should_fallback([0.1, 0.5, 0.2], threshold=0.4, strategy="any_above")
            is False
        )

    def test_all_below_threshold(self, svc):
        assert (
            svc.should_fallback([0.1, 0.2], threshold=0.4, strategy="any_above")
            is True
        )


class TestShouldFallbackAvgTopK:
    def test_average_above_threshold(self, svc):
        assert (
            svc.should_fallback(
                [0.5, 0.5, 0.5], threshold=0.4, strategy="avg_top_k", avg_top_n=3
            )
            is False
        )

    def test_average_below_threshold(self, svc):
        assert (
            svc.should_fallback(
                [0.5, 0.2, 0.2], threshold=0.4, strategy="avg_top_k", avg_top_n=3
            )
            is True
        )


class TestGetFallbackMessage:
    def test_english_fallback(self, svc):
        config = {"english": "Sorry, I couldn't find relevant information."}
        msg = svc.get_fallback_message(config, "english")
        assert "Sorry" in msg

    def test_hindi_fallback(self, svc):
        config = {"hindi": "माफ करें, मुझे कोई जानकारी नहीं मिली।", "english": "Sorry."}
        msg = svc.get_fallback_message(config, "hindi")
        assert "माफ" in msg

    def test_missing_language_uses_english(self, svc):
        config = {"english": "Sorry, no info found."}
        msg = svc.get_fallback_message(config, "hinglish")
        assert "Sorry" in msg

    def test_hinglish_uses_hindi_template_when_hindi_only(self, svc):
        config = {"hindi": "माफ करें, जानकारी नहीं मिली।", "english": "Sorry."}
        msg = svc.get_fallback_message(config, "hinglish")
        assert "माफ" in msg

    def test_completely_empty_config_returns_default(self, svc):
        msg = svc.get_fallback_message({}, "english")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_none_config_returns_default(self, svc):
        msg = svc.get_fallback_message(None, "english")
        assert isinstance(msg, str)
        assert len(msg) > 0
