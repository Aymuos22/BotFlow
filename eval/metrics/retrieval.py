"""
Deterministic retrieval evaluation metrics.

All functions are pure (no I/O, no LLM).  They operate on lists of IDs and
return floats, making them easy to unit-test and verify.

Metrics implemented:
  - Recall@K        : fraction of relevant items found in top-K
  - Precision@K     : fraction of top-K items that are relevant
  - Hit Rate@K      : binary — was ANY relevant item in top-K?
  - MRR             : Mean Reciprocal Rank of the first relevant item
  - NDCG@K          : Normalised Discounted Cumulative Gain (binary or graded)
  - Average score   : mean Weaviate retrieval score
  - Score distribution stats

Mathematical definitions
------------------------
  Recall@K    = |relevant ∩ top_K_retrieved| / |relevant|
  Precision@K = |relevant ∩ top_K_retrieved| / K
  Hit@K       = 1 if |relevant ∩ top_K_retrieved| > 0 else 0
  MRR         = 1 / rank_of_first_relevant   (0 if none found)
  DCG@K       = Σ_{i=1}^{K}  grade_i / log2(i + 1)
  IDCG@K      = DCG of ideal ranking
  NDCG@K      = DCG@K / IDCG@K

Note: ranks are 1-indexed.  An empty relevant set returns 0.0 for all metrics
(undefined recall) so callers should check ``item.has_ground_truth()`` before
computing retrieval metrics.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────── #
# Core single-query metrics
# ─────────────────────────────────────────────────────────────────────────── #


def recall_at_k(
    relevant: List[str],
    retrieved: List[str],
    k: int,
) -> float:
    """
    Recall@K for a single query.

    Returns 0.0 when ``relevant`` is empty (undefined, not an error).
    """
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    hits = len(set(relevant) & top_k)
    return hits / len(set(relevant))


def precision_at_k(
    relevant: List[str],
    retrieved: List[str],
    k: int,
) -> float:
    """
    Precision@K for a single query.

    Returns 0.0 when k == 0.
    """
    if k == 0:
        return 0.0
    top_k = set(retrieved[:k])
    hits = len(set(relevant) & top_k)
    return hits / k


def hit_rate_at_k(
    relevant: List[str],
    retrieved: List[str],
    k: int,
) -> float:
    """
    Hit Rate@K (binary): 1.0 if any relevant item in top-K, else 0.0.

    Returns 0.0 when ``relevant`` is empty.
    """
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    return 1.0 if (set(relevant) & top_k) else 0.0


def reciprocal_rank(
    relevant: List[str],
    retrieved: List[str],
) -> float:
    """
    Reciprocal Rank for a single query.

    Returns 1/rank where rank is the 1-indexed position of the first relevant
    item in ``retrieved``.  Returns 0.0 if no relevant item is found.
    """
    relevant_set = set(relevant)
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant_set:
            return 1.0 / rank
    return 0.0


def dcg_at_k(
    retrieved: List[str],
    grades: Dict[str, int],
    k: int,
) -> float:
    """
    Discounted Cumulative Gain at K using explicit relevance grades.

    Args:
        retrieved:  Ranked list of retrieved item IDs.
        grades:     Mapping from item_id to relevance grade (non-negative int).
                    Items absent from ``grades`` have grade 0.
        k:          Cutoff rank.

    Returns:
        DCG@K score.
    """
    total = 0.0
    for i, item in enumerate(retrieved[:k], start=1):
        grade = grades.get(item, 0)
        if grade > 0:
            total += grade / math.log2(i + 1)
    return total


def idcg_at_k(grades: Dict[str, int], k: int) -> float:
    """
    Ideal DCG@K — DCG of a perfect ranking.

    Args:
        grades:  All available relevance grades.
        k:       Cutoff rank.
    """
    sorted_grades = sorted(grades.values(), reverse=True)[:k]
    total = 0.0
    for i, grade in enumerate(sorted_grades, start=1):
        if grade > 0:
            total += grade / math.log2(i + 1)
    return total


def ndcg_at_k(
    relevant: List[str],
    retrieved: List[str],
    grades: Optional[Dict[str, int]],
    k: int,
) -> float:
    """
    NDCG@K for a single query.

    When ``grades`` is None or empty, falls back to binary relevance (grade=1
    for each item in ``relevant``).

    Returns 0.0 when no relevant items exist.
    """
    if not relevant:
        return 0.0

    # Build grade dict — fall back to binary if no graded relevance
    if grades:
        grade_dict = {r: grades.get(r, 1) for r in relevant}
        # Also include any extra grades provided
        grade_dict.update({k: v for k, v in grades.items() if v > 0})
    else:
        grade_dict = {r: 1 for r in relevant}

    ideal = idcg_at_k(grade_dict, k)
    if ideal == 0.0:
        return 0.0

    actual = dcg_at_k(retrieved, grade_dict, k)
    return actual / ideal


# ─────────────────────────────────────────────────────────────────────────── #
# Full per-query metric bundle
# ─────────────────────────────────────────────────────────────────────────── #


def compute_retrieval_metrics(
    relevant_chunk_ids: List[str],
    retrieved_chunk_ids: List[str],
    retrieval_scores: Optional[List[float]] = None,
    relevance_grades: Optional[Dict[str, int]] = None,
    ks: Optional[List[int]] = None,
) -> Dict[str, Optional[float]]:
    """
    Compute the full set of retrieval metrics for a single query.

    Args:
        relevant_chunk_ids:  Ground-truth relevant chunk IDs.
        retrieved_chunk_ids: Ordered retrieved chunk IDs (rank 1 first).
        retrieval_scores:    Aligned retrieval scores (same order as retrieved).
        relevance_grades:    Optional graded relevance dict for NDCG.
        ks:                  Cutoff values to compute metrics at (default [1,3,5,10]).

    Returns:
        Dict with keys like ``recall@5``, ``mrr``, ``ndcg@5``, etc.
        Values are ``None`` when relevant_chunk_ids is empty (no ground truth).
    """
    if ks is None:
        ks = [1, 3, 5, 10]

    if not relevant_chunk_ids:
        # No ground truth — mark all retrieval metrics as None
        result: Dict[str, Optional[float]] = {}
        for k in ks:
            result[f"recall@{k}"] = None
            result[f"precision@{k}"] = None
            result[f"ndcg@{k}"] = None
        result["mrr"] = None
        result["hit_rate@5"] = None
        result["avg_retrieval_score"] = _avg_score(retrieval_scores)
        return result

    result = {}

    # K-based metrics
    for k in ks:
        result[f"recall@{k}"] = recall_at_k(relevant_chunk_ids, retrieved_chunk_ids, k)
        result[f"precision@{k}"] = precision_at_k(relevant_chunk_ids, retrieved_chunk_ids, k)
        result[f"ndcg@{k}"] = ndcg_at_k(
            relevant_chunk_ids, retrieved_chunk_ids, relevance_grades, k
        )

    result["mrr"] = reciprocal_rank(relevant_chunk_ids, retrieved_chunk_ids)
    result["hit_rate@5"] = hit_rate_at_k(relevant_chunk_ids, retrieved_chunk_ids, 5)
    result["avg_retrieval_score"] = _avg_score(retrieval_scores)

    return result


# ─────────────────────────────────────────────────────────────────────────── #
# Aggregate across multiple queries
# ─────────────────────────────────────────────────────────────────────────── #


def aggregate_retrieval_metrics(
    per_query_metrics: List[Dict[str, Optional[float]]],
) -> Dict[str, float]:
    """
    Compute macro averages across all queries.

    ``None`` values (no ground truth) are excluded from the average.
    Keys without any non-None values are omitted from the result.

    Args:
        per_query_metrics:  List of dicts from ``compute_retrieval_metrics``.

    Returns:
        Dict of macro-averaged metrics.
    """
    if not per_query_metrics:
        return {}

    # Collect all metric keys
    all_keys: set[str] = set()
    for m in per_query_metrics:
        all_keys.update(m.keys())

    aggregated: Dict[str, float] = {}
    for key in sorted(all_keys):
        values = [m[key] for m in per_query_metrics if m.get(key) is not None]
        if values:
            aggregated[key] = sum(values) / len(values)

    return aggregated


# ─────────────────────────────────────────────────────────────────────────── #
# Score distribution helpers
# ─────────────────────────────────────────────────────────────────────────── #


def score_distribution(scores: List[float]) -> Dict[str, float]:
    """
    Compute basic distribution statistics for retrieval scores.

    Args:
        scores:  List of retrieval scores (e.g. Weaviate hybrid scores).

    Returns:
        Dict with min, max, mean, median, p25, p75.
    """
    if not scores:
        return {}

    s = sorted(scores)
    n = len(s)
    mean = sum(s) / n

    def _percentile(p: float) -> float:
        idx = p * (n - 1)
        lo = int(idx)
        hi = lo + 1
        if hi >= n:
            return s[-1]
        frac = idx - lo
        return s[lo] * (1 - frac) + s[hi] * frac

    return {
        "min": s[0],
        "max": s[-1],
        "mean": mean,
        "median": _percentile(0.5),
        "p25": _percentile(0.25),
        "p75": _percentile(0.75),
        "count": float(n),
        "below_threshold_count": float(sum(1 for v in s if v < 0.4)),
    }


def _avg_score(scores: Optional[List[float]]) -> Optional[float]:
    if not scores:
        return None
    valid = [s for s in scores if s is not None and not math.isnan(s)]
    return sum(valid) / len(valid) if valid else None
