"""
Production log evaluation.

Samples production retrieval logs from the existing ``retrieval_logs`` table
and computes aggregate quality metrics WITHOUT sending any data to an LLM.

This is intentionally non-invasive:
  - Reads from ``retrieval_logs`` (already written by RAGService)
  - Does NOT extend the table schema
  - Does NOT send production queries to an external judge
  - Returns a dict of aggregate statistics suitable for dashboards/reporting

Privacy note: this module only reads already-logged data and produces
aggregate statistics.  No individual query text leaves the system.

Metrics computed:
  - fallback_rate             : fraction of queries that triggered fallback
  - no_answer_rate            : fraction with result_count == 0
  - mean_top_score            : mean highest retrieval score
  - score_distribution        : percentile breakdown of top_score
  - top_k_distribution        : histogram of result_count values
  - low_confidence_rate       : fraction with top_score < threshold
  - handoff_rate              : fraction that triggered handoff
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def compute_production_metrics(
    db,
    *,
    company_id: Optional[str] = None,
    since_days: int = 7,
    score_threshold: float = 0.4,
    sample_limit: int = 1000,
) -> Dict[str, Any]:
    """
    Compute aggregate production quality metrics from ``retrieval_logs``.

    Args:
        db:               SQLAlchemy AsyncSession.
        company_id:       Filter to a specific company (None = all companies).
        since_days:       Look-back window in days.
        score_threshold:  Threshold used to define "low confidence".
        sample_limit:     Max rows to process (avoids scanning huge tables).

    Returns:
        Dict of aggregate metrics.
    """
    import uuid as uuid_lib
    from sqlalchemy import select
    from app.models.retrieval_log import RetrievalLog

    since = datetime.now(timezone.utc) - timedelta(days=since_days)

    query = (
        select(
            RetrievalLog.top_score,
            RetrievalLog.result_count,
            RetrievalLog.fallback_triggered,
            RetrievalLog.handoff_triggered,
            RetrievalLog.detected_language,
            RetrievalLog.top_k,
        )
        .where(RetrievalLog.created_at >= since)
        .limit(sample_limit)
        .order_by(RetrievalLog.created_at.desc())
    )

    if company_id:
        try:
            cid = uuid_lib.UUID(company_id)
            query = query.where(RetrievalLog.company_id == cid)
        except ValueError:
            logger.warning("Invalid company_id %r; not filtering by company", company_id)

    result = await db.execute(query)
    rows = result.fetchall()

    if not rows:
        logger.info("No retrieval logs found for the specified period.")
        return {"total": 0, "period_days": since_days}

    total = len(rows)
    fallback_count = sum(1 for r in rows if r.fallback_triggered)
    handoff_count = sum(1 for r in rows if r.handoff_triggered)
    no_result_count = sum(1 for r in rows if (r.result_count or 0) == 0)

    # Score statistics
    valid_scores = [
        r.top_score for r in rows
        if r.top_score is not None and not math.isnan(float(r.top_score or 0))
    ]
    low_confidence_count = sum(
        1 for s in valid_scores if s < score_threshold
    )

    score_dist: Dict[str, Any] = {}
    if valid_scores:
        sorted_scores = sorted(valid_scores)
        n = len(sorted_scores)

        def pct(p: float) -> float:
            idx = p * (n - 1)
            lo = int(idx)
            hi = min(lo + 1, n - 1)
            frac = idx - lo
            return sorted_scores[lo] * (1 - frac) + sorted_scores[hi] * frac

        score_dist = {
            "min": sorted_scores[0],
            "p25": pct(0.25),
            "median": pct(0.50),
            "p75": pct(0.75),
            "p90": pct(0.90),
            "max": sorted_scores[-1],
            "mean": sum(sorted_scores) / n,
            "n": n,
        }

    # Top-K distribution
    topk_dist: Dict[int, int] = {}
    for r in rows:
        k = r.result_count or 0
        topk_dist[k] = topk_dist.get(k, 0) + 1

    # Language distribution
    lang_dist: Dict[str, int] = {}
    for r in rows:
        lang = r.detected_language or "unknown"
        lang_dist[lang] = lang_dist.get(lang, 0) + 1

    metrics = {
        "total": total,
        "period_days": since_days,
        "score_threshold": score_threshold,
        "fallback_rate": fallback_count / total,
        "fallback_count": fallback_count,
        "handoff_rate": handoff_count / total,
        "handoff_count": handoff_count,
        "no_result_rate": no_result_count / total,
        "no_result_count": no_result_count,
        "low_confidence_rate": low_confidence_count / total if total else 0.0,
        "low_confidence_count": low_confidence_count,
        "score_distribution": score_dist,
        "top_k_distribution": topk_dist,
        "language_distribution": lang_dist,
    }

    logger.info(
        "Production metrics (%d logs, %d days): fallback=%.1f%% low_conf=%.1f%%",
        total,
        since_days,
        metrics["fallback_rate"] * 100,
        metrics["low_confidence_rate"] * 100,
    )

    return metrics


async def sample_production_queries(
    db,
    *,
    company_id: Optional[str] = None,
    since_days: int = 30,
    limit: int = 100,
    seed: int = 42,
    only_fallbacks: bool = False,
) -> List[Dict[str, Any]]:
    """
    Sample production queries for offline evaluation.

    Returns a list of dicts suitable for constructing DatasetItems.
    The sample is pseudo-random (seeded) so it is reproducible.

    IMPORTANT: This function returns QUERY TEXT.  Before using sampled
    queries for offline evaluation with an external LLM judge, ensure this
    is consistent with your data handling / privacy policy.

    Args:
        db:             SQLAlchemy AsyncSession.
        company_id:     Filter by company UUID string.
        since_days:     Look-back window in days.
        limit:          Max samples to return.
        seed:           Random seed for reproducibility.
        only_fallbacks: If True, only sample queries that triggered fallback.
    """
    import random
    import uuid as uuid_lib
    from sqlalchemy import select
    from app.models.retrieval_log import RetrievalLog

    since = datetime.now(timezone.utc) - timedelta(days=since_days)

    query = (
        select(
            RetrievalLog.id,
            RetrievalLog.query_text,
            RetrievalLog.detected_language,
            RetrievalLog.top_score,
            RetrievalLog.result_count,
            RetrievalLog.fallback_triggered,
            RetrievalLog.created_at,
        )
        .where(RetrievalLog.created_at >= since)
        .order_by(RetrievalLog.created_at.desc())
        .limit(limit * 5)  # oversample then shuffle
    )

    if company_id:
        try:
            cid = uuid_lib.UUID(company_id)
            query = query.where(RetrievalLog.company_id == cid)
        except ValueError:
            pass

    if only_fallbacks:
        query = query.where(RetrievalLog.fallback_triggered.is_(True))

    result = await db.execute(query)
    rows = result.fetchall()

    rng = random.Random(seed)
    rng.shuffle(rows)
    sampled = rows[:limit]

    return [
        {
            "id": f"prod_{str(r.id)[:8]}",
            "question": r.query_text,
            "language": r.detected_language or "english",
            "category": "factual_lookup",
            "difficulty": "unknown",
            "answerable": not r.fallback_triggered,
            "metadata": {
                "source": "production_log",
                "top_score": r.top_score,
                "result_count": r.result_count,
                "sampled_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        for r in sampled
    ]
