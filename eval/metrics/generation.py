"""
Deterministic generation evaluation metrics.

All functions are pure (no I/O, no LLM).  They operate on strings and return
floats.

Metrics:
  - token_f1              : token-level F1 between expected and generated answer
  - answer_length_chars   : character count of the generated answer
  - context_coverage      : fraction of retrieved chunks referenced in the answer
                            (heuristic — checks if chunk keywords appear in answer)
  - exact_match           : whether normalised answers are identical

Note: these are *complementary* to the LLM judge.  They measure different
things:
  - token_f1 is useful when an expected answer exists.  It is NOT a
    replacement for semantic faithfulness (a hallucinated answer that happens
    to share words with the expected answer will score high).
  - context_coverage is a weak proxy for faithfulness and should not be used
    as the primary faithfulness signal.
  - The LLM judge (eval/judge/) handles semantic evaluation.
"""
from __future__ import annotations

import re
import string
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────── #
# Token-level F1
# ─────────────────────────────────────────────────────────────────────────── #


def _normalise(text: str) -> str:
    """Lower-case, remove punctuation and excess whitespace."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return " ".join(text.split())


def _tokenise(text: str) -> List[str]:
    return _normalise(text).split()


def token_f1(
    expected: str,
    generated: str,
) -> float:
    """
    Token-level F1 score between expected and generated answers.

    Standard SQuAD-style F1: computed over bag-of-words.

    Returns:
        float in [0.0, 1.0].  Returns 0.0 if either string is empty.
    """
    if not expected or not generated:
        return 0.0

    pred_tokens = _tokenise(generated)
    gold_tokens = _tokenise(expected)

    if not pred_tokens or not gold_tokens:
        return 0.0

    pred_bag: Dict[str, int] = {}
    gold_bag: Dict[str, int] = {}
    for t in pred_tokens:
        pred_bag[t] = pred_bag.get(t, 0) + 1
    for t in gold_tokens:
        gold_bag[t] = gold_bag.get(t, 0) + 1

    common = sum(
        min(pred_bag.get(t, 0), gold_bag.get(t, 0)) for t in set(gold_bag)
    )
    if common == 0:
        return 0.0

    precision = common / len(pred_tokens)
    recall = common / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def exact_match(expected: str, generated: str) -> bool:
    """
    Normalised exact match.

    Returns True if normalised versions are identical.
    """
    if not expected or not generated:
        return False
    return _normalise(expected) == _normalise(generated)


# ─────────────────────────────────────────────────────────────────────────── #
# Context coverage
# ─────────────────────────────────────────────────────────────────────────── #

# Minimum number of significant tokens a chunk must share with the answer
# to count as "referenced".
_COVERAGE_MIN_COMMON_TOKENS = 3
_COVERAGE_MIN_TOKEN_LEN = 4
_STOPWORDS = frozenset(
    [
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "not", "and", "or", "but",
        "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
        "into", "through", "this", "that", "these", "those", "it", "its",
        "you", "your", "he", "she", "they", "we", "me", "him", "her", "us",
        "them", "my", "his", "their", "our",
    ]
)


def _significant_tokens(text: str) -> set[str]:
    tokens = set(_tokenise(text))
    return {t for t in tokens if len(t) >= _COVERAGE_MIN_TOKEN_LEN and t not in _STOPWORDS}


def context_coverage(
    generated_answer: str,
    retrieved_chunks: List[str],
) -> float:
    """
    Fraction of retrieved chunks that have at least ``_COVERAGE_MIN_COMMON_TOKENS``
    significant tokens in common with the generated answer.

    This is a *weak heuristic* — not a substitute for faithfulness scoring.
    Useful for detecting answers that completely ignore all context.

    Args:
        generated_answer:   Generated text.
        retrieved_chunks:   List of chunk text strings passed to the LLM.

    Returns:
        float in [0.0, 1.0].  Returns 0.0 if no chunks provided.
    """
    if not retrieved_chunks or not generated_answer:
        return 0.0

    answer_tokens = _significant_tokens(generated_answer)
    if not answer_tokens:
        return 0.0

    covered = 0
    for chunk in retrieved_chunks:
        chunk_tokens = _significant_tokens(chunk)
        common = len(answer_tokens & chunk_tokens)
        if common >= _COVERAGE_MIN_COMMON_TOKENS:
            covered += 1

    return covered / len(retrieved_chunks)


# ─────────────────────────────────────────────────────────────────────────── #
# Per-example generation metric bundle
# ─────────────────────────────────────────────────────────────────────────── #


def compute_generation_metrics(
    generated_answer: Optional[str],
    expected_answer: Optional[str],
    retrieved_chunks: Optional[List[str]] = None,
) -> Dict[str, Optional[float]]:
    """
    Compute all deterministic generation metrics for a single example.

    Args:
        generated_answer:   Answer produced by the RAG pipeline.
        expected_answer:    Ground-truth expected answer (may be None).
        retrieved_chunks:   Raw chunk text strings (not chunk IDs).

    Returns:
        Dict with keys: ``token_f1``, ``exact_match``, ``answer_length_chars``,
        ``context_coverage``.
        Values are ``None`` when inputs are unavailable.
    """
    result: Dict[str, Optional[float]] = {
        "token_f1": None,
        "exact_match": None,
        "answer_length_chars": None,
        "context_coverage": None,
    }

    if generated_answer:
        result["answer_length_chars"] = float(len(generated_answer))

    if generated_answer and expected_answer:
        result["token_f1"] = token_f1(expected_answer, generated_answer)
        result["exact_match"] = 1.0 if exact_match(expected_answer, generated_answer) else 0.0

    if generated_answer and retrieved_chunks:
        result["context_coverage"] = context_coverage(generated_answer, retrieved_chunks)

    return result


# ─────────────────────────────────────────────────────────────────────────── #
# Aggregate across examples
# ─────────────────────────────────────────────────────────────────────────── #


def aggregate_generation_metrics(
    per_example: List[Dict[str, Optional[float]]],
) -> Dict[str, float]:
    """
    Macro-average all generation metrics.  ``None`` values are excluded.

    Args:
        per_example:  List of dicts from ``compute_generation_metrics``.

    Returns:
        Dict of averages for all available metrics.
    """
    if not per_example:
        return {}

    all_keys: set[str] = set()
    for m in per_example:
        all_keys.update(m.keys())

    result: Dict[str, float] = {}
    for key in sorted(all_keys):
        values = [m[key] for m in per_example if m.get(key) is not None]
        if values:
            result[key] = sum(values) / len(values)

    return result
