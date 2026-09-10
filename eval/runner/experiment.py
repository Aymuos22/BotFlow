"""
Experiment comparison framework.

Enables A/B comparison of RAG configurations:
  - embedding model versions
  - hybrid alpha (BM25 vs vector balance)
  - top-K
  - chunking strategies
  - reranker variants
  - LLM models

Usage:
    experiments = [
        ExperimentConfig(name="baseline", embedding_model=None, hybrid_alpha=0.5),
        ExperimentConfig(name="with_voyage3", embedding_model="voyage-3", hybrid_alpha=0.7),
    ]
    results = await compare_experiments(experiments, dataset, rag_factory, db)
    print(format_comparison_table(results))

Each experiment runs as a separate OfflineEvalRunner invocation (separate EvalRun rows),
so results are stored in the database and can be queried later.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment."""

    name: str
    embedding_model: Optional[str] = None
    hybrid_alpha: float = 0.5
    retrieval_top_k: int = 5
    score_threshold: float = 0.4
    confidence_strategy: str = "top"
    llm_model: Optional[str] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Results from one experiment run."""

    name: str
    run_id: str
    aggregate_metrics: Dict[str, Any]
    total_examples: int
    latency_ms_mean: Optional[float] = None
    error: Optional[str] = None


def compare_experiments(
    results: List[ExperimentResult],
    *,
    baseline_name: str,
    metrics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Compare experiment results against a baseline.

    Args:
        results:        List of ExperimentResult objects.
        baseline_name:  Name of the baseline experiment.
        metrics:        Which metrics to compare (defaults to key retrieval + generation metrics).

    Returns:
        Dict with:
          - table: list of rows [{name, metric1, metric2, ...}]
          - regressions: list of {experiment, metric, baseline, current, delta}
          - baseline_name: str
    """
    if metrics is None:
        metrics = [
            "recall@5", "mrr", "ndcg@5",
            "faithfulness_score", "correctness_score", "relevance_score",
            "token_f1",
        ]

    baseline = next((r for r in results if r.name == baseline_name), None)
    baseline_metrics: Dict[str, Any] = baseline.aggregate_metrics if baseline else {}

    table: List[Dict[str, Any]] = []
    regressions: List[Dict[str, Any]] = []

    for result in results:
        row: Dict[str, Any] = {"name": result.name, "run_id": result.run_id}
        for metric in metrics:
            val = result.aggregate_metrics.get(metric)
            row[metric] = round(val, 4) if isinstance(val, float) else val
        if result.latency_ms_mean is not None:
            row["latency_ms"] = round(result.latency_ms_mean, 1)
        table.append(row)

        # Detect regressions vs baseline
        if result.name != baseline_name and baseline_metrics:
            for metric in metrics:
                current = result.aggregate_metrics.get(metric)
                base = baseline_metrics.get(metric)
                if current is None or base is None:
                    continue
                delta = current - base
                # Higher is better for recall/faithfulness/correctness/relevance
                # Regression if current is worse than baseline by > epsilon
                if delta < -0.01:
                    regressions.append({
                        "experiment": result.name,
                        "metric": metric,
                        "baseline": round(base, 4),
                        "current": round(current, 4),
                        "delta": round(delta, 4),
                    })

    return {
        "baseline_name": baseline_name,
        "table": table,
        "regressions": regressions,
        "metrics": metrics,
    }


def format_comparison_table(comparison: Dict[str, Any]) -> str:
    """
    Format the comparison as a human-readable ASCII table.

    Example output:

    Configuration          recall@5   mrr      ndcg@5   faithful  correct
    ─────────────────────────────────────────────────────────────────────
    baseline               0.8200     0.7100   0.7500   0.8000    0.7500
    with_voyage3           0.9100     0.8500   0.8800   0.8900    0.8600  ✓
    """
    table = comparison.get("table", [])
    metrics = comparison.get("metrics", [])
    baseline_name = comparison.get("baseline_name", "")
    regressions_set = {
        (r["experiment"], r["metric"]) for r in comparison.get("regressions", [])
    }

    if not table:
        return "(no results)"

    col_width = 10
    name_width = max(20, max(len(r["name"]) for r in table) + 2)

    # Header
    header = f"{'Configuration':<{name_width}}"
    for m in metrics:
        short = _shorten_metric(m)
        header += f"  {short:>{col_width}}"
    if any("latency_ms" in r for r in table):
        header += f"  {'latency_ms':>{col_width}}"

    sep = "─" * len(header)
    lines = [header, sep]

    for row in table:
        is_baseline = row["name"] == baseline_name
        line = f"{row['name']:<{name_width}}"
        for m in metrics:
            val = row.get(m)
            cell = f"{val:.4f}" if isinstance(val, float) else str(val or "")
            marker = " ↓" if (row["name"], m) in regressions_set else "  "
            line += f"{marker}{cell:>{col_width}}"
        if "latency_ms" in row:
            line += f"  {row['latency_ms']:>{col_width}}"
        if is_baseline:
            line += "  (baseline)"
        lines.append(line)

    return "\n".join(lines)


def _shorten_metric(metric: str) -> str:
    """Abbreviate metric name for table display."""
    shorten = {
        "faithfulness_score": "faithful",
        "correctness_score": "correct",
        "relevance_score": "relevant",
        "token_f1": "tok_f1",
        "avg_retrieval_score": "avg_score",
    }
    return shorten.get(metric, metric)
