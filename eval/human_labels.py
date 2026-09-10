"""
Human calibration — store and compare human vs LLM-judge labels.

Provides:
  - Functions to load human labels from the database
  - Agreement statistics between human labels and LLM judge scores
  - Calibration report generation

Usage:
    stats = await compute_calibration_stats(db, run_id=run_id)
    print(format_calibration_report(stats))
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def compute_calibration_stats(
    db,
    *,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute LLM-judge vs human agreement statistics.

    For each labelled dimension (faithfulness, correctness, relevance), returns:
      - n: number of labelled examples
      - exact_agreement_rate: fraction with identical score
      - tolerant_agreement_rate: fraction within ±1 point
      - mean_abs_diff: mean absolute difference
      - pearson_r: Pearson correlation coefficient

    Args:
        db:       AsyncSession.
        run_id:   Optional filter to one eval run.

    Returns:
        Dict with per-dimension stats + overall stats.
    """
    from sqlalchemy import select
    from app.models.eval_result import EvalResult
    from app.models.human_label import HumanLabel
    from app.models.eval_run import EvalRun
    from eval.judge.llm_judge import judge_vs_human_agreement

    # Join eval_results with human_labels
    query = (
        select(
            EvalResult.faithfulness_score,
            EvalResult.correctness_score,
            EvalResult.relevance_score,
            HumanLabel.faithfulness.label("h_faithfulness"),
            HumanLabel.correctness.label("h_correctness"),
            HumanLabel.relevance.label("h_relevance"),
        )
        .join(HumanLabel, HumanLabel.eval_result_id == EvalResult.id)
    )

    if run_id:
        run_subq = select(EvalRun.id).where(EvalRun.run_id == run_id).scalar_subquery()
        query = query.where(EvalResult.run_id == run_subq)

    result = await db.execute(query)
    rows = result.fetchall()

    if not rows:
        return {"n": 0, "message": "No human labels found"}

    dims = {
        "faithfulness": (
            [_scale_to_4(r.faithfulness_score) for r in rows if r.faithfulness_score is not None],
            [r.h_faithfulness for r in rows if r.h_faithfulness is not None and r.faithfulness_score is not None],
        ),
        "correctness": (
            [_scale_to_4(r.correctness_score) for r in rows if r.correctness_score is not None],
            [r.h_correctness for r in rows if r.h_correctness is not None and r.correctness_score is not None],
        ),
        "relevance": (
            [_scale_to_4(r.relevance_score) for r in rows if r.relevance_score is not None],
            [r.h_relevance for r in rows if r.h_relevance is not None and r.relevance_score is not None],
        ),
    }

    stats: Dict[str, Any] = {"n_total_labels": len(rows)}
    for dim_name, (judge_scores, human_scores) in dims.items():
        if not judge_scores or not human_scores:
            stats[dim_name] = {"n": 0}
            continue
        agreement = judge_vs_human_agreement(
            judge_scores, human_scores, tolerance=1
        )
        stats[dim_name] = agreement

    # Overall agreement across all three dimensions
    all_judge = []
    all_human = []
    for dim_name, (judge_scores, human_scores) in dims.items():
        all_judge.extend(judge_scores)
        all_human.extend(human_scores)

    if all_judge and all_human:
        from eval.judge.llm_judge import judge_vs_human_agreement as jha
        stats["overall"] = jha(all_judge, all_human, tolerance=1)

    return stats


def format_calibration_report(stats: Dict[str, Any]) -> str:
    """Format calibration stats as a human-readable string."""
    if stats.get("n") == 0:
        return "No human labels available for calibration."

    lines = [
        "=== LLM Judge vs Human Calibration ===",
        f"Total labelled examples: {stats.get('n_total_labels', 0)}",
        "",
    ]

    for dim in ("faithfulness", "correctness", "relevance", "overall"):
        dim_stats = stats.get(dim, {})
        if not dim_stats or dim_stats.get("n", 0) == 0:
            continue
        n = dim_stats.get("n", 0)
        exact = dim_stats.get("exact_agreement_rate", 0)
        tolerant = dim_stats.get("tolerant_agreement_rate", 0)
        mad = dim_stats.get("mean_abs_diff", 0)
        pearson = dim_stats.get("pearson_r")
        pearson_str = f"{pearson:.3f}" if pearson is not None else "N/A"
        lines.append(f"  {dim.upper():<15}  n={n:<5}  exact={exact:.1%}  "
                     f"±1={tolerant:.1%}  MAD={mad:.2f}  r={pearson_str}")

    lines.append("")
    lines.append(
        "Interpretation: exact ≥ 70% and ±1 ≥ 90% indicates a well-calibrated judge."
    )
    return "\n".join(lines)


def _scale_to_4(normalised: float) -> int:
    """Convert a normalised 0.0-1.0 score back to the 0-4 integer scale."""
    return round(normalised * 4)
