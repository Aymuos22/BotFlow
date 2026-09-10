"""
Regression detection.

Compares the current eval run against a baseline run.

A regression is detected when a metric that should be high (recall, faithfulness,
etc.) decreases by more than ``tolerance``.

The comparison is persisted in the EvalRun record so historical regression
reports are available in the database.

Usage:
    baseline = await load_run(db, baseline_run_id)
    current = await load_run(db, current_run_id)
    report = compare_runs(baseline, current, gates=gates)
    if report["has_regressions"]:
        sys.exit(1)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Metrics where higher is better (all of these are "higher = better")
_HIGHER_IS_BETTER = frozenset(
    [
        "recall@1", "recall@3", "recall@5", "recall@10",
        "precision@1", "precision@3", "precision@5",
        "mrr", "ndcg@5", "ndcg@10",
        "hit_rate@5",
        "token_f1",
        "faithfulness_score", "correctness_score", "relevance_score",
        "context_coverage",
    ]
)

# Metrics where lower is better (a regression = current > baseline + tolerance)
_LOWER_IS_BETTER = frozenset(
    [
        "failure_rates.hallucination",
        "failure_rates.incorrect_answer",
        "failure_rates.wrong_document",
        "failure_rates.wrong_chunk",
    ]
)

# Default tolerance: differences smaller than this are not reported as regressions.
# Rationale: small statistical fluctuations on a small dataset should not
# gate a deployment.  Set this higher for small datasets.
_DEFAULT_TOLERANCE = 0.02


async def load_run_metrics(db, run_id: str) -> Optional[Dict[str, Any]]:
    """
    Load aggregate metrics for a completed eval run.

    Returns:
        Dict of aggregate metrics, or None if the run is not found.
    """
    from sqlalchemy import select
    from app.models.eval_run import EvalRun

    result = await db.execute(
        select(EvalRun).where(EvalRun.run_id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        logger.warning("Run %r not found in database", run_id)
        return None
    return run.aggregate_metrics or {}


async def load_latest_completed_run_metrics(
    db,
    *,
    experiment_name: Optional[str] = None,
    dataset_version: Optional[str] = None,
) -> Optional[tuple[str, Dict[str, Any]]]:
    """
    Load metrics from the most recent completed eval run.

    Args:
        experiment_name:   Filter by experiment name (optional).
        dataset_version:   Filter by dataset version (optional).

    Returns:
        Tuple of (run_id, metrics_dict), or None.
    """
    from sqlalchemy import select
    from app.models.eval_run import EvalRun

    query = (
        select(EvalRun)
        .where(EvalRun.status.in_(["completed", "completed_with_errors"]))
        .order_by(EvalRun.completed_at.desc())
        .limit(1)
    )
    if experiment_name:
        query = query.where(EvalRun.experiment_name == experiment_name)
    if dataset_version:
        query = query.where(EvalRun.dataset_version == dataset_version)

    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        return None
    return (run.run_id, run.aggregate_metrics or {})


def compare_runs(
    baseline_run_id: str,
    baseline_metrics: Dict[str, Any],
    current_run_id: str,
    current_metrics: Dict[str, Any],
    *,
    tolerance: float = _DEFAULT_TOLERANCE,
    key_metrics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Compare current eval run against a baseline.

    Args:
        baseline_run_id:    Identifier of the baseline run.
        baseline_metrics:   Aggregate metrics from the baseline run.
        current_run_id:     Identifier of the current run.
        current_metrics:    Aggregate metrics from the current run.
        tolerance:          Minimum change to report as regression.
        key_metrics:        Which metrics to compare (defaults to all shared keys).

    Returns:
        Dict with:
          - has_regressions: bool
          - regressions:     list of regression dicts
          - improvements:    list of improvement dicts
          - comparison_table: list of (metric, baseline, current, delta, status) rows
          - summary:         human-readable summary string
    """
    if key_metrics is None:
        key_metrics = sorted(
            set(baseline_metrics.keys()) & set(current_metrics.keys())
            & (_HIGHER_IS_BETTER | _LOWER_IS_BETTER)
        )

    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []
    comparison_rows: List[Dict[str, Any]] = []

    for metric in key_metrics:
        base_val = baseline_metrics.get(metric)
        curr_val = current_metrics.get(metric)

        if not isinstance(base_val, (int, float)) or not isinstance(curr_val, (int, float)):
            continue

        base_f = float(base_val)
        curr_f = float(curr_val)
        delta = curr_f - base_f

        # Add a small epsilon so that floating-point imprecision in differences
        # that are exactly at the boundary do not cause spurious regressions.
        _eps = 1e-9
        if metric in _HIGHER_IS_BETTER:
            is_regression = delta < -(tolerance + _eps)
            is_improvement = delta > (tolerance + _eps)
        elif metric in _LOWER_IS_BETTER:
            is_regression = delta > (tolerance + _eps)
            is_improvement = delta < -(tolerance + _eps)
        else:
            is_regression = False
            is_improvement = False

        status = "regression" if is_regression else ("improvement" if is_improvement else "unchanged")
        row = {
            "metric": metric,
            "baseline": round(base_f, 4),
            "current": round(curr_f, 4),
            "delta": round(delta, 4),
            "delta_pct": round(delta / (abs(base_f) + 1e-9) * 100, 2),
            "status": status,
        }
        comparison_rows.append(row)

        if is_regression:
            regressions.append(row)
        elif is_improvement:
            improvements.append(row)

    has_regressions = len(regressions) > 0

    summary_lines = [
        f"Regression comparison: {current_run_id} vs baseline {baseline_run_id}",
        f"  Regressions:  {len(regressions)}",
        f"  Improvements: {len(improvements)}",
        f"  Tolerance:    {tolerance:.3f}",
    ]
    if regressions:
        summary_lines.append("\nREGRESSIONS DETECTED:")
        for r in regressions:
            summary_lines.append(
                f"  {r['metric']:<30}  baseline={r['baseline']:.4f}  "
                f"current={r['current']:.4f}  delta={r['delta']:+.4f}  "
                f"({r['delta_pct']:+.1f}%)"
            )

    return {
        "has_regressions": has_regressions,
        "regressions": regressions,
        "improvements": improvements,
        "comparison_table": comparison_rows,
        "summary": "\n".join(summary_lines),
        "baseline_run_id": baseline_run_id,
        "current_run_id": current_run_id,
        "tolerance": tolerance,
    }


def format_regression_table(comparison: Dict[str, Any]) -> str:
    """
    Format the comparison as an ASCII table.

    Example:
    Metric                         Baseline    Current     Delta
    ─────────────────────────────────────────────────────────────
    recall@5                       0.8200      0.9400      +0.1200  ↑
    mrr                            0.7100      0.7800      +0.0700  ↑
    faithfulness_score             0.9100      0.8800      -0.0300  ↓ REGRESSION
    """
    rows = comparison.get("comparison_table", [])
    if not rows:
        return "(no comparison data)"

    header = f"{'Metric':<35}  {'Baseline':>10}  {'Current':>10}  {'Delta':>10}  {'Status'}"
    sep = "─" * 80
    lines = [header, sep]

    for row in rows:
        marker = ""
        if row["status"] == "regression":
            marker = "  ↓ REGRESSION"
        elif row["status"] == "improvement":
            marker = "  ↑"
        lines.append(
            f"{row['metric']:<35}  {row['baseline']:>10.4f}  {row['current']:>10.4f}  "
            f"{row['delta']:>+10.4f}{marker}"
        )

    return "\n".join(lines)
