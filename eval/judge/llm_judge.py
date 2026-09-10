"""
LLM-as-judge implementation.

Uses the application's existing ``LLMClientProtocol`` so any configured LLM
provider (Groq, OpenAI) works without additional setup.

Design:
  - Provider-agnostic: injects any ``LLMClientProtocol`` implementation.
  - Strict JSON validation: Pydantic ``JudgeOutput`` rejects malformed output.
  - Retry with exponential backoff on parse failures (JSON parse error or
    validation error) up to ``max_retries`` attempts.
  - Timeout: each judge call is wrapped with ``asyncio.wait_for``.
  - Never falls back to a fabricated score on failure: raises ``JudgeError``
    so callers can decide whether to skip or propagate the failure.
  - All failures are logged with the raw LLM response for debugging.

Privacy note: the judge receives the question, retrieved context, and
generated answer — the same data already processed by the RAG pipeline.
No additional PII is sent beyond what the production LLM already receives.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Optional

from pydantic import ValidationError

from eval.config import JUDGE_DEFAULT_MAX_RETRIES, JUDGE_TIMEOUT_SECONDS
from eval.judge.prompts import get_system_prompt, get_user_prompt
from eval.judge.protocol import JudgeError, JudgeOutput

logger = logging.getLogger(__name__)

# Characters trimmed from the LLM response before JSON parsing
_JSON_EXTRACT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> str:
    """
    Extract the first JSON object from an LLM response.

    Handles cases where the model wraps the JSON in markdown code blocks
    (```json ... ```) or adds surrounding explanation text.
    """
    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Try to find the first {...} block
    m = _JSON_EXTRACT_RE.search(text)
    if m:
        return m.group(0)

    return text


class LLMJudge:
    """
    LLM-as-judge that reuses the application's LLM client.

    Args:
        llm_client:        Any object satisfying ``LLMClientProtocol``.
        prompt_version:    Version of the judge prompts to use.
        judge_model_name:  Display name for the judge model (stored in results).
        max_retries:       Number of retries on parse failure.
        timeout_seconds:   Per-call timeout.
    """

    def __init__(
        self,
        llm_client,  # LLMClientProtocol — not typed to avoid circular imports
        *,
        prompt_version: str = "v1",
        judge_model_name: Optional[str] = None,
        max_retries: int = JUDGE_DEFAULT_MAX_RETRIES,
        timeout_seconds: float = JUDGE_TIMEOUT_SECONDS,
    ) -> None:
        self._llm = llm_client
        self._prompt_version = prompt_version
        self._judge_model_name = judge_model_name
        self._max_retries = max(0, max_retries)
        self._timeout = timeout_seconds

    async def evaluate(
        self,
        *,
        question: str,
        retrieved_context: str,
        generated_answer: str,
        expected_answer: Optional[str] = None,
    ) -> JudgeOutput:
        """
        Evaluate a single RAG example.

        Returns:
            Validated ``JudgeOutput``.

        Raises:
            ``JudgeError`` if all retries are exhausted.
        """
        system_prompt = get_system_prompt(self._prompt_version)
        user_prompt = get_user_prompt(
            self._prompt_version,
            question=question,
            retrieved_context=retrieved_context,
            generated_answer=generated_answer,
            expected_answer=expected_answer,
        )

        last_raw: Optional[str] = None
        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                # Exponential backoff: 1s, 2s, 4s
                await asyncio.sleep(min(2 ** (attempt - 1), 8))

            try:
                raw = await asyncio.wait_for(
                    self._llm.generate_answer(
                        context_chunks=[user_prompt],
                        user_query="",
                        system_prompt=system_prompt,
                        output_language="english",
                        conversation_history=None,
                    ),
                    timeout=self._timeout,
                )
                last_raw = raw

                # Parse and validate
                json_text = _extract_json(raw)
                parsed = json.loads(json_text)
                output = JudgeOutput(
                    **parsed,
                    judge_model=self._judge_model_name,
                    prompt_version=self._prompt_version,
                )
                if attempt > 0:
                    logger.info(
                        "Judge succeeded after %d retries", attempt
                    )
                return output

            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(
                    f"Judge timed out after {self._timeout}s"
                )
                logger.warning(
                    "Judge timeout on attempt %d/%d",
                    attempt + 1,
                    self._max_retries + 1,
                )
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                last_error = exc
                logger.warning(
                    "Judge JSON parse failure on attempt %d/%d: %s | raw=%r",
                    attempt + 1,
                    self._max_retries + 1,
                    exc,
                    (last_raw or "")[:300],
                )
            except ValidationError as exc:
                last_error = exc
                logger.warning(
                    "Judge schema validation failure on attempt %d/%d: %s | raw=%r",
                    attempt + 1,
                    self._max_retries + 1,
                    exc,
                    (last_raw or "")[:300],
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Judge unexpected error on attempt %d/%d: %s",
                    attempt + 1,
                    self._max_retries + 1,
                    exc,
                    exc_info=True,
                )

        raise JudgeError(
            f"Judge failed after {self._max_retries + 1} attempt(s): {last_error}",
            last_raw_response=last_raw,
        )


# ─────────────────────────────────────────────────────────────────────────── #
# Human calibration helpers
# ─────────────────────────────────────────────────────────────────────────── #


def judge_vs_human_agreement(
    judge_scores: list[int],
    human_scores: list[int],
    *,
    tolerance: int = 1,
) -> dict:
    """
    Compute agreement statistics between LLM judge and human labels.

    Both lists must be the same length.  Scores are integers 0–4.

    Args:
        judge_scores:   LLM judge scores for a dimension.
        human_scores:   Human annotation scores for the same dimension.
        tolerance:      Scores within this many points count as "agreed".

    Returns:
        Dict with:
          exact_agreement_rate:    fraction of identical scores
          tolerant_agreement_rate: fraction within tolerance
          mean_abs_diff:           mean absolute difference
          correlation:             Pearson r (None if < 3 samples)
    """
    if not judge_scores or not human_scores:
        return {}
    if len(judge_scores) != len(human_scores):
        raise ValueError("judge_scores and human_scores must be the same length")

    n = len(judge_scores)
    exact = sum(1 for j, h in zip(judge_scores, human_scores) if j == h)
    tolerant = sum(
        1 for j, h in zip(judge_scores, human_scores) if abs(j - h) <= tolerance
    )
    mad = sum(abs(j - h) for j, h in zip(judge_scores, human_scores)) / n

    pearson = _pearson(judge_scores, human_scores) if n >= 3 else None

    return {
        "n": n,
        "exact_agreement_rate": exact / n,
        "tolerant_agreement_rate": tolerant / n,
        "mean_abs_diff": mad,
        "pearson_r": pearson,
    }


def _pearson(xs: list[int], ys: list[int]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denom_x = sum((x - mx) ** 2 for x in xs) ** 0.5
    denom_y = sum((y - my) ** 2 for y in ys) ** 0.5
    if denom_x == 0 or denom_y == 0:
        return None
    return num / (denom_x * denom_y)
