"""
Unit tests for eval/metrics/retrieval.py.

Tests cover:
  - recall_at_k: basic, all relevant, none relevant, k > len(retrieved)
  - precision_at_k: basic, empty relevant, k=0
  - hit_rate_at_k
  - reciprocal_rank: first match, last match, no match
  - ndcg_at_k: binary and graded relevance
  - dcg_at_k, idcg_at_k
  - compute_retrieval_metrics: bundle function
  - aggregate_retrieval_metrics: macro average
  - score_distribution
  - Edge cases: empty lists, duplicate chunks, no ground truth
"""
import math
import pytest

from eval.metrics.retrieval import (
    recall_at_k,
    precision_at_k,
    hit_rate_at_k,
    reciprocal_rank,
    dcg_at_k,
    idcg_at_k,
    ndcg_at_k,
    compute_retrieval_metrics,
    aggregate_retrieval_metrics,
    score_distribution,
)


# ─────────────────────────────────────────────────────────────────────────── #
# recall_at_k
# ─────────────────────────────────────────────────────────────────────────── #


class TestRecallAtK:
    def test_perfect_recall(self):
        assert recall_at_k(["a", "b", "c"], ["a", "b", "c"], k=3) == 1.0

    def test_partial_recall(self):
        # 1 out of 2 relevant items in top-3
        assert recall_at_k(["a", "b"], ["a", "x", "y"], k=3) == 0.5

    def test_no_relevant_in_top_k(self):
        assert recall_at_k(["z"], ["a", "b", "c"], k=3) == 0.0

    def test_all_relevant_outside_k(self):
        assert recall_at_k(["d", "e"], ["a", "b", "c", "d"], k=3) == 0.0

    def test_k_larger_than_retrieved(self):
        # k=10 but only 2 retrieved — both are relevant
        assert recall_at_k(["a", "b"], ["a", "b"], k=10) == 1.0

    def test_empty_relevant_returns_zero(self):
        assert recall_at_k([], ["a", "b", "c"], k=5) == 0.0

    def test_empty_retrieved_returns_zero(self):
        assert recall_at_k(["a", "b"], [], k=5) == 0.0

    def test_duplicate_relevant_not_double_counted(self):
        # Duplicates in relevant should be deduplicated (use set)
        assert recall_at_k(["a", "a", "b"], ["a"], k=3) == 0.5

    def test_k_zero(self):
        assert recall_at_k(["a"], ["a"], k=0) == 0.0

    def test_recall_at_1(self):
        assert recall_at_k(["a", "b"], ["a"], k=1) == 0.5

    def test_single_relevant_item_found_at_rank_3(self):
        assert recall_at_k(["c"], ["a", "b", "c", "d"], k=3) == 1.0

    def test_single_relevant_item_not_in_top_3(self):
        assert recall_at_k(["d"], ["a", "b", "c", "d"], k=3) == 0.0


# ─────────────────────────────────────────────────────────────────────────── #
# precision_at_k
# ─────────────────────────────────────────────────────────────────────────── #


class TestPrecisionAtK:
    def test_perfect_precision(self):
        assert precision_at_k(["a", "b"], ["a", "b"], k=2) == 1.0

    def test_half_precision(self):
        assert precision_at_k(["a", "b"], ["a", "x", "y"], k=3) == pytest.approx(1 / 3)

    def test_zero_precision(self):
        assert precision_at_k(["z"], ["a", "b", "c"], k=3) == 0.0

    def test_k_zero_returns_zero(self):
        assert precision_at_k(["a"], ["a"], k=0) == 0.0

    def test_empty_relevant(self):
        # Precision is defined even when relevant is empty
        assert precision_at_k([], ["a", "b", "c"], k=3) == 0.0


# ─────────────────────────────────────────────────────────────────────────── #
# hit_rate_at_k
# ─────────────────────────────────────────────────────────────────────────── #


