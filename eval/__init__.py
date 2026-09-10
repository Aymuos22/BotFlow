"""
RAG Evaluation Framework for BotFlow.

Layered evaluation architecture:

  Retrieval layer   — deterministic metrics: Recall@K, MRR, NDCG, Precision@K
  Generation layer  — token-level F1 (deterministic) + LLM-as-judge (semantic)
  Failure taxonomy  — systematic classification of failure modes
  Regression runner — compare eval runs, detect regressions
  Quality gates     — configurable thresholds; non-zero exit code on failure
  Report generator  — JSON + human-readable reports with worst/best examples

Entry point: ``eval.cli`` — run via  ``python -m eval.cli``
"""

__version__ = "1.0.0"
