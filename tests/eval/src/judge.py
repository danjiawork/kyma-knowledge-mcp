"""Keyword and GEval judges for eval expectations."""

from __future__ import annotations

import re

from deepeval.metrics import GEval
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams

from tests.eval.src.models import Expectation, ExpectationResult


class KeywordJudge:
    """Free, deterministic judge: regex match against the response."""

    def score(self, expectation: Expectation, response: str) -> ExpectationResult:
        pattern = expectation.pattern or ""
        try:
            matched = bool(re.search(pattern, response, re.IGNORECASE))
        except re.error as exc:
            return ExpectationResult(
                name=expectation.name,
                score=0.0,
                threshold=expectation.threshold,
                mandatory=expectation.mandatory,
                passed=False,
                reason=f"Invalid regex pattern '{pattern}': {exc}",
            )
        score = 1.0 if matched else 0.0
        return ExpectationResult(
            name=expectation.name,
            score=score,
            threshold=expectation.threshold,
            mandatory=expectation.mandatory,
            passed=score >= expectation.threshold,
            reason=f"Pattern '{pattern}' {'matched' if matched else 'not found'} in response.",
        )


class GEvalJudge:
    """LLM-as-judge using DeepEval GEval with criteria-as-ground-truth."""

    def __init__(self, model: str | DeepEvalBaseLLM) -> None:
        self.model = model

    def score(self, expectation: Expectation, response: str) -> ExpectationResult:
        metric = GEval(
            name=expectation.name,
            evaluation_steps=[expectation.description],
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            threshold=expectation.threshold,
            model=self.model,
            async_mode=False,
            verbose_mode=False,
        )
        test_case = LLMTestCase(
            input=expectation.description,
            actual_output=response,
        )
        metric.measure(test_case)
        score = metric.score if metric.score is not None else 0.0
        return ExpectationResult(
            name=expectation.name,
            score=score,
            threshold=expectation.threshold,
            mandatory=expectation.mandatory,
            passed=metric.is_successful(),
            reason=metric.reason or "",
        )


def score_expectation(
    expectation: Expectation,
    response: str,
    llm_judge: GEvalJudge,
) -> ExpectationResult:
    """Route to the correct judge based on expectation kind."""
    if expectation.kind == "keyword":
        return KeywordJudge().score(expectation, response)
    return llm_judge.score(expectation, response)
