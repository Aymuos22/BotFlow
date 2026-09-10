"""
Evaluation configuration.

Reads from:
  1. eval/config/quality_gates.yaml  — configurable thresholds
  2. Environment variables            — DB, LLM, Weaviate connections (reuse app settings)
  3. Function arguments               — per-run overrides

Design rationale: quality gate thresholds are in YAML (not env vars) so they
can be version-controlled and code-reviewed like any other configuration change.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_GATES_PATH = Path(__file__).parent / "config" / "quality_gates.yaml"

# ─────────────────────────────────────────────────────────────────────────── #
# Quality gate defaults (used when YAML is absent or missing a key)
# ─────────────────────────────────────────────────────────────────────────── #
_DEFAULT_GATES: Dict[str, Any] = {
    "retrieval_recall_at_5": {"minimum": 0.80},
    "retrieval_mrr": {"minimum": 0.75},
    "retrieval_ndcg_at_5": {"minimum": 0.75},
    "faithfulness": {"minimum": 0.80},
    "correctness": {"minimum": 0.75},
    "relevance": {"minimum": 0.80},
    "max_hallucination_rate": {"maximum": 0.10},
    "max_fallback_rate": {"maximum": 0.20},
    "max_regression": {"maximum": 0.03},
}

# ─────────────────────────────────────────────────────────────────────────── #
# Judge configuration
# ─────────────────────────────────────────────────────────────────────────── #
JUDGE_PROMPT_VERSION = "v1"
JUDGE_DEFAULT_MAX_RETRIES = 2
JUDGE_TIMEOUT_SECONDS = 30

# ─────────────────────────────────────────────────────────────────────────── #
# Scoring rubric (shared between prompts and agreement calculation)
# ─────────────────────────────────────────────────────────────────────────── #
SCORE_MIN = 0
SCORE_MAX = 4
SCORE_LABELS = {
    0: "completely incorrect / hallucinated",
    1: "mostly incorrect",
    2: "partially correct",
    3: "mostly correct",
    4: "fully correct / grounded",
}

# Normalised 0-1 score (score / SCORE_MAX)
def normalise_score(raw: int) -> float:
    """Convert a 0-4 judge score to a 0.0-1.0 float."""
    return max(0.0, min(1.0, raw / SCORE_MAX))


def load_quality_gates(path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load quality gate configuration from YAML.

    Falls back to ``_DEFAULT_GATES`` for any missing key so a partial YAML
    is still valid.
    """
    gates = dict(_DEFAULT_GATES)
    gates_path = path or _DEFAULT_GATES_PATH

    if gates_path.exists():
        try:
            raw = yaml.safe_load(gates_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "quality_gates" in raw:
                for k, v in raw["quality_gates"].items():
                    if isinstance(v, dict):
                        gates[k] = v
            logger.debug("Loaded quality gates from %s", gates_path)
        except Exception as exc:
            logger.warning(
                "Failed to load quality gates from %s: %s; using defaults",
                gates_path,
                exc,
            )
    else:
        logger.debug(
            "Quality gates file not found at %s; using defaults", gates_path
        )

    return gates


class EvalConfig:
    """
    Runtime configuration for a single evaluation run.

    Parameters are passed explicitly so the config is testable without
    environment variable side-effects.
    """

    def __init__(
        self,
        *,
        # Dataset
        dataset_path: Optional[Path] = None,
        dataset_version: str = "v1",
        # System under test
        company_id: Optional[str] = None,
        embedding_model: Optional[str] = None,
        retrieval_top_k: int = 5,
        hybrid_alpha: float = 0.5,
        score_threshold: float = 0.4,
        confidence_strategy: str = "top",
        llm_model: Optional[str] = None,
        prompt_version: str = "v1",
        # Judge
        judge_model: Optional[str] = None,
        judge_prompt_version: str = JUDGE_PROMPT_VERSION,
        judge_enabled: bool = True,
        # Experiment
        experiment_name: Optional[str] = None,
        git_commit: Optional[str] = None,
        # Gates
        gates_path: Optional[Path] = None,
    ) -> None:
        self.dataset_path = dataset_path or (
            Path(__file__).parent / "data" / "golden_dataset_v1.yaml"
        )
        self.dataset_version = dataset_version
        self.company_id = company_id or os.environ.get("EVAL_COMPANY_ID")
        self.embedding_model = embedding_model
        self.retrieval_top_k = retrieval_top_k
        self.hybrid_alpha = hybrid_alpha
        self.score_threshold = score_threshold
        self.confidence_strategy = confidence_strategy
        self.llm_model = llm_model or os.environ.get("LLM_MODEL")
        self.prompt_version = prompt_version
        self.judge_model = judge_model or os.environ.get(
            "EVAL_JUDGE_MODEL", self.llm_model
        )
        self.judge_prompt_version = judge_prompt_version
        self.judge_enabled = judge_enabled
        self.experiment_name = experiment_name
        self.git_commit = git_commit or _read_git_commit()
        self.quality_gates = load_quality_gates(gates_path)

    def retrieval_config_dict(self) -> Dict[str, Any]:
        return {
            "top_k": self.retrieval_top_k,
            "hybrid_alpha": self.hybrid_alpha,
            "score_threshold": self.score_threshold,
            "confidence_strategy": self.confidence_strategy,
        }


def _read_git_commit() -> Optional[str]:
    """Try to read the current git HEAD commit (short SHA)."""
    try:
        import subprocess  # noqa: S404
        result = subprocess.run(  # noqa: S603 S607
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None
