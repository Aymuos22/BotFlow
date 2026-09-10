"""
Unit tests for eval/taxonomy.py.

Tests cover:
  - assign_retrieval_failures: wrong_document, wrong_chunk, insufficient_top_k
  - assign_system_failures: fallback_failure, llm_failure
  - assign_generation_failures_heuristic: language drift
  - aggregate_failure_counts
  - failure_rate_summary
"""
import pytest

from eval.taxonomy import (
    assign_retrieval_failures,
    assign_system_failures,
    assign_generation_failures_heuristic,
    aggregate_failure_counts,
    failure_rate_summary,
    RetrievalFailure,
    SystemFailure,
    GenerationFailure,
)


class TestAssignRetrievalFailures:
    def test_no_failure_when_correct_chunk_in_top_k(self):
        relevant = ["doc1-chunk-2"]
        retrieved = ["doc1-chunk-2", "doc1-chunk-3", "doc1-chunk-5"]
        failures = assign_retrieval_failures(
            relevant_chunk_ids=relevant,
            relevant_document_ids=["doc1"],
            retrieved_chunk_ids=retrieved,
            top_k=5,
        )
        assert failures == []

    def test_wrong_document(self):
        relevant = ["doc1-chunk-2"]
        retrieved = ["doc2-chunk-0", "doc3-chunk-1", "doc4-chunk-0"]
        failures = assign_retrieval_failures(
            relevant_chunk_ids=relevant,
            relevant_document_ids=["doc1"],
            retrieved_chunk_ids=retrieved,
            top_k=3,
        )
        assert RetrievalFailure.WRONG_DOCUMENT.value in failures

    def test_wrong_chunk_right_doc(self):
        # Right document (doc1) retrieved but wrong chunk
        relevant = ["doc1-chunk-2"]
        retrieved = ["doc1-chunk-5", "doc2-chunk-0"]  # doc1 present but not chunk-2
        failures = assign_retrieval_failures(
            relevant_chunk_ids=relevant,
            relevant_document_ids=["doc1"],
            retrieved_chunk_ids=retrieved,
            top_k=5,
        )
        assert RetrievalFailure.WRONG_CHUNK.value in failures

    def test_insufficient_top_k(self):
        # Relevant chunk is in retrieved but beyond top-K
        relevant = ["doc1-chunk-2"]
        # retrieved has doc1-chunk-2 at position 5 (0-indexed), top_k=3 means rank 6
        retrieved = ["a", "b", "c", "d", "e", "doc1-chunk-2"]
        failures = assign_retrieval_failures(
            relevant_chunk_ids=relevant,
            relevant_document_ids=["doc1"],
            retrieved_chunk_ids=retrieved,
            top_k=3,
        )
        # Should get both wrong_document (not in top-3) and insufficient_top_k
        assert RetrievalFailure.INSUFFICIENT_TOP_K.value in failures

    def test_unanswerable_no_failures(self):
        failures = assign_retrieval_failures(
            relevant_chunk_ids=[],
            relevant_document_ids=[],
            retrieved_chunk_ids=["doc1-chunk-0"],
            answerable=False,
        )
        assert failures == []

    def test_no_ground_truth_no_failures(self):
        failures = assign_retrieval_failures(
            relevant_chunk_ids=[],
            relevant_document_ids=[],
            retrieved_chunk_ids=["doc1-chunk-0"],
            answerable=True,
        )
        assert failures == []

    def test_multiple_relevant_partial_hit(self):
        # Two relevant chunks, only one retrieved
        relevant = ["doc1-chunk-2", "doc1-chunk-5"]
        retrieved = ["doc1-chunk-2", "doc2-chunk-0"]
        failures = assign_retrieval_failures(
            relevant_chunk_ids=relevant,
            relevant_document_ids=["doc1"],
            retrieved_chunk_ids=retrieved,
            top_k=3,
        )
        # doc1-chunk-5 is missing from top-3 but doc1-chunk-2 is there
        # Not a full failure — recall@3 = 0.5, but no wrong_document or wrong_chunk
        # (the doc is in the retrieved, just not all chunks)
        assert failures == []


