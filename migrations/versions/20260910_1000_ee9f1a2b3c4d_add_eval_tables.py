"""add_eval_tables

Revision ID: ee9f1a2b3c4d
Revises: dd8e0f2a3b4c
Create Date: 2026-09-10 10:00:00.000000+00:00

Creates three tables for the RAG evaluation framework:

  eval_runs        — one row per evaluation run (config snapshot + aggregate metrics)
  eval_results     — one row per (run, dataset_item); per-example metrics + judge scores
  human_labels     — human annotations for a subset of eval_results (judge calibration)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ee9f1a2b3c4d"
down_revision: Union[str, None] = "dd8e0f2a3b4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── eval_runs ─────────────────────────────────────────────────────── #
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.String(120), nullable=False),
        sa.Column("dataset_version", sa.String(40), nullable=False),
        sa.Column("embedding_model", sa.String(120), nullable=True),
        sa.Column("retrieval_config", sa.JSON(), nullable=True),
        sa.Column("reranker_config", sa.JSON(), nullable=True),
        sa.Column("llm_model", sa.String(120), nullable=True),
        sa.Column("prompt_version", sa.String(40), nullable=True),
        sa.Column("judge_model", sa.String(120), nullable=True),
        sa.Column("judge_prompt_version", sa.String(40), nullable=True),
        sa.Column("git_commit", sa.String(60), nullable=True),
        sa.Column("experiment_name", sa.String(120), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="running",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("total_examples", sa.Integer(), nullable=True),
        sa.Column("aggregate_metrics", sa.JSON(), nullable=True),
        sa.Column("failure_counts", sa.JSON(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_eval_runs_run_id", "eval_runs", ["run_id"], unique=True)
    op.create_index("ix_eval_runs_created_at", "eval_runs", ["created_at"])
    op.create_index("ix_eval_runs_status", "eval_runs", ["status"])

    # ── eval_results ──────────────────────────────────────────────────── #
    op.create_table(
        "eval_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_item_id", sa.String(120), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("category", sa.String(60), nullable=True),
        sa.Column("difficulty", sa.String(20), nullable=True),
        sa.Column("language", sa.String(20), nullable=True),
        sa.Column("answerable", sa.Boolean(), nullable=True),
        # Ground truth
        sa.Column("relevant_document_ids", sa.JSON(), nullable=True),
        sa.Column("relevant_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("relevance_grades", sa.JSON(), nullable=True),
        # Retrieval results
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("retrieved_document_ids", sa.JSON(), nullable=True),
        sa.Column("retrieval_scores", sa.JSON(), nullable=True),
        sa.Column("search_mode", sa.String(20), nullable=True),
        # Deterministic retrieval metrics
        sa.Column("recall_at_1", sa.Float(), nullable=True),
        sa.Column("recall_at_3", sa.Float(), nullable=True),
        sa.Column("recall_at_5", sa.Float(), nullable=True),
        sa.Column("recall_at_10", sa.Float(), nullable=True),
        sa.Column("precision_at_1", sa.Float(), nullable=True),
        sa.Column("precision_at_3", sa.Float(), nullable=True),
        sa.Column("precision_at_5", sa.Float(), nullable=True),
        sa.Column("mrr", sa.Float(), nullable=True),
        sa.Column("ndcg_at_5", sa.Float(), nullable=True),
        sa.Column("ndcg_at_10", sa.Float(), nullable=True),
        sa.Column("hit_rate_at_5", sa.Float(), nullable=True),
        sa.Column("avg_retrieval_score", sa.Float(), nullable=True),
        # Generation
        sa.Column("generated_answer", sa.Text(), nullable=True),
        sa.Column("response_type", sa.String(20), nullable=True),
        sa.Column("fallback_triggered", sa.Boolean(), nullable=True),
        # Deterministic generation metrics
        sa.Column("token_f1", sa.Float(), nullable=True),
        sa.Column("answer_length_chars", sa.Integer(), nullable=True),
        # LLM-judge scores
        sa.Column("faithfulness_score", sa.Float(), nullable=True),
        sa.Column("faithfulness_reason", sa.Text(), nullable=True),
        sa.Column("correctness_score", sa.Float(), nullable=True),
        sa.Column("correctness_reason", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("relevance_reason", sa.Text(), nullable=True),
        sa.Column("judge_model", sa.String(120), nullable=True),
        sa.Column("judge_prompt_version", sa.String(40), nullable=True),
        sa.Column("judge_raw_response", sa.JSON(), nullable=True),
        # Failure taxonomy
        sa.Column("failure_types", sa.JSON(), nullable=True),
        # Latency
        sa.Column("retrieval_latency_ms", sa.Integer(), nullable=True),
        sa.Column("generation_latency_ms", sa.Integer(), nullable=True),
        sa.Column("total_latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["eval_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_results_run_id", "eval_results", ["run_id"])
    op.create_index("ix_eval_results_created_at", "eval_results", ["created_at"])
    op.create_index(
        "ix_eval_results_run_item",
        "eval_results",
        ["run_id", "dataset_item_id"],
    )

    # ── human_labels ──────────────────────────────────────────────────── #
    op.create_table(
        "human_labels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("eval_result_id", sa.Uuid(), nullable=False),
        sa.Column("labeler_id", sa.String(120), nullable=False),
        sa.Column("correctness", sa.Integer(), nullable=True),
        sa.Column("faithfulness", sa.Integer(), nullable=True),
        sa.Column("relevance", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["eval_result_id"], ["eval_results.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_human_labels_eval_result_id", "human_labels", ["eval_result_id"]
    )
    op.create_index("ix_human_labels_created_at", "human_labels", ["created_at"])
    op.create_index(
        "ix_human_labels_labeler", "human_labels", ["labeler_id"]
    )


def downgrade() -> None:
    op.drop_table("human_labels")
    op.drop_table("eval_results")
    op.drop_table("eval_runs")
