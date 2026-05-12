"""Unit tests for the eval runner."""

from unittest.mock import MagicMock

from tests.eval.src.models import Condition, EvalReport, Expectation, ExpectationResult, TestCase
from tests.eval.src.runner import run_case, run_eval


def _make_case(case_id: str = "c1") -> TestCase:
    return TestCase(
        id=case_id,
        question="What is Kyma?",
        collection="user",
        source="original",
        expectations=[
            Expectation(
                name="k8s",
                description="mentions k8s",
                threshold=0.5,
                mandatory=True,
                kind="keyword",
                pattern="Kubernetes|k8s",
            ),
        ],
    )


def _mock_agent(response: str = "Kyma runs on Kubernetes.") -> MagicMock:
    agent = MagicMock()
    agent.answer.return_value = response
    return agent


def _mock_judge(score: float = 0.9, passed: bool = True) -> MagicMock:
    judge = MagicMock()
    judge.score.return_value = ExpectationResult(
        name="k8s", score=score, threshold=0.5, mandatory=True, passed=passed, reason="ok"
    )
    return judge


def test_run_case_returns_case_result():
    case = _make_case()
    result = run_case(
        case=case,
        agent=_mock_agent(),
        llm_judge=_mock_judge(),
        conditions=[Condition.NO_TOOLS, Condition.MCP],
    )
    assert result.case_id == "c1"
    assert Condition.NO_TOOLS in result.results
    assert Condition.MCP in result.results


def test_run_case_all_conditions_scored():
    case = _make_case()
    result = run_case(
        case=case,
        agent=_mock_agent("Kyma runs on Kubernetes."),
        llm_judge=_mock_judge(),
        conditions=list(Condition),
    )
    assert len(result.results) == 3


def test_run_case_keyword_judge_used_for_keyword_expectation():
    """keyword expectations are scored by regex, not llm_judge."""
    case = _make_case()
    llm_judge = MagicMock()
    result = run_case(
        case=case,
        agent=_mock_agent("Kyma runs on Kubernetes."),
        llm_judge=llm_judge,
        conditions=[Condition.MCP],
    )
    # llm_judge.score should NOT be called for keyword expectations
    llm_judge.score.assert_not_called()
    assert result.results[Condition.MCP][0].score == 1.0


def test_run_eval_returns_report():
    cases = [_make_case("c1"), _make_case("c2")]
    report = run_eval(
        cases=cases,
        agent=_mock_agent("Kyma runs on Kubernetes."),
        llm_judge=_mock_judge(),
        conditions=[Condition.NO_TOOLS, Condition.MCP],
        pass_threshold=0.75,
        max_workers=2,
    )
    assert isinstance(report, EvalReport)
    assert len(report.results) == 2


def test_run_eval_retry_on_agent_error():
    """Runner retries up to max_retries times when agent raises."""
    case = _make_case()
    agent = MagicMock()
    agent.answer.side_effect = [RuntimeError("timeout"), "Kyma runs on Kubernetes."]

    report = run_eval(
        cases=[case],
        agent=agent,
        llm_judge=_mock_judge(),
        conditions=[Condition.MCP],
        max_retries=2,
    )
    assert len(report.results) == 1
    assert agent.answer.call_count == 2
