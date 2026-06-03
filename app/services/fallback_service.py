"""
Fallback decision and message selection service.

Determines whether to return a fallback response instead of an LLM-generated
answer, and selects the appropriate fallback message text.

Business rules
--------------
Confidence uses an ordered list of per-hit scores from Weaviate (hybrid or BM25).

``confidence_strategy`` (company ``rag_config_json`` or default ``top``):

- ``top`` — Fallback when the best score is below the threshold (legacy behavior).
- ``avg_top_k`` — Fallback when the average of the top *k* scores is below the
  threshold (smoother when the first hit is an outlier).
- ``any_above`` — Proceed if *any* retrieved hit meets or exceeds the threshold.

If there are no numeric scores, the caller should treat that as low confidence
(typically an empty score list → fallback).

Fallback messages are stored per language in the company's
``fallback_config_json`` column.
"""
from typing import Any, Dict, List, Optional


_DEFAULT_FALLBACK = "I'm sorry, I couldn't find relevant information to answer your question. Please contact support for further assistance."

_DEFAULT_FALLBACK_BY_LANG: Dict[str, str] = {
    "english": _DEFAULT_FALLBACK,
    "hindi": "माफ करें, मुझे आपके प्रश्न का उत्तर देने के लिए पर्याप्त जानकारी नहीं मिली।",
    "hinglish": "Sorry, aapke question ka jawab dene ke liye relevant information nahi mili.",
}


class FallbackService:
    """Stateless service for fallback decision logic."""

    def should_fallback(
        self,
        scores: List[float],
        threshold: float,
        strategy: str = "top",
        *,
        avg_top_n: int = 3,
    ) -> bool:
        """
        Return True if retrieval should be treated as low confidence.

        Args:
            scores: Non-empty list of numeric scores (best-first).
            threshold: Minimum acceptable score for the chosen strategy.
            strategy: ``top`` | ``avg_top_k`` | ``any_above``.
            avg_top_n: Window size for ``avg_top_k``.
        """
        if not scores:
            return True
        s = (strategy or "top").strip().lower()
        if s == "any_above":
            return not any(sc >= threshold for sc in scores)
        if s == "avg_top_k":
            k = max(1, int(avg_top_n))
            subset = scores[:k]
            if not subset:
                return True
            return (sum(subset) / len(subset)) < threshold
        # top (default)
        return scores[0] < threshold

    def get_fallback_message(
        self,
        fallback_config: Optional[Dict[str, Any]],
        language: str,
    ) -> str:
        if fallback_config:
            msg = fallback_config.get(language)
            if msg:
                return str(msg)
            if language == "hinglish":
                msg = fallback_config.get("hindi")
                if msg:
                    return str(msg)
            msg = fallback_config.get("english")
            if msg:
                return str(msg)

        return _DEFAULT_FALLBACK_BY_LANG.get(language, _DEFAULT_FALLBACK)
