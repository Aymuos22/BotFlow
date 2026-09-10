"""
Evaluation CLI.

Entry point: ``python -m eval.cli``

Commands:
  run           Run offline evaluation against the golden dataset
  report        Generate a report for a completed run
  compare       Compare two eval runs (regression detection)
  gate-check    Check quality gates for a run (exits 1 if any gate fails)
  prod-metrics  Show production log quality metrics
  sample-prod   Sample production queries and output them as YAML dataset items

Examples:
  # Run evaluation (requires EVAL_COMPANY_ID + DATABASE_URL + LLM keys)
  python -m eval.cli run \\
      --dataset eval/data/golden_dataset_v1.yaml \\
      --company-id 550e8400-e29b-41d4-a716-446655440000 \\
      --judge

  # Generate report
  python -m eval.cli report --run-id run_20260910_abc123

  # Compare with baseline and check gates
  python -m eval.cli compare \\
      --current run_20260910_abc123 \\
      --baseline run_20260901_def456

  # Quality gate check (exits 1 on failure — use in CI)
  python -m eval.cli gate-check --run-id run_20260910_abc123

  # Production metrics
  python -m eval.cli prod-metrics --days 7
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Use argparse (stdlib) to avoid adding a click/typer dependency.
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("eval.cli")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.cli",
        description="RAG Evaluation Framework CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── run ──────────────────────────────────────────────────────────── #
    p_run = sub.add_parser("run", help="Run offline evaluation over the golden dataset")
    p_run.add_argument("--dataset", default=None, help="Path to golden dataset YAML")
    p_run.add_argument("--company-id", default=None, help="Company UUID to evaluate")
    p_run.add_argument("--judge", action="store_true", default=True,
                       help="Enable LLM judge (default: on)")
    p_run.add_argument("--no-judge", dest="judge", action="store_false",
                       help="Disable LLM judge")
    p_run.add_argument("--experiment-name", default=None)
    p_run.add_argument("--top-k", type=int, default=5)
    p_run.add_argument("--hybrid-alpha", type=float, default=0.5)
    p_run.add_argument("--score-threshold", type=float, default=0.4)
    p_run.add_argument("--dataset-version", default="v1")
    p_run.add_argument("--gate-check", action="store_true", default=False,
                       help="Run quality gate check after evaluation (exits 1 on failure)")
    p_run.add_argument("--baseline-run-id", default=None,
                       help="Compare against this baseline run ID after evaluation")

    # ── report ───────────────────────────────────────────────────────── #
    p_report = sub.add_parser("report", help="Generate report for a completed run")
    p_report.add_argument("--run-id", required=True)
    p_report.add_argument("--output-dir", default=None)
    p_report.add_argument("--baseline-run-id", default=None)

    # ── compare ──────────────────────────────────────────────────────── #
    p_compare = sub.add_parser("compare", help="Compare two eval runs")
    p_compare.add_argument("--current", required=True, help="Current run ID")
    p_compare.add_argument("--baseline", required=True, help="Baseline run ID")
    p_compare.add_argument("--tolerance", type=float, default=0.02)

    # ── gate-check ───────────────────────────────────────────────────── #
    p_gate = sub.add_parser("gate-check", help="Check quality gates (exits 1 on failure)")
    p_gate.add_argument("--run-id", required=True)
    p_gate.add_argument("--gates-config", default=None)

    # ── prod-metrics ─────────────────────────────────────────────────── #
    p_prod = sub.add_parser("prod-metrics", help="Show production log metrics")
    p_prod.add_argument("--company-id", default=None)
    p_prod.add_argument("--days", type=int, default=7)
    p_prod.add_argument("--threshold", type=float, default=0.4)

    # ── sample-prod ──────────────────────────────────────────────────── #
    p_sample = sub.add_parser("sample-prod", help="Sample production queries for annotation")
    p_sample.add_argument("--company-id", default=None)
    p_sample.add_argument("--days", type=int, default=30)
    p_sample.add_argument("--limit", type=int, default=50)
    p_sample.add_argument("--only-fallbacks", action="store_true")
    p_sample.add_argument("--output", default="eval/data/sampled_queries.yaml")

    return parser


async def _cmd_run(args) -> int:
    """Execute the 'run' command."""
    from eval.config import EvalConfig
    from eval.runner.offline import OfflineEvalRunner
    from eval.gates import check_quality_gates
    from eval.regression import compare_runs, load_run_metrics

    config = EvalConfig(
        dataset_path=Path(args.dataset) if args.dataset else None,
        dataset_version=args.dataset_version,
        company_id=args.company_id,
        retrieval_top_k=args.top_k,
        hybrid_alpha=args.hybrid_alpha,
        score_threshold=args.score_threshold,
        judge_enabled=args.judge,
        experiment_name=args.experiment_name,
    )

    async with _get_db() as db:
        rag = _get_rag_service(db, config)
        llm = _get_llm_client()

        runner = OfflineEvalRunner(config, rag, llm, db)
        run_id = await runner.run()
        print(f"\nEval run complete: {run_id}")

        exit_code = 0

        if args.gate_check:
            from sqlalchemy import select
            from app.models.eval_run import EvalRun
            result = await db.execute(select(EvalRun).where(EvalRun.run_id == run_id))
            eval_run = result.scalar_one_or_none()
            if eval_run and eval_run.aggregate_metrics:
                gate_result = check_quality_gates(
                    eval_run.aggregate_metrics, config.quality_gates
                )
                print(gate_result.summary())
                if not gate_result.passed:
                    exit_code = 1

        if args.baseline_run_id:
            baseline_metrics = await load_run_metrics(db, args.baseline_run_id)
            current_metrics_row = await load_run_metrics(db, run_id)
            if baseline_metrics and current_metrics_row:
                comparison = compare_runs(
                    args.baseline_run_id, baseline_metrics,
                    run_id, current_metrics_row,
                )
                print("\n" + comparison["summary"])
                if comparison["has_regressions"]:
                    exit_code = 1

    return exit_code


async def _cmd_report(args) -> int:
    from eval.report import load_run_results, build_report, write_report
    from eval.regression import load_run_metrics, compare_runs
    from eval.human_labels import compute_calibration_stats

    async with _get_db() as db:
        eval_run, results = await load_run_results(db, args.run_id)
        if eval_run is None:
            print(f"Run {args.run_id!r} not found.", file=sys.stderr)
            return 1

        regression_comparison = None
        if args.baseline_run_id:
            baseline_m = await load_run_metrics(db, args.baseline_run_id)
            current_m = eval_run.aggregate_metrics or {}
            if baseline_m:
                regression_comparison = compare_runs(
                    args.baseline_run_id, baseline_m,
                    args.run_id, current_m,
                )

        calibration = await compute_calibration_stats(db, run_id=args.run_id)

        report = build_report(
            eval_run, results,
            regression_comparison=regression_comparison,
            calibration_stats=calibration,
        )
        out_dir = Path(args.output_dir) if args.output_dir else None
        json_path, txt_path = write_report(report, args.run_id, out_dir)
        print(f"JSON report: {json_path}")
        print(f"Text report: {txt_path}")

        # Print executive summary to stdout
        summary = report.get("executive_summary", {})
        print(f"\nHeadline metrics for {args.run_id}:")
        for k, v in (summary.get("headline_metrics") or {}).items():
            print(f"  {k:<25} {v}")

    return 0


async def _cmd_compare(args) -> int:
    from eval.regression import load_run_metrics, compare_runs, format_regression_table

    async with _get_db() as db:
        baseline_m = await load_run_metrics(db, args.baseline)
        current_m = await load_run_metrics(db, args.current)

    if baseline_m is None:
        print(f"Baseline run {args.baseline!r} not found.", file=sys.stderr)
        return 1
    if current_m is None:
        print(f"Current run {args.current!r} not found.", file=sys.stderr)
        return 1

    comparison = compare_runs(
        args.baseline, baseline_m,
        args.current, current_m,
        tolerance=args.tolerance,
    )
    print(format_regression_table(comparison))
    print("\n" + comparison["summary"])
    return 1 if comparison["has_regressions"] else 0


async def _cmd_gate_check(args) -> int:
    from eval.config import load_quality_gates
    from eval.gates import check_quality_gates
    from sqlalchemy import select
    from app.models.eval_run import EvalRun

    gates_path = Path(args.gates_config) if args.gates_config else None
    gates = load_quality_gates(gates_path)

    async with _get_db() as db:
        result = await db.execute(select(EvalRun).where(EvalRun.run_id == args.run_id))
        eval_run = result.scalar_one_or_none()

    if eval_run is None:
        print(f"Run {args.run_id!r} not found.", file=sys.stderr)
        return 1

    gate_result = check_quality_gates(eval_run.aggregate_metrics or {}, gates)
    print(gate_result.summary())
    return gate_result.exit_code


async def _cmd_prod_metrics(args) -> int:
    import json
    from eval.runner.production import compute_production_metrics

    async with _get_db() as db:
        metrics = await compute_production_metrics(
            db,
            company_id=args.company_id,
            since_days=args.days,
            score_threshold=args.threshold,
        )

    print(json.dumps(metrics, indent=2, default=str))
    return 0


async def _cmd_sample_prod(args) -> int:
    import yaml
    from eval.runner.production import sample_production_queries

    async with _get_db() as db:
        samples = await sample_production_queries(
            db,
            company_id=args.company_id,
            since_days=args.days,
            limit=args.limit,
            only_fallbacks=args.only_fallbacks,
        )

    output = {
        "version": "sampled",
        "note": "Review and annotate before using as golden dataset items.",
        "items": samples,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.dump(output, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Sampled {len(samples)} queries -> {out_path}")
    return 0


# ─────────────────────────────────────────────────────────────────────────── #
# Helpers
# ─────────────────────────────────────────────────────────────────────────── #


def _get_db():
    """Return an async context manager for an AsyncSession."""
    import contextlib
    from app.core.database import AsyncSessionLocal

    @contextlib.asynccontextmanager
    async def _ctx():
        async with AsyncSessionLocal() as session:
            yield session

    return _ctx()


def _get_llm_client():
    """Return the configured LLM client."""
    from app.integrations.llm.client import get_llm_client
    return get_llm_client()


def _get_rag_service(db, config):
    """Build a RAGService using the application's DI wiring."""
    from app.integrations.weaviate.client import get_weaviate_client
    from app.integrations.embeddings.client import get_embedding_client
    from app.integrations.llm.client import get_llm_client
    from app.repositories.company_config_repository import CompanyConfigRepository
    from app.services.fallback_service import FallbackService
    from app.services.rag_service import RAGService

    return RAGService(
        config_repo=CompanyConfigRepository(db),
        weaviate_client=get_weaviate_client(),
        llm_client=get_llm_client(),
        fallback_service=FallbackService(),
        default_top_k=config.retrieval_top_k,
        default_hybrid_alpha=config.hybrid_alpha,
        default_score_threshold=config.score_threshold,
        embedding_client=get_embedding_client(),
    )


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    handlers = {
        "run": _cmd_run,
        "report": _cmd_report,
        "compare": _cmd_compare,
        "gate-check": _cmd_gate_check,
        "prod-metrics": _cmd_prod_metrics,
        "sample-prod": _cmd_sample_prod,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    exit_code = asyncio.run(handler(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
