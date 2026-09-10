"""
Evaluation report generator.

Produces:
  1. Machine-readable JSON report (eval/reports/<run_id>.json)
  2. Human-readable text report  (eval/reports/<run_id>.txt)

Report sections:
  1.  Executive summary
  2.  Dataset statistics
  3.  Retrieval metrics
  4.  Generation metrics
  5.  LLM judge results
  6.  Failure distribution
  7.  Human vs LLM judge agreement (if labels exist)
  8.  Regression comparison (if baseline provided)
  9.  Latency statistics
  10. Worst-performing examples (lowest faithfulness + recall)
  11. Best-performing examples
  12. Recommended improvements

The worst/best examples section is critical for debugging — it shows actual
questions, retrieved context, expected and generated answers, and failure types.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).parent / "reports"


async def load_run_results(db, run_id: str) -> tuple[Optional[Any], List[Any]]:
    """
    Load EvalRun and all EvalResult rows for a run.

    Returns:
        (eval_run, list_of_eval_results)
    """
    from sqlalchemy import select
    from app.models.eval_run import EvalRun
    from app.models.eval_result import EvalResult

    run_result = await db.execute(
        select(EvalRun).where(EvalRun.run_id == run_id)
    )
    eval_run = run_result.scalar_one_or_none()
    if eval_run is None:
        return None, []

    results_query = await db.execute(
        select(EvalResult)
        .where(EvalResult.run_id == eval_run.id)
        .order_by(EvalResult.created_at)
    )
    results = list(results_query.scalars().all())
    return eval_run, results


def build_report(
    eval_run: Any,
    eval_results: List[Any],
    *,
    regression_comparison: Optional[Dict[str, Any]] = None,
    calibration_stats: Optional[Dict[str, Any]] = None,
    n_worst: int = 10,
    n_best: int = 5,
) -> Dict[str, Any]:
    """
    Build the full report dict from loaded DB objects.

    This function is pure (no I/O) so it is easy to test.
    """
    aggregate = eval_run.aggregate_metrics or {}
    failure_counts = eval_run.failure_counts or {}

    # ── 1. Executive summary ────────────────────────────────────────── #
    recall5 = aggregate.get("recall@5")
    faithfulness = aggregate.get("faithfulness_score")
    correctness = aggregate.get("correctness_score")
    fallback_rate = (aggregate.get("failure_rates") or {}).get("fallback_failure", 0.0)

    summary = {
        "run_id": eval_run.run_id,
        "status": eval_run.status,
        "dataset_version": eval_run.dataset_version,
        "total_examples": eval_run.total_examples,
        "completed_at": eval_run.completed_at.isoformat() if eval_run.completed_at else None,
        "git_commit": eval_run.git_commit,
        "experiment_name": eval_run.experiment_name,
        "headline_metrics": {
            "recall@5": _fmt(recall5),
            "faithfulness": _fmt(faithfulness),
            "correctness": _fmt(correctness),
            "fallback_rate": _fmt(fallback_rate),
        },
    }

    # ── 2. Dataset statistics ────────────────────────────────────────── #
    categories: Dict[str, int] = {}
    languages: Dict[str, int] = {}
    for r in eval_results:
        c = r.category or "unknown"
        l = r.language or "unknown"
        categories[c] = categories.get(c, 0) + 1
        languages[l] = languages.get(l, 0) + 1

    dataset_stats = {
        "total": len(eval_results),
        "answerable": sum(1 for r in eval_results if r.answerable),
        "unanswerable": sum(1 for r in eval_results if not r.answerable),
        "with_judge_scores": sum(1 for r in eval_results if r.faithfulness_score is not None),
        "categories": categories,
        "languages": languages,
    }

    # ── 3. Retrieval metrics ─────────────────────────────────────────── #
    retrieval_metrics = {
        k: _fmt(v)
        for k, v in aggregate.items()
        if any(k.startswith(p) for p in ("recall", "precision", "mrr", "ndcg", "hit_rate"))
    }

    # Score distribution from results
    scores = [r.avg_retrieval_score for r in eval_results if r.avg_retrieval_score is not None]
    if scores:
        sorted_s = sorted(scores)
        n = len(sorted_s)
        retrieval_metrics["score_distribution"] = {
            "min": round(sorted_s[0], 4),
            "median": round(sorted_s[n // 2], 4),
            "max": round(sorted_s[-1], 4),
            "mean": round(sum(sorted_s) / n, 4),
        }

    # ── 4. Generation metrics ────────────────────────────────────────── #
    generation_metrics = {
        k: _fmt(v)
        for k, v in aggregate.items()
        if k in ("token_f1", "exact_match", "context_coverage", "answer_length_chars")
    }

    # ── 5. LLM judge results ─────────────────────────────────────────── #
    judge_results = {
        "faithfulness": _fmt(aggregate.get("faithfulness_score")),
        "correctness": _fmt(aggregate.get("correctness_score")),
        "relevance": _fmt(aggregate.get("relevance_score")),
        "judge_model": eval_run.judge_model,
        "judge_prompt_version": eval_run.judge_prompt_version,
        "n_scored": sum(1 for r in eval_results if r.faithfulness_score is not None),
    }

    # ── 6. Failure distribution ──────────────────────────────────────── #
    total = len(eval_results) or 1
    failure_rates = {
        ft: round(count / total, 4)
        for ft, count in failure_counts.items()
        if count > 0
    }
    failure_section = {
        "counts": {k: v for k, v in failure_counts.items() if v > 0},
        "rates": failure_rates,
    }

    # ── 7. Human calibration ─────────────────────────────────────────── #
    calibration_section = calibration_stats or {}

    # ── 8. Regression ───────────────────────────────────────────────── #
    regression_section = regression_comparison or {}

    # ── 9. Latency ──────────────────────────────────────────────────── #
    latencies = [r.total_latency_ms for r in eval_results if r.total_latency_ms is not None]
    latency_section: Dict[str, Any] = {}
    if latencies:
        s = sorted(latencies)
        n = len(s)
        latency_section = {
            "min_ms": s[0],
            "median_ms": s[n // 2],
            "p90_ms": s[int(n * 0.9)],
            "max_ms": s[-1],
            "mean_ms": round(sum(s) / n),
        }

    # ── 10-11. Worst / best examples ────────────────────────────────── #
    scored_results = [r for r in eval_results if r.faithfulness_score is not None]
    retrieval_scored = [r for r in eval_results if r.recall_at_5 is not None]

    worst = _worst_examples(scored_results, retrieval_scored, n=n_worst)
    best = _best_examples(scored_results, n=n_best)

    # ── 12. Recommendations ─────────────────────────────────────────── #
    recommendations = _generate_recommendations(aggregate, failure_counts, total)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executive_summary": summary,
        "dataset_statistics": dataset_stats,
        "retrieval_metrics": retrieval_metrics,
        "generation_metrics": generation_metrics,
        "judge_results": judge_results,
        "failure_distribution": failure_section,
        "calibration": calibration_section,
        "regression": regression_section,
        "latency": latency_section,
        "worst_examples": worst,
        "best_examples": best,
        "recommendations": recommendations,
    }


def write_report(
    report: Dict[str, Any],
    run_id: str,
    output_dir: Optional[Path] = None,
) -> tuple[Path, Path]:
    """
    Write JSON and text reports to disk.

    Returns:
        Tuple of (json_path, text_path).
    """
    out_dir = output_dir or _REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"{run_id}.json"
    txt_path = out_dir / f"{run_id}.txt"

    json_path.write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    txt_path.write_text(_render_text_report(report), encoding="utf-8")

    logger.info("Report written: %s", json_path)
    logger.info("Report written: %s", txt_path)
    return json_path, txt_path


def _render_text_report(report: Dict[str, Any]) -> str:
    """Render the report dict as a human-readable text report."""
    lines: List[str] = []
    _h1(lines, "RAG EVALUATION REPORT")

    # Executive summary
    summary = report.get("executive_summary", {})
    _h2(lines, "1. Executive Summary")
    lines.append(f"  Run ID:            {summary.get('run_id')}")
    lines.append(f"  Status:            {summary.get('status')}")
    lines.append(f"  Dataset version:   {summary.get('dataset_version')}")
    lines.append(f"  Total examples:    {summary.get('total_examples')}")
    lines.append(f"  Git commit:        {summary.get('git_commit', 'N/A')}")
    lines.append(f"  Completed at:      {summary.get('completed_at', 'N/A')}")
    hm = summary.get("headline_metrics", {})
    lines.append("")
    lines.append("  Headline metrics:")
    for k, v in hm.items():
        lines.append(f"    {k:<25} {v}")

    # Dataset stats
    ds = report.get("dataset_statistics", {})
    _h2(lines, "2. Dataset Statistics")
    lines.append(f"  Total: {ds.get('total')}  answerable={ds.get('answerable')}  "
                 f"unanswerable={ds.get('unanswerable')}")
    _kv_block(lines, "  Categories", ds.get("categories", {}))
    _kv_block(lines, "  Languages", ds.get("languages", {}))

    # Retrieval metrics
    rm = report.get("retrieval_metrics", {})
    _h2(lines, "3. Retrieval Metrics")
    for k, v in sorted(rm.items()):
        if k != "score_distribution":
            lines.append(f"  {k:<30} {v}")
    if "score_distribution" in rm:
        _kv_block(lines, "  Score distribution", rm["score_distribution"])

    # Generation metrics
    gm = report.get("generation_metrics", {})
    _h2(lines, "4. Generation Metrics")
    for k, v in sorted(gm.items()):
        lines.append(f"  {k:<30} {v}")

    # Judge results
    jr = report.get("judge_results", {})
    _h2(lines, "5. LLM Judge Results")
    lines.append(f"  Judge model:       {jr.get('judge_model', 'N/A')}")
    lines.append(f"  Prompt version:    {jr.get('judge_prompt_version', 'N/A')}")
    lines.append(f"  Scored examples:   {jr.get('n_scored', 0)}")
    for dim in ("faithfulness", "correctness", "relevance"):
        lines.append(f"  {dim:<25} {jr.get(dim, 'N/A')}")

    # Failure distribution
    fd = report.get("failure_distribution", {})
    _h2(lines, "6. Failure Distribution")
    for ft, rate in sorted((fd.get("rates") or {}).items(), key=lambda x: -x[1]):
        count = (fd.get("counts") or {}).get(ft, 0)
        lines.append(f"  {ft:<35} {rate:.1%}  (n={count})")
    if not fd.get("rates"):
        lines.append("  No failures detected.")

    # Calibration
    cal = report.get("calibration", {})
    if cal and cal.get("n_total_labels", 0) > 0:
        _h2(lines, "7. Human vs LLM Judge Calibration")
        lines.append(f"  Labelled examples: {cal.get('n_total_labels', 0)}")
        for dim in ("faithfulness", "correctness", "relevance", "overall"):
            d = cal.get(dim, {})
            if d and d.get("n", 0) > 0:
                lines.append(
                    f"  {dim:<15} exact={d.get('exact_agreement_rate', 0):.1%}  "
                    f"±1={d.get('tolerant_agreement_rate', 0):.1%}  "
                    f"r={d.get('pearson_r', 0):.3f}"
                )

    # Regression
    reg = report.get("regression", {})
    if reg:
        _h2(lines, "8. Regression Comparison")
        lines.append(reg.get("summary", "(no regression data)"))

    # Latency
    lat = report.get("latency", {})
    if lat:
        _h2(lines, "9. Latency")
        for k, v in sorted(lat.items()):
            lines.append(f"  {k:<25} {v}ms")

    # Worst examples
    worst = report.get("worst_examples", [])
    if worst:
        _h2(lines, "10. Worst-Performing Examples")
        for i, ex in enumerate(worst, 1):
            lines.append(f"\n  [{i}] {ex.get('dataset_item_id')}  "
                         f"(recall@5={ex.get('recall_at_5', 'N/A')}  "
                         f"faithfulness={ex.get('faithfulness_score', 'N/A')})")
            lines.append(f"  Question:  {ex.get('question', '')[:200]}")
            if ex.get("expected_answer"):
                lines.append(f"  Expected:  {ex['expected_answer'][:200]}")
            if ex.get("generated_answer"):
                lines.append(f"  Generated: {ex['generated_answer'][:200]}")
            if ex.get("failure_types"):
                lines.append(f"  Failures:  {', '.join(ex['failure_types'])}")
            if ex.get("faithfulness_reason"):
                lines.append(f"  Judge:     {ex['faithfulness_reason'][:200]}")

    # Best examples
    best = report.get("best_examples", [])
    if best:
        _h2(lines, "11. Best-Performing Examples")
        for i, ex in enumerate(best, 1):
            lines.append(f"\n  [{i}] {ex.get('dataset_item_id')}  "
                         f"(recall@5={ex.get('recall_at_5', 'N/A')}  "
                         f"faithfulness={ex.get('faithfulness_score', 'N/A')})")
            lines.append(f"  Question:  {ex.get('question', '')[:200]}")

    # Recommendations
    recs = report.get("recommendations", [])
    if recs:
        _h2(lines, "12. Recommended Improvements")
        for rec in recs:
            lines.append(f"  • {rec}")

    lines.append("")
    lines.append(f"Report generated: {report.get('generated_at')}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────── #
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────── #


def _worst_examples(
    scored: List[Any], retrieval_scored: List[Any], n: int
) -> List[Dict[str, Any]]:
    """Return the N worst examples ranked by composite badness score."""
    def badness(r) -> float:
        f = r.faithfulness_score if r.faithfulness_score is not None else 0.5
        rc = r.recall_at_5 if r.recall_at_5 is not None else 0.5
        return -(f + rc)  # lower combined score = worse

    all_scored = list(set(scored + retrieval_scored))
    ranked = sorted(all_scored, key=badness)[:n]
    return [_result_to_dict(r) for r in ranked]


def _best_examples(scored: List[Any], n: int) -> List[Dict[str, Any]]:
    def goodness(r) -> float:
        f = r.faithfulness_score if r.faithfulness_score is not None else 0.0
        rc = r.recall_at_5 if r.recall_at_5 is not None else 0.0
        return f + rc

    ranked = sorted(scored, key=goodness, reverse=True)[:n]
    return [_result_to_dict(r) for r in ranked]


def _result_to_dict(r: Any) -> Dict[str, Any]:
    return {
        "dataset_item_id": r.dataset_item_id,
        "question": r.question,
        "expected_answer": r.expected_answer,
        "generated_answer": r.generated_answer,
        "recall_at_5": _fmt(r.recall_at_5),
        "mrr": _fmt(r.mrr),
        "faithfulness_score": _fmt(r.faithfulness_score),
        "correctness_score": _fmt(r.correctness_score),
        "relevance_score": _fmt(r.relevance_score),
        "faithfulness_reason": r.faithfulness_reason,
        "token_f1": _fmt(r.token_f1),
        "failure_types": r.failure_types or [],
        "language": r.language,
        "category": r.category,
    }


def _generate_recommendations(
    aggregate: Dict[str, Any],
    failure_counts: Dict[str, int],
    total: int,
) -> List[str]:
    recs: List[str] = []
    total = total or 1

    recall5 = aggregate.get("recall@5") or 0
    if recall5 < 0.8:
        recs.append(
            f"Retrieval recall@5 is {recall5:.1%} (below 80%). "
            "Consider: larger top-K, enabling vector embeddings, or improving chunking strategy."
        )

    faithfulness = aggregate.get("faithfulness_score") or 0
    if faithfulness < 0.8:
        recs.append(
            f"Faithfulness is {faithfulness:.1%} (below 80%). "
            "Review system prompt to emphasize grounding in context. "
            "Check for retrieval failures causing LLM to fall back on parametric knowledge."
        )

    hallucination_count = failure_counts.get("hallucination", 0)
    if hallucination_count / total > 0.05:
        recs.append(
            f"Hallucination rate {hallucination_count / total:.1%} exceeds 5%. "
            "Add explicit context-only instruction to system prompt."
        )

    wrong_doc = failure_counts.get("wrong_document", 0)
    if wrong_doc / total > 0.1:
        recs.append(
            f"Wrong document rate {wrong_doc / total:.1%} exceeds 10%. "
            "Enable vector embeddings or review document chunking overlap."
        )

    fallback = (aggregate.get("failure_rates") or {}).get("fallback_failure", 0)
    if fallback > 0.15:
        recs.append(
            f"Fallback rate {fallback:.1%} exceeds 15%. "
            "Lower the score threshold or expand the knowledge base."
        )

    if not recs:
        recs.append("All key metrics are within acceptable ranges. No immediate improvements needed.")

    return recs


def _fmt(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 4)
    return v


def _h1(lines: List[str], title: str) -> None:
    sep = "=" * 70
    lines.extend(["", sep, f"  {title}", sep, ""])


def _h2(lines: List[str], title: str) -> None:
    lines.extend(["", f"── {title} ─────────────────────────────────────────"])


def _kv_block(lines: List[str], label: str, d: Dict) -> None:
    if not d:
        return
    lines.append(f"{label}:")
    for k, v in sorted(d.items()):
        lines.append(f"    {k:<30} {v}")
