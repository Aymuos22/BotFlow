"""
Unit tests for eval/metrics/generation.py.

Tests cover:
  - token_f1: perfect match, partial match, no overlap, empty strings
  - exact_match: normalisation, punctuation, case
  - context_coverage: coverage fraction, all covered, none covered
  - compute_generation_metrics: bundle function
  - aggregate_generation_metrics: macro average
"""
import pytest

from eval.metrics.generation import (
    token_f1,
    exact_match,
    context_coverage,
    compute_generation_metrics,
    aggregate_generation_metrics,
)


class TestTokenF1:
    def test_identical_strings(self):
        assert token_f1("hello world", "hello world") == pytest.approx(1.0)

    def test_no_overlap(self):
        assert token_f1("apple banana", "cat dog fish") == 0.0

    def test_partial_overlap(self):
        # "hello world" vs "hello there"
        # gold: {hello, world}, pred: {hello, there}
        # common: {hello} = 1
        # precision = 1/2, recall = 1/2, f1 = 1/2
        assert token_f1("hello world", "hello there") == pytest.approx(0.5)

    def test_empty_expected(self):
        assert token_f1("", "some answer") == 0.0

    def test_empty_generated(self):
        assert token_f1("expected answer", "") == 0.0

    def test_both_empty(self):
        assert token_f1("", "") == 0.0

    def test_case_insensitive(self):
        assert token_f1("Hello World", "hello world") == pytest.approx(1.0)

    def test_punctuation_ignored(self):
        assert token_f1("Hello, world!", "hello world") == pytest.approx(1.0)

    def test_subset_answer(self):
        # Generated is subset of expected
        result = token_f1("the cat sat on the mat", "cat mat")
        assert 0 < result < 1.0

    def test_superset_answer(self):
        # Generated is superset of expected (lower precision, full recall)
        result = token_f1("cat", "the cat sat on the mat")
        assert 0 < result < 1.0

    def test_duplicate_tokens(self):
        # Bag-of-words with duplicates
        result = token_f1("good good good", "good bad")
        # gold: {good:3, bad:0}, pred: {good:1, bad:1}
        # common good = min(1,3) = 1, common bad = min(1,0) = 0
        # precision = 1/2, recall = 1/3, f1 = 2*(1/2 * 1/3)/(1/2+1/3)
        assert 0 < result < 1.0


class TestExactMatch:
    def test_identical(self):
        assert exact_match("hello world", "hello world") is True

    def test_different_case(self):
        assert exact_match("Hello World", "hello world") is True

    def test_different_punctuation(self):
        assert exact_match("Hello, world!", "hello world") is True

    def test_different_content(self):
        assert exact_match("hello world", "goodbye world") is False

    def test_empty_both(self):
        assert exact_match("", "") is False  # both empty = not a match

    def test_one_empty(self):
        assert exact_match("hello", "") is False


class TestContextCoverage:
    def test_full_coverage(self):
        # Answer contains all significant tokens from the single chunk
        chunk = "return policy allows customers to return products within 30 days"
        answer = "customers can return their products within 30 days according to our policy"
        result = context_coverage(answer, [chunk])
        assert result == 1.0

    def test_zero_coverage(self):
        chunk = "refund policy allows returns within 30 days"
        # Answer has completely different content
        answer = "hello there how are you today"
        result = context_coverage(answer, [chunk])
        # May or may not be 0 depending on stopword overlap, but should be very low
        assert result < 0.5

    def test_empty_chunks(self):
        assert context_coverage("some answer", []) == 0.0

    def test_empty_answer(self):
        assert context_coverage("", ["some chunk content here"]) == 0.0

    def test_partial_coverage(self):
        chunks = [
            "products can be returned within 30 days",
            "delivery takes 5 to 7 business days",
        ]
        # Answer only mentions returns, not delivery
        answer = "you can return products within 30 days of purchase"
        result = context_coverage(answer, chunks)
        # One of two chunks covered
        assert result == pytest.approx(0.5)


class TestComputeGenerationMetrics:
    def test_all_inputs_provided(self):
        result = compute_generation_metrics(
            generated_answer="The return policy allows returns within 30 days.",
            expected_answer="You can return products within 30 days.",
            retrieved_chunks=["return policy allows returning products within 30 days"],
        )
        assert result["token_f1"] is not None
        assert result["exact_match"] is not None
        assert result["answer_length_chars"] is not None
        assert result["context_coverage"] is not None

    def test_no_expected_answer(self):
        result = compute_generation_metrics(
            generated_answer="Some answer here.",
            expected_answer=None,
        )
        assert result["token_f1"] is None
        assert result["exact_match"] is None
        assert result["answer_length_chars"] is not None

    def test_no_retrieved_chunks(self):
        result = compute_generation_metrics(
            generated_answer="Some answer.",
            expected_answer="Expected answer.",
            retrieved_chunks=None,
        )
        assert result["context_coverage"] is None
        assert result["token_f1"] is not None  # still computed

    def test_no_generated_answer(self):
        result = compute_generation_metrics(
            generated_answer=None,
            expected_answer="expected",
        )
        assert result["token_f1"] is None
        assert result["answer_length_chars"] is None

    def test_answer_length_correct(self):
        result = compute_generation_metrics(
            generated_answer="Hello!",
            expected_answer=None,
        )
        assert result["answer_length_chars"] == pytest.approx(6.0)


class TestAggregateGenerationMetrics:
    def test_basic_average(self):
        per_example = [
            {"token_f1": 0.8, "answer_length_chars": 100.0},
            {"token_f1": 0.6, "answer_length_chars": 200.0},
        ]
        result = aggregate_generation_metrics(per_example)
        assert result["token_f1"] == pytest.approx(0.7)
        assert result["answer_length_chars"] == pytest.approx(150.0)

    def test_none_excluded(self):
        per_example = [
            {"token_f1": 0.8, "context_coverage": None},
            {"token_f1": 0.4, "context_coverage": 0.9},
        ]
        result = aggregate_generation_metrics(per_example)
        assert result["token_f1"] == pytest.approx(0.6)
        assert result["context_coverage"] == pytest.approx(0.9)

    def test_empty_list(self):
        assert aggregate_generation_metrics([]) == {}
