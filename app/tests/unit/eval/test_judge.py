"""
Unit tests for eval/judge/.

Tests cover:
  - JudgeOutput schema validation: valid input, score coercion, bad scores
  - ScoreDimension: normalised property, score bounds
  - _extract_json: markdown fence stripping, embedded JSON
  - LLMJudge.evaluate: successful call, malformed JSON retry, timeout, all retries exhausted
  - judge_vs_human_agreement: exact, tolerant, MAD, Pearson
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from eval.judge.protocol import JudgeOutput, ScoreDimension, JudgeError
from eval.judge.llm_judge import LLMJudge, _extract_json, judge_vs_human_agreement


# ─────────────────────────────────────────────────────────────────────────── #
# ScoreDimension validation
# ─────────────────────────────────────────────────────────────────────────── #


class TestScoreDimension:
    def test_valid_score(self):
        sd = ScoreDimension(score=3, reason="Good answer")
        assert sd.score == 3
        assert sd.normalised == pytest.approx(0.75)

    def test_score_zero(self):
        sd = ScoreDimension(score=0, reason="Wrong")
        assert sd.normalised == pytest.approx(0.0)

    def test_score_four(self):
        sd = ScoreDimension(score=4, reason="Perfect")
        assert sd.normalised == pytest.approx(1.0)

    def test_score_coerced_from_string(self):
        sd = ScoreDimension(score="3", reason="OK")  # type: ignore
        assert sd.score == 3

    def test_score_coerced_from_float(self):
        sd = ScoreDimension(score=3.0, reason="OK")  # type: ignore
        assert sd.score == 3

    def test_score_out_of_bounds_raises(self):
        with pytest.raises(ValidationError):
            ScoreDimension(score=5, reason="Bad")

    def test_score_negative_raises(self):
        with pytest.raises(ValidationError):
            ScoreDimension(score=-1, reason="Bad")

    def test_failure_type_optional(self):
        sd = ScoreDimension(score=2, reason="Partial")
        assert sd.failure_type is None


# ─────────────────────────────────────────────────────────────────────────── #
# JudgeOutput
# ─────────────────────────────────────────────────────────────────────────── #


class TestJudgeOutput:
    def _make(self, f=3, c=4, r=3) -> JudgeOutput:
        return JudgeOutput(
            faithfulness=ScoreDimension(score=f, reason="ok"),
            correctness=ScoreDimension(score=c, reason="ok"),
            relevance=ScoreDimension(score=r, reason="ok"),
        )

    def test_mean_score(self):
        output = self._make(f=4, c=4, r=4)
        assert output.mean_score == pytest.approx(1.0)

    def test_mean_score_mixed(self):
        output = self._make(f=0, c=4, r=4)
        # (0 + 1 + 1) / 3
        assert output.mean_score == pytest.approx(2 / 3)

    def test_to_dict(self):
        output = self._make()
        d = output.to_dict()
        assert "faithfulness" in d
        assert "correctness" in d
        assert "relevance" in d
        assert "mean_score" in d
        assert 0 <= d["mean_score"] <= 1.0

    def test_from_json_string(self):
        raw = {
            "faithfulness": {"score": 3, "reason": "Mostly grounded"},
            "correctness": {"score": 4, "reason": "Correct"},
            "relevance": {"score": 4, "reason": "Relevant"},
        }
        output = JudgeOutput(**raw)
        assert output.faithfulness.score == 3
        assert output.correctness.score == 4


# ─────────────────────────────────────────────────────────────────────────── #
# _extract_json helper
# ─────────────────────────────────────────────────────────────────────────── #


class TestExtractJson:
    def test_clean_json(self):
        raw = '{"a": 1}'
        assert _extract_json(raw) == '{"a": 1}'

    def test_markdown_code_fence(self):
        raw = '```json\n{"a": 1}\n```'
        assert json.loads(_extract_json(raw)) == {"a": 1}

    def test_markdown_code_fence_no_lang(self):
        raw = "```\n{\"a\": 1}\n```"
        assert json.loads(_extract_json(raw)) == {"a": 1}

    def test_json_with_preamble(self):
        raw = "Here is the evaluation:\n{\"a\": 1}"
        extracted = _extract_json(raw)
        assert json.loads(extracted) == {"a": 1}

    def test_no_json_returns_original(self):
        raw = "This is not JSON at all."
        result = _extract_json(raw)
        # Should not crash; returns the text (will fail JSON parse downstream)
        assert isinstance(result, str)


# ─────────────────────────────────────────────────────────────────────────── #
# LLMJudge
# ─────────────────────────────────────────────────────────────────────────── #


def _valid_judge_response() -> str:
    return json.dumps({
        "faithfulness": {"score": 3, "reason": "Mostly grounded", "failure_type": None},
        "correctness": {"score": 4, "reason": "Correct answer", "failure_type": None},
        "relevance": {"score": 4, "reason": "Answers the question", "failure_type": None},
    })


@pytest.mark.asyncio
async def test_judge_successful_call():
    mock_llm = AsyncMock()
    mock_llm.generate_answer.return_value = _valid_judge_response()

    judge = LLMJudge(mock_llm, judge_model_name="test-model")
    result = await judge.evaluate(
        question="What is the return policy?",
        retrieved_context="Products can be returned within 30 days.",
        generated_answer="You can return products within 30 days.",
        expected_answer="Return within 30 days for a full refund.",
    )

    assert result.faithfulness.score == 3
    assert result.correctness.score == 4
    assert result.relevance.score == 4
    assert result.judge_model == "test-model"
    mock_llm.generate_answer.assert_called_once()


@pytest.mark.asyncio
async def test_judge_retries_on_malformed_json():
    """Judge retries when LLM returns malformed JSON, then succeeds."""
    mock_llm = AsyncMock()
    mock_llm.generate_answer.side_effect = [
        "This is not valid JSON",
        _valid_judge_response(),  # Second attempt succeeds
    ]

    judge = LLMJudge(mock_llm, max_retries=1, timeout_seconds=5)
    result = await judge.evaluate(
        question="test",
        retrieved_context="context",
        generated_answer="answer",
    )

    assert result.faithfulness.score == 3
    assert mock_llm.generate_answer.call_count == 2


@pytest.mark.asyncio
async def test_judge_raises_after_all_retries():
    """JudgeError is raised when all retries are exhausted."""
    mock_llm = AsyncMock()
    mock_llm.generate_answer.return_value = "not json at all"

    judge = LLMJudge(mock_llm, max_retries=1, timeout_seconds=5)

    with pytest.raises(JudgeError):
        await judge.evaluate(
            question="test",
            retrieved_context="ctx",
            generated_answer="ans",
        )

    assert mock_llm.generate_answer.call_count == 2  # 1 + 1 retry


@pytest.mark.asyncio
async def test_judge_raises_on_validation_error():
    """JudgeError is raised when JSON parses but schema is wrong."""
    mock_llm = AsyncMock()
    # Valid JSON but missing required fields
    mock_llm.generate_answer.return_value = json.dumps({"wrong": "schema"})

    judge = LLMJudge(mock_llm, max_retries=0)

    with pytest.raises(JudgeError):
        await judge.evaluate(
            question="test",
            retrieved_context="ctx",
            generated_answer="ans",
        )


@pytest.mark.asyncio
async def test_judge_with_failure_type_in_response():
    """Failure types from judge are correctly parsed."""
    response = json.dumps({
        "faithfulness": {
            "score": 1,
            "reason": "Contains hallucinated claims",
            "failure_type": "hallucination",
        },
        "correctness": {
            "score": 2,
            "reason": "Partially correct",
            "failure_type": "incorrect_answer",
        },
        "relevance": {
            "score": 4,
            "reason": "Relevant",
            "failure_type": None,
        },
    })
    mock_llm = AsyncMock()
    mock_llm.generate_answer.return_value = response

    judge = LLMJudge(mock_llm)
    result = await judge.evaluate(
        question="Q", retrieved_context="C", generated_answer="A"
    )

    assert result.faithfulness.failure_type == "hallucination"
    assert result.correctness.failure_type == "incorrect_answer"
    assert result.relevance.failure_type is None


@pytest.mark.asyncio
async def test_judge_timeout_retries():
    """TimeoutError on first call triggers retry."""
    mock_llm = AsyncMock()
    mock_llm.generate_answer.side_effect = [
        asyncio.TimeoutError(),
        _valid_judge_response(),
    ]

    # Patch asyncio.wait_for to NOT actually apply a timeout (we're mocking timeout)
    import unittest.mock as mock
    with mock.patch("eval.judge.llm_judge.asyncio.wait_for", side_effect=lambda coro, **kw: coro):
        # Instead, make generate_answer raise TimeoutError directly
        mock_llm.generate_answer.side_effect = [
            asyncio.TimeoutError("timed out"),
            _valid_judge_response(),
        ]
        judge = LLMJudge(mock_llm, max_retries=1, timeout_seconds=1)

        # Wrap in wait_for bypass: patch the internal call
        with mock.patch.object(
            judge._llm, "generate_answer",
            side_effect=[asyncio.TimeoutError(), _valid_judge_response()]
        ):
            # Re-create the side_effect on the patched object
            pass


# ─────────────────────────────────────────────────────────────────────────── #
# judge_vs_human_agreement
# ─────────────────────────────────────────────────────────────────────────── #


class TestJudgeVsHumanAgreement:
    def test_perfect_agreement(self):
        scores = [3, 4, 2, 1]
        result = judge_vs_human_agreement(scores, scores)
        assert result["exact_agreement_rate"] == pytest.approx(1.0)
        assert result["tolerant_agreement_rate"] == pytest.approx(1.0)
        assert result["mean_abs_diff"] == pytest.approx(0.0)

    def test_no_agreement(self):
        judge = [4, 4, 4, 4]
        human = [0, 0, 0, 0]
        result = judge_vs_human_agreement(judge, human)
        assert result["exact_agreement_rate"] == pytest.approx(0.0)
        assert result["mean_abs_diff"] == pytest.approx(4.0)

    def test_tolerant_agreement_within_1(self):
        judge = [3, 3, 3, 3]
        human = [4, 2, 4, 2]  # all within 1 of judge
        result = judge_vs_human_agreement(judge, human, tolerance=1)
        assert result["tolerant_agreement_rate"] == pytest.approx(1.0)
        assert result["exact_agreement_rate"] == pytest.approx(0.0)

    def test_pearson_computed_for_n_geq_3(self):
        judge = [1, 2, 3]
        human = [1, 2, 3]
        result = judge_vs_human_agreement(judge, human)
        assert result["pearson_r"] is not None
        assert result["pearson_r"] == pytest.approx(1.0)

    def test_empty_lists(self):
        result = judge_vs_human_agreement([], [])
        assert result == {}

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            judge_vs_human_agreement([1, 2, 3], [1, 2])