class TestAssignSystemFailures:
    def test_fallback_on_answerable(self):
        response = {"response_type": "fallback", "fallback_triggered": True}
        failures = assign_system_failures(response, answerable=True)
        assert SystemFailure.FALLBACK_FAILURE.value in failures

    def test_no_failure_on_correct_response(self):
        response = {"response_type": "rag", "fallback_triggered": False}
        failures = assign_system_failures(response, answerable=True)
        assert failures == []

    def test_fallback_on_unanswerable_is_correct(self):
        # Fallback on unanswerable question = correct behavior
        response = {"response_type": "fallback", "fallback_triggered": True}
        failures = assign_system_failures(response, answerable=False)
        assert SystemFailure.FALLBACK_FAILURE.value not in failures

    def test_llm_failure_detected(self):
        response = {
            "response_type": "fallback",
            "fallback_triggered": True,
            "answer": "I'm having trouble generating a reply right now. Please try again.",
        }
        failures = assign_system_failures(response, answerable=True)
        assert SystemFailure.LLM_FAILURE.value in failures


class TestAssignGenerationFailuresHeuristic:
    def test_no_failure_for_clean_english(self):
        failures = assign_generation_failures_heuristic(
            generated_answer="This product helps with joint pain.",
            expected_answer="It helps with joint pain.",
            retrieved_chunks=["Joint pain product"],
            language="english",
        )
        assert failures == []

    def test_devanagari_in_english_answer(self):
        failures = assign_generation_failures_heuristic(
            generated_answer="यह एक अच्छा उत्पाद है।",
            expected_answer="This is a good product.",
            retrieved_chunks=[],
            language="english",
        )
        from eval.taxonomy import GenerationFailure
        assert GenerationFailure.INSTRUCTION_FOLLOWING_FAILURE.value in failures

    def test_no_devanagari_in_hindi_answer(self):
        failures = assign_generation_failures_heuristic(
            generated_answer="This is all English text in Hindi context.",
            expected_answer=None,
            retrieved_chunks=[],
            language="hindi",
        )
        assert GenerationFailure.INSTRUCTION_FOLLOWING_FAILURE.value in failures

    def test_empty_generated_no_failure(self):
        failures = assign_generation_failures_heuristic(
            generated_answer="",
            expected_answer="some answer",
            retrieved_chunks=[],
            language="english",
        )
        assert failures == []

    def test_very_short_answer_when_long_expected(self):
        failures = assign_generation_failures_heuristic(
            generated_answer="Yes.",
            expected_answer="The return policy allows customers to return any product within "
                           "30 days of purchase for a full refund. Items must be unused.",
            retrieved_chunks=[],
            language="english",
        )
        assert GenerationFailure.INCOMPLETE_ANSWER.value in failures


class TestAggregateFailureCounts:
    def test_counts_correctly(self):
        per_example = [
            ["wrong_document", "fallback_failure"],
            ["hallucination"],
            ["wrong_document"],
            [],
        ]
        counts = aggregate_failure_counts(per_example)
        assert counts["wrong_document"] == 2
        assert counts["hallucination"] == 1
        assert counts["fallback_failure"] == 1
        assert counts["wrong_chunk"] == 0

    def test_empty_list(self):
        counts = aggregate_failure_counts([])
        assert all(v == 0 for v in counts.values())


class TestFailureRateSummary:
    def test_basic_rates(self):
        per_example = [["wrong_document"], ["hallucination"], [], []]
        rates = failure_rate_summary(per_example, total=4)
        assert rates["wrong_document"] == pytest.approx(0.25)
        assert rates["hallucination"] == pytest.approx(0.25)
        assert rates["wrong_chunk"] == pytest.approx(0.0)

    def test_zero_total_returns_zeros(self):
        rates = failure_rate_summary([], total=0)
        assert all(v == 0.0 for v in rates.values())
