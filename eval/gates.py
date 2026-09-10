"""
Quality gate checker.

Validates eval run aggregate metrics against configurable thresholds.
Returns a ``GateCheckResult`` that contains:
  - whether all gates passed
  - which gates failed and by how much
  - an exit code (0 = pass, 1 = fail)

Callers (CLI, CI/CD) should call ``sys.exit(result.exit_code)`` to propagate
the failure to the build pipeline.

Gate configuration (eval/config/quality_gates.yaml):

    quality_gates:
      retrieval_recall_at_5:
        minimum: 0.90
      faithfulness:
        minimum: 0.90
      max_hallucination_rate:
        maximum: 0.05
      max_regression:
        maximum: 0.02       # applied during regression check, not here

Rationale for defaults:
  - 0.80 recall@5: A retrieval system that misses 20%+ of relevant documents
    needs significant improvement before going to production.
  - 0.80 faithfulness: More than 20% hallucination rate is unacceptable for a
    customer-facing product chatbot.
  - 0.10 max_hallucination_rate: Up to 10% hallucination is the tolerance
    for initial deployment (tighten after calibration).
  - 0.20 max_fallback_rate: More than 20% fallback rate suggests the knowledge
    base needs expansion.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GateViolation:
    """One failed quality gate."""

    gate_name: str
    threshold_type: str  # "minimum" or "maximum"
    threshold_value: float
    actual_value: float
    deficit: float       # How far from the threshold (positive = bad)
    message: str


@dataclass
class GateCheckResult:
    """Result of checking all quality gates."""

    passed: bool
    violations: List[GateViolation] = field(default_factory=list)
    passed_gates: List[str] = field(default_factory=list)
    skipped_gates: List[str] = field(default_factory=list)  # metric not in run metrics

    @property
    def exit_code(self) -> int:
        """0 if all gates passed, 1 if any gate failed."""
        return 0 if self.passed else 1

    def summary(self) -> str:
        lines = [
            f"Quality gate check: {'PASSED' if self.passed else 'FAILED'}",
            f"  Violations: {len(self.violations)}",
            f"  Passed:     {len(self.passed_gates)}",
            f"  Skipped:    {len(self.skipped_gates)} (metric not in run)",
        ]
        if self.violations:
            lines.append("\nVIOLATED GATES:")
            for v in self.violations:
                lines.append(f"  {v.gate_name:<35}  {v.threshold_type}={v.threshold_value:.4f}  "
                             f"actual={v.actual_value:.4f}  deficit={v.deficit:.4f}")
        return "\n".join(lines)


# Mapping from gate name to the metric key in the aggregate metrics dict
_GATE_TO_METRIC: Dict[str, str] = {
    "retrieval_recall_at_5":  "recall@5",
    "retrieval_recall_at_3":  "recall@3",
    "retrieval_mrr":          "mrr",
    "retrieval_ndcg_at_5":    "ndcg@5",
    "faithfulness":           "faithfulness_score",
    "correctness":            "correctness_score",
    "relevance":              "relevance_score",
    "token_f1":               "token_f1",
    # Failure rate gates use nested keys in aggregate_metrics["failure_rates"]
    "max_hallucination_rate": "failure_rates.hallucination",
    "max_fallback_rate":      "failure_rates.fallback_failure",
    "max_wrong_document_rate": "failure_rates.wrong_document",
}


def check_quality_gates(
    aggregate_metrics: Dict[str, Any],
    quality_gates: Dict[str, Any],
) -> GateCheckResult:
    """
    Check all configured quality gates against aggregate metrics.

    Args:
        aggregate_metrics:  Dict from ``EvalRun.aggregate_metrics``.
        quality_gates:      Dict loaded by ``load_quality_gates()``.

    Returns:
        ``GateCheckResult`` — caller should check ``.passed`` and ``.exit_code``.
    """
    violations: List[GateViolation] = []
    passed: List[str] = []
    skipped: List[str] = []

    for gate_name, gate_config in quality_gates.items():
        if gate_name == "max_regression":
            # Regression gates are handled separately in regression.py
            continue

        if not isinstance(gate_config, dict):
            continue

        metric_key = _GATE_TO_METRIC.get(gate_name, gate_name)
        actual = _get_nested(aggregate_metrics, metric_key)

        if actual is None:
            skipped.append(gate_name)
            logger.debug("Gate %r skipped: metric %r not in run metrics", gate_name, metric_key)
            continue

        actual_f = float(actual)

        if "minimum" in gate_config:
            threshold = float(gate_config["minimum"])
            if actual_f < threshold:
                deficit = threshold - actual_f
                violations.append(GateViolation(
                    gate_name=gate_name,
                    threshold_type="minimum",
                    threshold_value=threshold,
                    actual_value=actual_f,
                    deficit=deficit,
                    message=(
                        f"{gate_name}: actual {actual_f:.4f} < minimum {threshold:.4f} "
                        f"(deficit {deficit:.4f})"
                    ),
                ))
                logger.warning("Gate FAILED: %s", violations[-1].message)
            else:
                passed.append(gate_name)
                logger.debug("Gate passed: %s = %.4f >= %.4f", gate_name, actual_f, threshold)

        if "maximum" in gate_config:
            threshold = float(gate_config["maximum"])
            if actual_f > threshold:
                deficit = actual_f - threshold
                violations.append(GateViolation(
                    gate_name=gate_name,
                    threshold_type="maximum",
                    threshold_value=threshold,
                    actual_value=actual_f,
                    deficit=deficit,
                    message=(
                        f"{gate_name}: actual {actual_f:.4f} > maximum {threshold:.4f} "
                        f"(excess {deficit:.4f})"
                    ),
                ))
                logger.warning("Gate FAILED: %s", violations[-1].message)
            else:
                passed.append(gate_name)
                logger.debug("Gate passed: %s = %.4f <= %.4f", gate_name, actual_f, threshold)

    result = GateCheckResult(
        passed=len(violations) == 0,
        violations=violations,
        passed_gates=passed,
        skipped_gates=skipped,
    )

    if result.passed:
        logger.info("All quality gates passed (%d gates, %d skipped)", len(passed), len(skipped))
    else:
        logger.error(
            "Quality gates FAILED: %d violation(s) | %s",
            len(violations),
            ", ".join(v.gate_name for v in violations),
        )

    return result


def _get_nested(d: Dict[str, Any], key: str) -> Optional[float]:
    """
    Get a possibly nested value using dot notation.

    e.g. ``_get_nested(d, "failure_rates.hallucination")``
    navigates ``d["failure_rates"]["hallucination"]``.
    """
    parts = key.split(".", 1)
    val = d.get(parts[0])
    if val is None:
        return None
    if len(parts) == 1:
        return float(val) if isinstance(val, (int, float)) else None
    if isinstance(val, dict):
        return _get_nested(val, parts[1])
    return None