class TestHitRateAtK:
    def test_hit(self):
        assert hit_rate_at_k(["b"], ["a", "b", "c"], k=3) == 1.0

    def test_no_hit(self):
        assert hit_rate_at_k(["z"], ["a", "b", "c"], k=3) == 0.0

    def test_empty_relevant(self):
        assert hit_rate_at_k([], ["a", "b", "c"], k=3) == 0.0

    def test_hit_at_boundary(self):
        # Item is exactly at rank k
        assert hit_rate_at_k(["c"], ["a", "b", "c", "d"], k=3) == 1.0
        assert hit_rate_at_k(["d"], ["a", "b", "c", "d"], k=3) == 0.0


# ─────────────────────────────────────────────────────────────────────────── #
# reciprocal_rank
# ─────────────────────────────────────────────────────────────────────────── #


class TestReciprocalRank:
    def test_first_rank(self):
        assert reciprocal_rank(["a"], ["a", "b", "c"]) == 1.0

    def test_second_rank(self):
        assert reciprocal_rank(["b"], ["a", "b", "c"]) == pytest.approx(0.5)

    def test_third_rank(self):
        assert reciprocal_rank(["c"], ["a", "b", "c"]) == pytest.approx(1 / 3)

    def test_no_relevant(self):
        assert reciprocal_rank(["z"], ["a", "b", "c"]) == 0.0

    def test_empty_retrieved(self):
        assert reciprocal_rank(["a"], []) == 0.0

    def test_empty_relevant(self):
        assert reciprocal_rank([], ["a", "b"]) == 0.0

    def test_multiple_relevant_uses_first(self):
        # Both a and c are relevant; first hit is a at rank 1
        assert reciprocal_rank(["a", "c"], ["a", "b", "c"]) == 1.0

    def test_multiple_relevant_later_hit(self):
        # b is relevant at rank 2; c is relevant at rank 3 — use rank 2
        assert reciprocal_rank(["b", "c"], ["a", "b", "c"]) == pytest.approx(0.5)


# ─────────────────────────────────────────────────────────────────────────── #
# NDCG / DCG / IDCG
# ─────────────────────────────────────────────────────────────────────────── #


class TestDCG:
    def test_dcg_perfect_order(self):
        # Grades: [3, 2, 1] at positions 1, 2, 3
        grades = {"a": 3, "b": 2, "c": 1}
        retrieved = ["a", "b", "c"]
        dcg = dcg_at_k(retrieved, grades, k=3)
        expected = 3 / math.log2(2) + 2 / math.log2(3) + 1 / math.log2(4)
        assert dcg == pytest.approx(expected)

    def test_dcg_zero_grade_items(self):
        grades = {"a": 0, "b": 0}
        assert dcg_at_k(["a", "b"], grades, k=2) == 0.0

    def test_idcg_correct(self):
        grades = {"a": 3, "b": 1, "c": 2}
        # Ideal order: a(3), c(2), b(1)
        idcg = idcg_at_k(grades, k=3)
        expected = 3 / math.log2(2) + 2 / math.log2(3) + 1 / math.log2(4)
        assert idcg == pytest.approx(expected)


class TestNDCG:
    def test_perfect_ndcg(self):
        """Perfect retrieval: same order as ideal."""
        relevant = ["a", "b", "c"]
        grades = {"a": 3, "b": 2, "c": 1}
        assert ndcg_at_k(relevant, ["a", "b", "c"], grades, k=3) == pytest.approx(1.0)

    def test_ndcg_binary_fallback(self):
        """When grades=None, binary relevance (grade=1) is used."""
        relevant = ["a", "b"]
        # Retrieved: [a, x, b] — both relevant items present, a before b
        result = ndcg_at_k(relevant, ["a", "x", "b"], None, k=3)
        assert 0.0 < result <= 1.0

    def test_ndcg_zero_when_nothing_retrieved(self):
        assert ndcg_at_k(["a", "b"], ["x", "y"], None, k=5) == 0.0

    def test_ndcg_empty_relevant_returns_zero(self):
        assert ndcg_at_k([], ["a", "b"], None, k=5) == 0.0

    def test_ndcg_degrade_with_worse_ranking(self):
        """Worse ranking of same relevant items produces lower NDCG."""
        relevant = ["a", "b"]
        grades = {"a": 2, "b": 1}
        perfect = ndcg_at_k(relevant, ["a", "b", "x"], grades, k=3)
        worse = ndcg_at_k(relevant, ["x", "b", "a"], grades, k=3)
        assert perfect > worse

    def test_ndcg_at_1(self):
        """NDCG@1 = 1.0 iff the top result is the most relevant."""
        relevant = ["a"]
        grades = {"a": 3}
        assert ndcg_at_k(relevant, ["a", "b"], grades, k=1) == pytest.approx(1.0)
        assert ndcg_at_k(relevant, ["b", "a"], grades, k=1) == 0.0


