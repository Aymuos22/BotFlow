"""
Versioned LLM judge prompts.

Each prompt version is a module-level constant so changes are tracked in git.
The active version is set in ``eval/config.py`` (JUDGE_PROMPT_VERSION).

Prompt design principles:
  1. Explicit scoring rubric with examples (reduces variance).
  2. Independent dimension evaluation (do not let one dimension influence another).
  3. Mandatory JSON output schema (enables Pydantic validation).
  4. Instructions to cite specific evidence from context (improves faithfulness accuracy).
  5. Short — judge context window budget is shared with the eval example.
"""
from __future__ import annotations

from typing import Optional

# ─────────────────────────────────────────────────────────────────────────── #
# v1 — baseline judge prompts
# ─────────────────────────────────────────────────────────────────────────── #

_SYSTEM_PROMPT_V1 = """\
You are an expert evaluator for a RAG (Retrieval-Augmented Generation) system.
Your task is to independently assess the quality of a generated answer on three dimensions.

SCORING RUBRIC (apply to EACH dimension independently):
  0 = Completely wrong / absent
  1 = Mostly wrong, some relevant elements
  2 = Partially correct, important gaps or errors
  3 = Mostly correct, minor issues
  4 = Fully correct / excellent

DIMENSION DEFINITIONS:

  FAITHFULNESS
  Does the generated answer contain ONLY information that is explicitly present
  in the provided context? Do NOT penalise for irrelevant context not being cited.
  Score 0 if the answer invents facts not in the context.
  Score 4 if every factual claim is directly supported by the context.

  CORRECTNESS
  How factually correct is the generated answer compared to the expected answer?
  If no expected answer is provided, evaluate whether the answer is plausible
  and consistent with the context.
  Score 0 if the answer is completely wrong.
  Score 4 if the answer perfectly matches the expected answer.

  RELEVANCE
  Does the generated answer directly address the user's question?
  Score 0 if the answer is completely off-topic.
  Score 4 if the answer directly and fully answers what was asked.

OUTPUT FORMAT (JSON ONLY — no markdown, no explanation outside the JSON):
{
  "faithfulness": {
    "score": <int 0-4>,
    "reason": "<one sentence explaining the score>",
    "failure_type": "<null or one of: hallucination, context_ignored>"
  },
  "correctness": {
    "score": <int 0-4>,
    "reason": "<one sentence explaining the score>",
    "failure_type": "<null or one of: incorrect_answer, incomplete_answer>"
  },
  "relevance": {
    "score": <int 0-4>,
    "reason": "<one sentence explaining the score>",
    "failure_type": "<null or one of: instruction_following_failure>"
  }
}

IMPORTANT: Return ONLY the JSON object. No preamble, no markdown code block.
"""


def _user_prompt_v1(
    question: str,
    retrieved_context: str,
    generated_answer: str,
    expected_answer: Optional[str],
) -> str:
    parts = [
        f"QUESTION:\n{question}",
        f"\nCONTEXT (what was retrieved and passed to the RAG system):\n{retrieved_context}",
        f"\nGENERATED ANSWER:\n{generated_answer}",
    ]
    if expected_answer:
        parts.append(f"\nEXPECTED ANSWER:\n{expected_answer}")
    else:
        parts.append("\nEXPECTED ANSWER: (not provided — evaluate faithfulness and relevance only)")
    parts.append("\nEvaluate the generated answer and return the JSON scores.")
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────── #
# Prompt registry
# ─────────────────────────────────────────────────────────────────────────── #

PROMPTS = {
    "v1": {
        "system": _SYSTEM_PROMPT_V1,
        "user_fn": _user_prompt_v1,
    }
}


def get_system_prompt(version: str = "v1") -> str:
    entry = PROMPTS.get(version)
    if not entry:
        raise ValueError(f"Unknown judge prompt version: {version!r}")
    return entry["system"]


def get_user_prompt(
    version: str,
    question: str,
    retrieved_context: str,
    generated_answer: str,
    expected_answer: Optional[str],
) -> str:
    entry = PROMPTS.get(version)
    if not entry:
        raise ValueError(f"Unknown judge prompt version: {version!r}")
    return entry["user_fn"](
        question, retrieved_context, generated_answer, expected_answer
    )
