"""
Unit tests for eval/regression.py and eval/gates.py.

Tests cover:
  - compare_runs: improvements, regressions, unchanged, boundary conditions
  - format_regression_table: output structure
  - check_quality_gates: minimum violations, maximum violations, skipped gates
  - _get_nested: dot notation navigation
  - Edge cases: empty metrics, missing keys, tolerance boundary
"""
import pytest

from eval.regression import compare_runs, format_regression_table
from eval.gates import check_quality_gates, _get_nested, GateCheckResult


# ─────────────────────────────────────────────────────────────────────────── #
# compare_runs
# ─────────────────────────────────────────────────────────────────────────── #


class TestCompareRuns:
    def _baseline(self):
        return {
            "recall@5": 0.80,
            "mrr": 0.70,
            "ndcg@5": 0.75,
            "faithfulness_score": 0.85,
            "correctness_score": 0.80,
        }

    def test_no_regressions_when_better(self):
        current = {k: v + 0.05 for k, v in self._baseline().items()}
        result = compare_runs("baseline", self._baseline(), "current", current)
        assert result["has_regressions"] is False
        assert len(result["improvements"]) > 0

    def test_regression_detected(self):
        current = dict(self._baseline())
        current["recall@5"] = 0.70  # drop of 0.10 (above default tolerance 0.02)
        result = compare_runs("baseline", self._baseline(), "current", current)
        assert result["has_regressions"] is True
        reg_metrics = [r["metric"] for r in result["regressions"]]
        assert "recall@5" in reg_metrics

    def test_within_tolerance_no_regression(self):
        current = dict(self._baseline())
        current["recall@5"] = 0.79  # drop of 0.01 (below tolerance 0.02)
        result = compare_runs(
            "baseline", self._baseline(), "current", current, tolerance=0.02
        )
        assert result["has_regressions"] is False

    def test_exactly_at_tolerance_no_regression(self):
        # Use exact base 10 fractions to avoid floating-point precision issues.
        # Drop of exactly 0.05 with tolerance 0.05 should NOT be a regression.
        baseline = {"recall@5": 0.90, "mrr": 0.70}
        current = {"recall@5": 0.85, "mrr": 0.70}  # drop of exactly 0.05
        result = compare_runs(
            "baseline", baseline, "current", current, tolerance=0.05
        )
        # delta = -0.05, condition is delta < -0.05 → False → no regression
        assert result["has_regressions"] is False

    def test_just_over_tolerance_regression(self):
        current = dict(self._baseline())
        current["recall@5"] = 0.779  # drop of 0.021 (just over tolerance)
        result = compare_runs(
            "baseline", self._baseline(), "current", current, tolerance=0.02
        )
        assert result["has_regressions"] is True

    def test_multiple_regressions(self):
        current = {
            "recall@5": 0.60,   # -0.20
            "mrr": 0.50,         # -0.20
            "ndcg@5": 0.74,      # -0.01 within tolerance
            "faithfulness_score": 0.85,
            "correctness_score": 0.80,
        }
        result = compare_runs("baseline", self._baseline(), "current", current)
        reg_metrics = {r["metric"] for r in result["regressions"]}
        assert "recall@5" in reg_metrics
        assert "mrr" in reg_metrics
        assert "ndcg@5" not in reg_metrics  # within tolerance

    def test_empty_metrics_no_regressions(self):
        result = compare_runs("base", {}, "current", {})
        assert result["has_regressions"] is False
        assert result["comparison_table"] == []

    def test_comparison_table_structure(self):
        result = compare_runs("baseline", self._baseline(), "current", self._baseline())
        for row in result["comparison_table"]:
            assert "metric" in row
            assert "baseline" in row
            assert "current" in row
            assert "delta" in row
            assert "status" in row

    def test_run_ids_in_result(self):
        result = compare_runs("run_001", self._baseline(), "run_002", self._baseline())
        assert result["baseline_run_id"] == "run_001"
        assert result["current_run_id"] == "run_002"


class TestFormatRegressionTable:
    def test_renders_without_error(self):
        metrics = {"recall@5": 0.80, "mrr": 0.70}
        result = compare_runs("base", metrics, "curr", {"recall@5": 0.65, "mrr": 0.80})
        table = format_regression_table(result)
        assert "REGRESSION" in table
        assert "recall@5" in table
        assert "mrr" in table

    def test_empty_comparison(self):
        result = compare_runs("base", {}, "curr", {})
        table = format_regression_table(result)
        assert "no comparison data" in table


