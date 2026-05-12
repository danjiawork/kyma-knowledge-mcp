"""Unit tests for judge implementations."""

from unittest.mock import MagicMock, patch

from tests.eval.src.judge import GEvalJudge, KeywordJudge, score_expectation
from tests.eval.src.models import Expectation, ExpectationResult


def _kw_expectation(pattern: str, mandatory: bool = True) -> Expectation:
    return Expectation(
        name="test",
        description="test desc",
        threshold=0.5,
        mandatory=mandatory,
        kind="keyword",
        pattern=pattern,
    )


def _llm_expectation(description: str, mandatory: bool = True) -> Expectation:
    return Expectation(
        name="test",
        description=description,
        threshold=0.5,
        mandatory=mandatory,
        kind="llm",
    )


def test_keyword_judge_match():
    judge = KeywordJudge()
    result = judge.score(_kw_expectation("Kubernetes|k8s"), "Kyma runs on Kubernetes clusters.")
    assert result.score == 1.0
    assert result.passed is True


def test_keyword_judge_no_match():
    judge = KeywordJudge()
    result = judge.score(_kw_expectation("Kubernetes|k8s"), "Kyma is a cloud platform.")
    assert result.score == 0.0
    assert result.passed is False


def test_keyword_judge_case_insensitive():
    judge = KeywordJudge()
    result = judge.score(_kw_expectation("kubernetes|k8s"), "Uses K8s under the hood.")
    assert result.score == 1.0


def test_keyword_judge_reason_populated():
    judge = KeywordJudge()
    result = judge.score(_kw_expectation("Kubernetes"), "Uses Kubernetes.")
    assert len(result.reason) > 0


def test_geval_judge_pass():
    """GEvalJudge returns passed=True when GEval metric passes."""
    judge = GEvalJudge(model=MagicMock())
    mock_metric = MagicMock()
    mock_metric.score = 0.9
    mock_metric.is_successful.return_value = True
    mock_metric.reason = "Response clearly mentions the topic."

    with patch("tests.eval.src.judge.GEval", return_value=mock_metric):
        result = judge.score(_llm_expectation("mentions Kubernetes"), "Kyma runs on Kubernetes.")

    assert result.score == 0.9
    assert result.passed is True


def test_geval_judge_fail():
    judge = GEvalJudge(model=MagicMock())
    mock_metric = MagicMock()
    mock_metric.score = 0.2
    mock_metric.is_successful.return_value = False
    mock_metric.reason = "Response does not mention the topic."

    with patch("tests.eval.src.judge.GEval", return_value=mock_metric):
        result = judge.score(_llm_expectation("mentions Kubernetes"), "No relevant content.")

    assert result.passed is False


def test_score_expectation_routes_keyword():
    """score_expectation delegates to KeywordJudge for kind=keyword."""
    e = _kw_expectation("Kubernetes|k8s")
    result = score_expectation(e, "Runs on Kubernetes.", llm_judge=MagicMock())
    assert result.score == 1.0


def test_score_expectation_routes_llm():
    """score_expectation delegates to GEvalJudge for kind=llm."""
    e = _llm_expectation("describes Kyma")
    mock_llm_judge = MagicMock()
    mock_llm_judge.score.return_value = ExpectationResult(
        name="test", score=0.8, threshold=0.5, mandatory=True, passed=True, reason="ok"
    )
    result = score_expectation(e, "Kyma is a platform.", llm_judge=mock_llm_judge)
    assert result.score == 0.8
    mock_llm_judge.score.assert_called_once_with(e, "Kyma is a platform.")
