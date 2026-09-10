"""
Failure taxonomy for RAG evaluation.

Three layers of failures:
  1. Retrieval failures  — deterministically detectable from metrics
  2. Generation failures — mix of heuristic (detected here) + LLM-judge
  3. System failures     — detected from response metadata

Design: deterministic assignment is done here without any LLM call.
LLM-judge-detected failures (hallucination, context_ignored) are added
by the judge module and appended to the failure list.

Usage:
    from eval.taxonomy import assign_retrieval_failures, assign_system_failures

    failures = assign_retrieval_failures(item, retrieved_chunk_ids, ks=[1,3,5])
    failures += assign_system_failures(response)
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────── #
# Taxonomy enums
# ─────────────────────────────────────────────────────────────────────────── #


class RetrievalFailure(str, Enum):
    WRONG_DOCUMENT = "wrong_document"
    """The correct document was never retrieved."""

    WRONG_CHUNK = "wrong_chunk"
    """Correct document was retrieved, but not the right chunk."""

    INSUFFICIENT_TOP_K = "insufficient_top_k"
    """Relevant chunk exists but was ranked beyond the configured top-K."""

    SEMANTIC_MISMATCH = "semantic_mismatch"
    """High Weaviate score but the retrieved chunk is not actually relevant."""

    MISSING_INFORMATION = "missing_information"
    """No relevant information exists in the indexed corpus."""


class GenerationFailure(str, Enum):
    HALLUCINATION = "hallucination"
    """Answer contains claims not present in retrieved context."""

    INCORRECT_ANSWER = "incorrect_answer"
    """Answer is factually wrong compared to expected answer."""

    INCOMPLETE_ANSWER = "incomplete_answer"
    """Answer only partially addresses the question."""

    CONTEXT_IGNORED = "context_ignored"
    """Context contained the answer but LLM ignored it."""

    INSTRUCTION_FOLLOWING_FAILURE = "instruction_following_failure"
    """Language / format constraint was not followed."""


class SystemFailure(str, Enum):
    EMBEDDING_FAILURE = "embedding_failure"
    """Query embedding failed; BM25 used as fallback."""

    RETRIEVAL_FAILURE = "retrieval_failure"
    """Weaviate returned an error or empty result unexpectedly."""

    LLM_FAILURE = "llm_failure"
    """LLM call threw an exception."""

    TIMEOUT = "timeout"
    """Evaluation timed out waiting for retrieval or generation."""

    FALLBACK_FAILURE = "fallback_failure"
    """System triggered fallback on an answerable question."""


# All failure type strings in a flat set for validation
ALL_FAILURE_TYPES: frozenset[str] = frozenset(
    {f.value for f in RetrievalFailure}
    | {f.value for f in GenerationFailure}
    | {f.value for f in SystemFailure}
)


# ─────────────────────────────────────────────────────────────────────────── #
# Deterministic failure assigners
# ─────────────────────────────────────────────────────────────────────────── #


def assign_retrieval_failures(
    relevant_chunk_ids: List[str],
    relevant_document_ids: List[str],
    retrieved_chunk_ids: List[str],
    *,
    top_k: int = 5,
    answerable: bool = True,
) -> List[str]:
    """
    Assign retrieval failure types deterministically.

    Args:
        relevant_chunk_ids:  Ground-truth chunk IDs (from dataset).
        relevant_document_ids: Ground-truth document IDs.
        retrieved_chunk_ids:   Ordered list of retrieved chunk IDs (position = rank).
        top_k:                 Configured top-K for retrieval.
        answerable:            Whether the question should be answerable.

    Returns:
        List of failure type strings (may be empty if retrieval succeeded).
    """
    if not answerable:
        # Unanswerable questions: retrieval "success" means we correctly return fallback.
        return []

    if not relevant_chunk_ids and not relevant_document_ids:
        # No ground truth available — cannot assign retrieval failures.
        return []

    failures: List[str] = []
    top_k_retrieved = set(retrieved_chunk_ids[:top_k])

    # ── Check chunk-level recall ─────────────────────────────────────── #
    chunk_hit = bool(top_k_retrieved & set(relevant_chunk_ids))

    # ── Check document-level recall ──────────────────────────────────── #
    # Extract document IDs from retrieved chunk IDs (format: "<doc_id>-chunk-<N>")
    def _doc_from_chunk(chunk_id: str) -> Optional[str]:
        if "-chunk-" in chunk_id:
            return chunk_id.rsplit("-chunk-", 1)[0]
        return None

    retrieved_doc_ids = set()
    for cid in top_k_retrieved:
        doc = _doc_from_chunk(cid)
        if doc:
            retrieved_doc_ids.add(doc)

    doc_hit = bool(retrieved_doc_ids & set(relevant_document_ids))

    if relevant_chunk_ids and not chunk_hit:
        if doc_hit:
            # Right document, wrong chunk
            failures.append(RetrievalFailure.WRONG_CHUNK.value)
        else:
            # Wrong document entirely
            failures.append(RetrievalFailure.WRONG_DOCUMENT.value)

            # Was the relevant chunk ranked at all (beyond top-K)?
            all_retrieved = set(retrieved_chunk_ids)
            beyond_top_k = bool(all_retrieved & set(relevant_chunk_ids))
            if beyond_top_k:
                failures.append(RetrievalFailure.INSUFFICIENT_TOP_K.value)

    elif relevant_document_ids and not doc_hit:
        # We have doc ground truth but no chunk ground truth
        failures.append(RetrievalFailure.WRONG_DOCUMENT.value)

    return failures


def assign_system_failures(
    response: Dict[str, Any],
    *,
    answerable: bool = True,
) -> List[str]:
    """
    Assign system failure types from the RAG response dict.

    Args:
        response:  Output of ``RAGService.process_query()``.
        answerable: Whether the question was answerable.

    Returns:
        List of system failure type strings.
    """
    failures: List[str] = []

    response_type = response.get("response_type", "rag")
    fallback_triggered = response.get("fallback_triggered", False)

    # Fallback on an answerable question = failure
    if answerable and fallback_triggered:
        failures.append(SystemFailure.FALLBACK_FAILURE.value)

    # Detect LLM failure from answer text heuristic
    answer = (response.get("answer") or "").lower()
    if "having trouble generating" in answer or "try again" in answer.lower():
        failures.append(SystemFailure.LLM_FAILURE.value)

    return failures


def assign_generation_failures_heuristic(
    generated_answer: Optional[str],
    expected_answer: Optional[str],
    retrieved_chunks: List[str],
    *,
    language: str = "english",
) -> List[str]:
    """
    Assign generation failures using deterministic heuristics (no LLM).

    These are complementary to LLM-judge-assigned failures and run without
    any external API call.

    Args:
        generated_answer:  The answer produced by the RAG pipeline.
        expected_answer:   Ground-truth answer (may be None).
        retrieved_chunks:  Context chunks that were passed to the LLM.
        language:          Output language of the answer.

    Returns:
        List of generation failure type strings.
    """
    if not generated_answer:
        return []

    failures: List[str] = []

    # Detect language instruction following failure (simple heuristic)
    if language == "english" and _has_devanagari(generated_answer):
        failures.append(GenerationFailure.INSTRUCTION_FOLLOWING_FAILURE.value)
    elif language == "hindi" and not _has_devanagari(generated_answer):
        # Hindi answer with no Devanagari is suspicious
        latin_frac = _latin_fraction(generated_answer)
        if latin_frac > 0.8:
            failures.append(GenerationFailure.INSTRUCTION_FOLLOWING_FAILURE.value)

    # Detect very short answers as potentially incomplete
    answer_stripped = generated_answer.strip()
    if len(answer_stripped) < 20 and expected_answer and len(expected_answer) > 100:
        failures.append(GenerationFailure.INCOMPLETE_ANSWER.value)

    return failures


def aggregate_failure_counts(
    per_example_failures: List[List[str]],
) -> Dict[str, int]:
    """
    Aggregate failure counts across all examples.

    Returns:
        dict mapping failure_type -> count (number of examples with that failure).
    """
    counts: Dict[str, int] = {ft: 0 for ft in ALL_FAILURE_TYPES}
    for failures in per_example_failures:
        for ft in failures:
            if ft in counts:
                counts[ft] += 1
    return counts


def failure_rate_summary(
    per_example_failures: List[List[str]],
    total: int,
) -> Dict[str, float]:
    """
    Return failure rates as fractions of total examples.

    Args:
        per_example_failures: List of failure lists per example.
        total:                 Total number of examples evaluated.

    Returns:
        dict mapping failure_type -> rate (0.0 to 1.0).
    """
    if total == 0:
        return {ft: 0.0 for ft in ALL_FAILURE_TYPES}
    counts = aggregate_failure_counts(per_example_failures)
    return {ft: count / total for ft, count in counts.items()}


def _has_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in (text or ""))


def _latin_fraction(text: str) -> float:
    if not text:
        return 0.0
    alpha = [ch for ch in text if ch.isalpha()]
    if not alpha:
        return 0.0
    latin = sum(1 for ch in alpha if ch.isascii())
    return latin / len(alpha)