# ─────────────────────────────────────────────────────────────────────────── #
# check_quality_gates
# ─────────────────────────────────────────────────────────────────────────── #


class TestCheckQualityGates:
    def _default_gates(self):
        return {
            "retrieval_recall_at_5": {"minimum": 0.80},
            "faithfulness": {"minimum": 0.80},
            "max_hallucination_rate": {"maximum": 0.10},
        }

    def _passing_metrics(self):
        return {
            "recall@5": 0.90,
            "faithfulness_score": 0.85,
            "failure_rates": {"hallucination": 0.05},
        }

    def test_all_pass(self):
        result = check_quality_gates(self._passing_metrics(), self._default_gates())
        assert result.passed is True
        assert result.exit_code == 0
        assert len(result.violations) == 0

    def test_minimum_violation(self):
        metrics = dict(self._passing_metrics())
        metrics["recall@5"] = 0.70  # below minimum 0.80
        result = check_quality_gates(metrics, self._default_gates())
        assert result.passed is False
        assert result.exit_code == 1
        assert any(v.gate_name == "retrieval_recall_at_5" for v in result.violations)

    def test_maximum_violation(self):
        metrics = {
            "recall@5": 0.90,
            "faithfulness_score": 0.85,
            "failure_rates": {"hallucination": 0.15},  # above maximum 0.10
        }
        result = check_quality_gates(metrics, self._default_gates())
        assert result.passed is False
        assert any(v.gate_name == "max_hallucination_rate" for v in result.violations)

    def test_skipped_when_metric_missing(self):
        # metrics dict has no recall@5
        metrics = {"faithfulness_score": 0.90}
        result = check_quality_gates(metrics, {"retrieval_recall_at_5": {"minimum": 0.80}})
        assert "retrieval_recall_at_5" in result.skipped_gates
        assert result.passed is True  # no violations (gate was skipped)

    def test_violation_deficit_correct(self):
        metrics = {"recall@5": 0.70}
        gates = {"retrieval_recall_at_5": {"minimum": 0.80}}
        result = check_quality_gates(metrics, gates)
        violation = result.violations[0]
        assert violation.deficit == pytest.approx(0.10, abs=1e-6)
        assert violation.actual_value == pytest.approx(0.70)
        assert violation.threshold_value == pytest.approx(0.80)

    def test_max_regression_gate_skipped(self):
        # max_regression is handled by regression.py, not gates.py
        gates = {"max_regression": {"maximum": 0.02}}
        result = check_quality_gates({"recall@5": 0.50}, gates)
        assert result.passed is True  # max_regression gate is ignored here

    def test_boundary_exactly_at_minimum(self):
        # Exactly at minimum = pass
        metrics = {"recall@5": 0.80}
        result = check_quality_gates(metrics, {"retrieval_recall_at_5": {"minimum": 0.80}})
        assert result.passed is True

    def test_gate_check_result_summary(self):
        metrics = {"recall@5": 0.70}
        gates = {"retrieval_recall_at_5": {"minimum": 0.80}}
        result = check_quality_gates(metrics, gates)
        summary = result.summary()
        assert "FAILED" in summary
        assert "retrieval_recall_at_5" in summary


# ─────────────────────────────────────────────────────────────────────────── #
# _get_nested
# ─────────────────────────────────────────────────────────────────────────── #


class TestGetNested:
    def test_top_level(self):
        assert _get_nested({"a": 0.5}, "a") == pytest.approx(0.5)

    def test_nested(self):
        d = {"failure_rates": {"hallucination": 0.05}}
        assert _get_nested(d, "failure_rates.hallucination") == pytest.approx(0.05)

    def test_missing_key_returns_none(self):
        assert _get_nested({"a": 1}, "b") is None

    def test_missing_nested_key_returns_none(self):
        assert _get_nested({"a": {}}, "a.b") is None

    def test_non_numeric_returns_none(self):
        assert _get_nested({"a": "string"}, "a") is None

    def test_integer_value(self):
        assert _get_nested({"a": 3}, "a") == pytest.approx(3.0)