# ─────────────────────────────────────────────────────────────────────────── #
# compute_retrieval_metrics (bundle)
# ─────────────────────────────────────────────────────────────────────────── #


class TestComputeRetrievalMetrics:
    def test_full_metrics_with_ground_truth(self):
        relevant = ["doc1-chunk-2", "doc1-chunk-5"]
        retrieved = ["doc1-chunk-2", "doc1-chunk-3", "doc1-chunk-5", "doc2-chunk-1"]
        scores = [0.9, 0.8, 0.7, 0.6]
        result = compute_retrieval_metrics(relevant, retrieved, scores)

        assert result["recall@5"] == pytest.approx(1.0)
        assert result["recall@1"] == pytest.approx(0.5)
        assert result["precision@5"] is not None
        assert result["mrr"] == pytest.approx(1.0)  # first hit at rank 1
        assert result["hit_rate@5"] == pytest.approx(1.0)
        assert result["avg_retrieval_score"] == pytest.approx(0.75)

    def test_no_ground_truth_returns_none(self):
        result = compute_retrieval_metrics([], ["a", "b", "c"], [0.9, 0.8, 0.7])
        assert result["recall@5"] is None
        assert result["mrr"] is None
        assert result["ndcg@5"] is None
        # avg_retrieval_score should still be computed
        assert result["avg_retrieval_score"] is not None

    def test_no_scores_returns_none_avg(self):
        result = compute_retrieval_metrics(["a"], ["a", "b"], None)
        assert result["avg_retrieval_score"] is None

    def test_empty_retrieved(self):
        result = compute_retrieval_metrics(["a", "b"], [], [])
        assert result["recall@5"] == 0.0
        assert result["mrr"] == 0.0


# ─────────────────────────────────────────────────────────────────────────── #
# aggregate_retrieval_metrics
# ─────────────────────────────────────────────────────────────────────────── #


class TestAggregateRetrievalMetrics:
    def test_simple_average(self):
        metrics = [
            {"recall@5": 0.8, "mrr": 0.7},
            {"recall@5": 0.6, "mrr": 0.5},
        ]
        result = aggregate_retrieval_metrics(metrics)
        assert result["recall@5"] == pytest.approx(0.7)
        assert result["mrr"] == pytest.approx(0.6)

    def test_none_values_excluded(self):
        metrics = [
            {"recall@5": 0.8, "mrr": None},
            {"recall@5": 0.6, "mrr": 0.5},
        ]
        result = aggregate_retrieval_metrics(metrics)
        # mrr: only one non-None value = 0.5
        assert result["mrr"] == pytest.approx(0.5)

    def test_empty_list_returns_empty(self):
        assert aggregate_retrieval_metrics([]) == {}

    def test_all_none_key_omitted(self):
        metrics = [{"recall@5": None}, {"recall@5": None}]
        result = aggregate_retrieval_metrics(metrics)
        assert "recall@5" not in result


# ─────────────────────────────────────────────────────────────────────────── #
# score_distribution
# ─────────────────────────────────────────────────────────────────────────── #


class TestScoreDistribution:
    def test_basic_stats(self):
        scores = [0.1, 0.3, 0.5, 0.7, 0.9]
        d = score_distribution(scores)
        assert d["min"] == pytest.approx(0.1)
        assert d["max"] == pytest.approx(0.9)
        assert d["mean"] == pytest.approx(0.5)

    def test_empty_returns_empty(self):
        assert score_distribution([]) == {}

    def test_single_score(self):
        d = score_distribution([0.75])
        assert d["min"] == pytest.approx(0.75)
        assert d["max"] == pytest.approx(0.75)
