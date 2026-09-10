"""
Offline evaluation runner.

Orchestrates a full end-to-end evaluation pass over a golden dataset:

  1. Load dataset from YAML.
  2. Create an EvalRun record in the database.
  3. For each dataset item:
       a. Call the RAG pipeline (live Weaviate + LLM).
       b. Compute deterministic retrieval metrics.
       c. Compute deterministic generation metrics.
       d. Run LLM judge (if enabled).
       e. Assign failure types.
       f. Persist EvalResult to the database.
  4. Compute aggregate metrics.
  5. Update EvalRun with aggregates + completion status.
  6. Return the run ID.

The runner is designed to be fault-tolerant: a single item failure does NOT
abort the run.  Failed items are recorded with their error and the run
continues.

Usage:
    runner = OfflineEvalRunner(config, rag_service, weaviate_client, llm_client, db)
    run_id = await runner.run()
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OfflineEvalRunner:
    """
    Runs offline evaluation over a golden dataset.

    All dependencies are injected so the runner is fully testable.

    Args:
        config:           EvalConfig instance.
        rag_service:      RAGService (or compatible mock).
        llm_client:       LLMClientProtocol for the judge (may differ from RAG LLM).
        db:               SQLAlchemy AsyncSession for persisting results.
        judge:            Optional pre-built JudgeProtocol; built from llm_client if None.
        run_id_override:  Override the auto-generated run ID (useful in tests).
    """

    def __init__(
        self,
        config,        # EvalConfig
        rag_service,   # RAGService
        llm_client,    # LLMClientProtocol
        db,            # AsyncSession
        *,
        judge=None,    # Optional JudgeProtocol
        run_id_override: Optional[str] = None,
    ) -> None:
        self._config = config
        self._rag = rag_service
        self._llm = llm_client
        self._db = db
        self._run_id_override = run_id_override

        if judge is None and config.judge_enabled:
            from eval.judge.llm_judge import LLMJudge
            self._judge = LLMJudge(
                llm_client,
                prompt_version=config.judge_prompt_version,
                judge_model_name=config.judge_model,
            )
        else:
            self._judge = judge

    async def run(self) -> str:
        """
        Execute the full evaluation run.

        Returns:
            run_id string (e.g. ``run_20260910_abc123``).
        """
        from eval.config import EvalConfig
        from eval.dataset import load_dataset
        from eval.metrics.retrieval import compute_retrieval_metrics, aggregate_retrieval_metrics
        from eval.metrics.generation import compute_generation_metrics, aggregate_generation_metrics
        from eval.taxonomy import (
            assign_retrieval_failures,
            assign_system_failures,
            assign_generation_failures_heuristic,
            failure_rate_summary,
            aggregate_failure_counts,
        )
        from app.models.eval_run import EvalRun
        from app.models.eval_result import EvalResult

        # ── 1. Load dataset ────────────────────────────────────────────── #
        dataset = load_dataset(self._config.dataset_path)
        logger.info(
            "Starting eval run: dataset=%r items=%d",
            dataset.version,
            len(dataset),
        )

        # ── 2. Create EvalRun record ───────────────────────────────────── #
        run_id = self._run_id_override or _make_run_id()
        eval_run = EvalRun(
            run_id=run_id,
            dataset_version=dataset.version,
            embedding_model=self._config.embedding_model,
            retrieval_config=self._config.retrieval_config_dict(),
            llm_model=self._config.llm_model,
            prompt_version=self._config.prompt_version,
            judge_model=self._config.judge_model,
            judge_prompt_version=self._config.judge_prompt_version,
            git_commit=self._config.git_commit,
            experiment_name=self._config.experiment_name,
            status="running",
        )
        self._db.add(eval_run)
        await self._db.flush()
        logger.info("Created eval run: run_id=%r db_id=%s", run_id, eval_run.id)

        # ── 3. Evaluate each item ──────────────────────────────────────── #
        all_retrieval_metrics: List[Dict[str, Any]] = []
        all_generation_metrics: List[Dict[str, Any]] = []
        all_failure_lists: List[List[str]] = []
        completed = 0
        failed = 0

        for item in dataset:
            t_start = time.monotonic()
            try:
                result = await self._evaluate_item(
                    item,
                    eval_run_id=eval_run.id,
                )
                self._db.add(result)
                await self._db.flush()

                # Collect per-item metrics for aggregation
                all_retrieval_metrics.append(
                    {k: getattr(result, _DB_KEY.get(k, k), None)
                     for k in _RETRIEVAL_KEYS}
                )
                all_generation_metrics.append(
                    {k: getattr(result, _DB_KEY.get(k, k), None)
                     for k in _GENERATION_KEYS}
                )
                all_failure_lists.append(result.failure_types or [])
                completed += 1

            except Exception as exc:
                logger.error(
                    "Item %r failed: %s", item.id, exc, exc_info=True
                )
                failed += 1
                # Persist a partial result so we know what failed
                error_result = EvalResult(
                    run_id=eval_run.id,
                    dataset_item_id=item.id,
                    question=item.question,
                    expected_answer=item.expected_answer,
                    category=item.category,
                    difficulty=item.difficulty,
                    language=item.language,
                    answerable=item.answerable,
                    failure_types=["system_error"],
                )
                self._db.add(error_result)
                try:
                    await self._db.flush()
                except Exception:
                    pass

            elapsed = int((time.monotonic() - t_start) * 1000)
            logger.info(
                "Item %r done in %dms (%d/%d)", item.id, elapsed, completed + failed, len(dataset)
            )

        # ── 4. Aggregate metrics ───────────────────────────────────────── #
        agg_retrieval = aggregate_retrieval_metrics(all_retrieval_metrics)  # type: ignore[arg-type]
        agg_generation = aggregate_generation_metrics(all_generation_metrics)  # type: ignore[arg-type]
        failure_rates = failure_rate_summary(all_failure_lists, len(dataset))
        failure_counts = aggregate_failure_counts(all_failure_lists)

        aggregate = {**agg_retrieval, **agg_generation, "failure_rates": failure_rates}

        # ── 5. Update EvalRun ──────────────────────────────────────────── #
        eval_run.status = "completed" if failed == 0 else "completed_with_errors"
        eval_run.total_examples = len(dataset)
        eval_run.aggregate_metrics = aggregate
        eval_run.failure_counts = failure_counts
        eval_run.completed_at = datetime.now(timezone.utc)
        await self._db.commit()

        logger.info(
            "Eval run %r completed: %d succeeded, %d failed", run_id, completed, failed
        )
        _log_aggregate_summary(run_id, aggregate)

        return run_id

    async def _evaluate_item(self, item, *, eval_run_id: uuid.UUID):
        """Evaluate a single dataset item and return an EvalResult (not yet persisted)."""
        from eval.metrics.retrieval import compute_retrieval_metrics
        from eval.metrics.generation import compute_generation_metrics
        from eval.taxonomy import (
            assign_retrieval_failures,
            assign_system_failures,
            assign_generation_failures_heuristic,
        )
        from eval.judge.protocol import JudgeError
        from app.models.eval_result import EvalResult

        company_id = _parse_company_id(self._config.company_id)

        # ── Retrieval ──────────────────────────────────────────────────── #
        t_retrieval_start = time.monotonic()
        response = await self._rag.process_query(
            company_id=company_id,
            query=item.question,
        )
        retrieval_ms = int((time.monotonic() - t_retrieval_start) * 1000)

        # Extract retrieved chunk IDs and scores from sources
        sources = response.get("sources") or []
        retrieved_chunk_ids = _chunk_ids_from_sources(sources)
        retrieved_doc_ids = list({
            s["document_id"] for s in sources if s.get("document_id")
        })
        retrieval_scores = [
            float(s["score"]) for s in sources if s.get("score") is not None
        ]
        search_mode = None  # RAGService doesn't expose this currently

        retrieval_metrics = compute_retrieval_metrics(
            relevant_chunk_ids=item.relevant_chunk_ids,
            retrieved_chunk_ids=retrieved_chunk_ids,
            retrieval_scores=retrieval_scores,
            relevance_grades=item.relevance_grades or None,
        )

        # ── Generation ────────────────────────────────────────────────── #
        t_gen_start = time.monotonic()
        generated_answer = response.get("answer", "")
        gen_ms = int((time.monotonic() - t_gen_start) * 1000)

        # Collect raw chunk text for context coverage metric
        retrieved_chunk_texts = [s.get("chunk_text", "") for s in sources if s.get("chunk_text")]
        gen_metrics = compute_generation_metrics(
            generated_answer=generated_answer,
            expected_answer=item.expected_answer,
            retrieved_chunks=retrieved_chunk_texts or None,
        )

        # ── Failure assignment ────────────────────────────────────────── #
        retrieval_failures = assign_retrieval_failures(
            relevant_chunk_ids=item.relevant_chunk_ids,
            relevant_document_ids=item.relevant_document_ids,
            retrieved_chunk_ids=retrieved_chunk_ids,
            top_k=self._config.retrieval_top_k,
            answerable=item.answerable,
        )
        system_failures = assign_system_failures(response, answerable=item.answerable)
        gen_heuristic_failures = assign_generation_failures_heuristic(
            generated_answer=generated_answer,
            expected_answer=item.expected_answer,
            retrieved_chunks=retrieved_chunk_texts,
            language=item.language,
        )
        all_failures = list(set(retrieval_failures + system_failures + gen_heuristic_failures))

        # ── LLM judge ─────────────────────────────────────────────────── #
        faithfulness_score = None
        faithfulness_reason = None
        correctness_score = None
        correctness_reason = None
        relevance_score = None
        relevance_reason = None
        judge_raw = None
        judge_model = None

        if self._judge is not None and generated_answer:
            context_text = "\n\n---\n\n".join(
                retrieved_chunk_texts or [s.get("chunk_text", "") for s in sources]
            )[:6000]
            try:
                judge_output = await self._judge.evaluate(
                    question=item.question,
                    retrieved_context=context_text,
                    generated_answer=generated_answer,
                    expected_answer=item.expected_answer,
                )
                faithfulness_score = judge_output.faithfulness.normalised
                faithfulness_reason = judge_output.faithfulness.reason
                correctness_score = judge_output.correctness.normalised
                correctness_reason = judge_output.correctness.reason
                relevance_score = judge_output.relevance.normalised
                relevance_reason = judge_output.relevance.reason
                judge_raw = judge_output.to_dict()
                judge_model = judge_output.judge_model

                # Add judge-detected failures
                if judge_output.faithfulness.failure_type:
                    all_failures.append(judge_output.faithfulness.failure_type)
                if judge_output.correctness.failure_type:
                    all_failures.append(judge_output.correctness.failure_type)
                if judge_output.relevance.failure_type:
                    all_failures.append(judge_output.relevance.failure_type)

            except JudgeError as exc:
                logger.warning("Judge failed for item %r: %s", item.id, exc)
                # Non-fatal: continue without judge scores

        return EvalResult(
            run_id=eval_run_id,
            dataset_item_id=item.id,
            question=item.question,
            expected_answer=item.expected_answer,
            category=item.category,
            difficulty=item.difficulty,
            language=item.language,
            answerable=item.answerable,
            relevant_document_ids=item.relevant_document_ids,
            relevant_chunk_ids=item.relevant_chunk_ids,
            relevance_grades=item.relevance_grades,
            retrieved_chunk_ids=retrieved_chunk_ids,
            retrieved_document_ids=retrieved_doc_ids,
            retrieval_scores=retrieval_scores,
            search_mode=search_mode,
            # Retrieval metrics
            recall_at_1=retrieval_metrics.get("recall@1"),
            recall_at_3=retrieval_metrics.get("recall@3"),
            recall_at_5=retrieval_metrics.get("recall@5"),
            recall_at_10=retrieval_metrics.get("recall@10"),
            precision_at_1=retrieval_metrics.get("precision@1"),
            precision_at_3=retrieval_metrics.get("precision@3"),
            precision_at_5=retrieval_metrics.get("precision@5"),
            mrr=retrieval_metrics.get("mrr"),
            ndcg_at_5=retrieval_metrics.get("ndcg@5"),
            ndcg_at_10=retrieval_metrics.get("ndcg@10"),
            hit_rate_at_5=retrieval_metrics.get("hit_rate@5"),
            avg_retrieval_score=retrieval_metrics.get("avg_retrieval_score"),
            # Generation
            generated_answer=generated_answer,
            response_type=response.get("response_type"),
            fallback_triggered=response.get("fallback_triggered"),
            token_f1=gen_metrics.get("token_f1"),
            answer_length_chars=int(gen_metrics["answer_length_chars"])
            if gen_metrics.get("answer_length_chars") is not None else None,
            # Judge
            faithfulness_score=faithfulness_score,
            faithfulness_reason=faithfulness_reason,
            correctness_score=correctness_score,
            correctness_reason=correctness_reason,
            relevance_score=relevance_score,
            relevance_reason=relevance_reason,
            judge_model=judge_model,
            judge_prompt_version=self._config.judge_prompt_version,
            judge_raw_response=judge_raw,
            # Failures
            failure_types=list(set(all_failures)) if all_failures else [],
            # Latency
            retrieval_latency_ms=retrieval_ms,
            total_latency_ms=retrieval_ms + gen_ms,
        )


# ─────────────────────────────────────────────────────────────────────────── #
# Helpers
# ─────────────────────────────────────────────────────────────────────────── #

# Map from metric key to EvalResult column name where they differ
_DB_KEY: Dict[str, str] = {
    "recall@1": "recall_at_1",
    "recall@3": "recall_at_3",
    "recall@5": "recall_at_5",
    "recall@10": "recall_at_10",
    "precision@1": "precision_at_1",
    "precision@3": "precision_at_3",
    "precision@5": "precision_at_5",
    "ndcg@5": "ndcg_at_5",
    "ndcg@10": "ndcg_at_10",
    "hit_rate@5": "hit_rate_at_5",
    "avg_retrieval_score": "avg_retrieval_score",
}

_RETRIEVAL_KEYS = [
    "recall@1", "recall@3", "recall@5", "recall@10",
    "precision@1", "precision@3", "precision@5",
    "mrr", "ndcg@5", "ndcg@10", "hit_rate@5",
]

_GENERATION_KEYS = [
    "token_f1", "exact_match", "answer_length_chars", "context_coverage",
    "faithfulness_score", "correctness_score", "relevance_score",
]


def _make_run_id() -> str:
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"run_{ts}_{short}"


def _parse_company_id(company_id: Optional[str]):
    if company_id is None:
        raise ValueError(
            "EVAL_COMPANY_ID must be set. Pass --company-id or set EVAL_COMPANY_ID env var."
        )
    return uuid.UUID(company_id)


def _chunk_ids_from_sources(sources: List[Dict[str, Any]]) -> List[str]:
    """
    Build deterministic chunk IDs from source metadata.

    Format: ``<document_id>-chunk-<chunk_index>``
    This matches the format used by ``WeaviateClient.upsert_document_chunks``
    which uses ``uuid5(document_id-chunk-i)`` as the Weaviate object ID.

    For retrieval evaluation we use the document_id + chunk_index composite
    as the chunk identifier since we don't have the raw Weaviate object UUID
    in the RAGService response.
    """
    ids = []
    seen: set[str] = set()
    for source in sources:
        doc_id = source.get("document_id")
        chunk_idx = source.get("chunk_index")
        if doc_id is not None and chunk_idx is not None:
            cid = f"{doc_id}-chunk-{chunk_idx}"
            if cid not in seen:
                seen.add(cid)
                ids.append(cid)
    return ids


def _log_aggregate_summary(run_id: str, aggregate: Dict[str, Any]) -> None:
    logger.info("=== Aggregate metrics for run %r ===", run_id)
    for key, val in sorted(aggregate.items()):
        if key != "failure_rates" and isinstance(val, (int, float)):
            logger.info("  %-30s = %.4f", key, val)
    failure_rates = aggregate.get("failure_rates", {})
    if failure_rates:
        logger.info("  --- Failure rates ---")
        for ft, rate in sorted(failure_rates.items()):
            if rate > 0:
                logger.info("  %-30s = %.1f%%", ft, rate * 100)
