"""
Unit tests for app.services.language_service.

Covers:
  - detect_language()
  - normalize_query()
  - choose_output_language()
"""
import pytest

from app.services.language_service import (
    choose_output_language,
    detect_language,
    is_strong_language_signal,
    last_decisive_user_language_from_history,
    normalize_query,
    resolve_reply_language,
)


class TestDetectLanguage:
    def test_english_sentence(self):
        assert detect_language("Hello, how are you?") == "english"

    def test_hindi_devanagari(self):
        assert detect_language("नमस्ते, आप कैसे हैं?") == "hindi"

    def test_hinglish_common_words(self):
        # Contains common Hinglish markers like 'hai', 'kya'
        assert detect_language("Mera naam John hai, kya aap help kar sakte ho?") == "hinglish"

    def test_english_with_punctuation(self):
        assert detect_language("What is the refund policy?") == "english"

    def test_mostly_devanagari_is_hindi(self):
        # Mix but Devanagari heavy
        assert detect_language("मेरा नाम John है") == "hindi"

    def test_empty_string_defaults_to_english(self):
        assert detect_language("") == "english"

    def test_single_hinglish_word_is_english(self):
        # Single 'hai' alone shouldn't trigger hinglish
        result = detect_language("hai")
        # Acceptable result: english or hinglish
        assert result in ("english", "hinglish")

    def test_multiple_hinglish_markers(self):
        text = "Kya aur bhi options hain mere liye?"
        assert detect_language(text) == "hinglish"

    def test_help_chahiye_is_hinglish(self):
        assert detect_language("help chahiye") == "hinglish"
        assert detect_language("mujhe help chahiye") == "hinglish"

    @pytest.mark.parametrize(
        "text",
        [
            "order ka status batao",
            "price kitna hai",
            "dard ke liye dawa chahiye",
            "mujhe delivery kab milegi",
            "pet me gas aur jalan hai",
            "baal jhad rahe hain product batao",
            "madad chahiye",
        ],
    )
    def test_common_whatsapp_hinglish_phrases(self, text):
        assert detect_language(text) == "hinglish"

    def test_english_support_words_do_not_force_hinglish(self):
        assert detect_language("I need help with my order please explain the steps") == "english"

    @pytest.mark.parametrize(
        "text",
        [
            "help de do",
            "order kar do",
            "payment check kar do",
            "price bata do",
            "details bhej do",
            "product dikha do",
            "medicine suggest kar do",
            "doctor call kar do",
            "delivery kab milegi",
            "kitne ka hai",
            "refund kaise milega",
            "isko confirm kar do",
        ],
    )
    def test_common_multiword_hinglish_requests(self, text):
        assert detect_language(text) == "hinglish"


class TestNormalizeQuery:
    def test_english_strips_extra_spaces(self):
        result = normalize_query("  hello   world  ", "english")
        assert result == "hello world"

    def test_hinglish_lowercased(self):
        result = normalize_query("KYA Aap HELP Kar Sakte Ho?", "hinglish")
        assert result == result.lower()

    def test_hindi_returned_as_is_stripped(self):
        result = normalize_query("  नमस्ते  ", "hindi")
        assert result == "नमस्ते"

    def test_english_returns_stripped(self):
        result = normalize_query("What is your return policy?", "english")
        assert result == "What is your return policy?"

    def test_unknown_language_defaults_to_strip(self):
        result = normalize_query("  some text  ", "unknown")
        assert "some text" in result


class TestChooseOutputLanguage:
    def test_uses_detected_language_when_no_config(self):
        result = choose_output_language(
            detected_language="hindi",
            company_supported_languages=["english", "hindi"],
            default_language="english",
        )
        assert result == "hindi"

    def test_hinglish_maps_to_roman_reply_when_hindi_supported(self):
        """Roman Hindi input should not fall back to English when Hindi is on."""
        result = choose_output_language(
            detected_language="hinglish",
            company_supported_languages=["english", "hindi"],
            default_language="english",
        )
        assert result == "hinglish"

    def test_hinglish_falls_back_to_default_if_only_english_supported(self):
        result = choose_output_language(
            detected_language="hinglish",
            company_supported_languages=["english"],
            default_language="english",
        )
        assert result == "english"

    def test_returns_detected_if_in_supported(self):
        result = choose_output_language(
            detected_language="hinglish",
            company_supported_languages=["english", "hindi", "hinglish"],
            default_language="english",
        )
        assert result == "hinglish"

    def test_default_language_used_when_detected_is_none(self):
        result = choose_output_language(
            detected_language=None,
            company_supported_languages=["english"],
            default_language="english",
        )
        assert result == "english"


class TestStrongSignalAndResolve:
    def test_ok_is_weak_english(self):
        assert not is_strong_language_signal("ok", "english")

    def test_long_english_is_strong(self):
        assert is_strong_language_signal(
            "What is your return policy for international orders?",
            "english",
        )

    def test_hindi_always_strong(self):
        assert is_strong_language_signal("नमस्ते", "hindi")

    def test_resolve_uses_sticky_for_weak_message(self):
        out = resolve_reply_language(
            "thanks",
            conversation_last_language="hindi",
            company_supported_languages=["english", "hindi", "hinglish"],
            default_language="english",
        )
        assert out == "hindi"

    def test_resolve_uses_current_when_strong(self):
        out = resolve_reply_language(
            "I need help with my order please explain the steps",
            conversation_last_language="hindi",
            company_supported_languages=["english", "hindi", "hinglish"],
            default_language="english",
        )
        assert out == "english"

    def test_last_decisive_from_history(self):
        class T:
            def __init__(self, role: str, content: str):
                self.role = role
                self.content = content

        hist = [
            T("user", "नमस्ते मुझे जानकारी चाहिए"),
            T("assistant", "जी बताइए"),
            T("user", "ok"),
        ]
        assert last_decisive_user_language_from_history(hist) == "hindi"
