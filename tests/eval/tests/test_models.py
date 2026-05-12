"""Unit tests for eval data models."""

import pytest

from tests.eval.src.models import (
    CaseResult,
    Condition,
    EvalReport,
    Expectation,
    ExpectationResult,
    TestCase,
)


def test_expectation_keyword_parses():
    raw = {
        "name": "mentions_kubernetes",
        "description": "Response mentions Kubernetes or k8s",
        "threshold": 0.5,
        "mandatory": True,
        "kind": "keyword",
        "pattern": "Kubernetes|k8s",
    }
    e = Expectation(**raw)
    assert e.kind == "keyword"
    assert e.pattern == "Kubernetes|k8s"
    assert e.mandatory is True


def test_expectation_llm_parses():
    raw = {
        "name": "describes_purpose",
        "description": "Explains Kyma as an extension runtime",
        "threshold": 0.5,
        "mandatory": False,
        "kind": "llm",
    }
    e = Expectation(**raw)
    assert e.kind == "llm"
    assert e.pattern is None


def test_expectation_keyword_requires_pattern():
    with pytest.raises(ValueError, match="pattern"):
        Expectation(
            name="x",
            description="y",
            threshold=0.5,
            mandatory=True,
            kind="keyword",  # missing pattern
        )


def test_testcase_parses():
    raw = {
        "id": "user_01_what_is_kyma",
        "question": "What is Kyma?",
        "collection": "user",
        "source": "joule_inspired",
        "expectations": [
            {
                "name": "k8s",
                "description": "mentions k8s",
                "threshold": 0.5,
                "mandatory": True,
                "kind": "keyword",
                "pattern": "Kubernetes|k8s",
            },
        ],
    }
    tc = TestCase(**raw)
    assert tc.id == "user_01_what_is_kyma"
    assert len(tc.expectations) == 1


def test_load_cases_from_yaml(tmp_path):
    content = """
- id: test_01
  question: "What is Kyma?"
  collection: user
  source: original
  expectations:
    - name: mentions_k8s
      description: "mentions Kubernetes"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "Kubernetes|k8s"
"""
    f = tmp_path / "cases.yaml"
    f.write_text(content)
    cases = TestCase.load_from_yaml(f)
    assert len(cases) == 1
    assert cases[0].id == "test_01"


def test_expectation_result_pass():
    r = ExpectationResult(
        name="x", score=0.8, threshold=0.5, mandatory=True, passed=True, reason="ok"
    )
    assert r.passed is True


def test_case_result_mandatory_fail_means_case_fails():
    r = CaseResult(
        case_id="c1",
        question="Q?",
        results={
            Condition.NO_TOOLS: [
                ExpectationResult(
                    name="x", score=0.3, threshold=0.5, mandatory=True, passed=False, reason="bad"
                ),
            ],
        },
    )
    assert r.condition_pass(Condition.NO_TOOLS) is False


def test_case_result_all_pass():
    r = CaseResult(
        case_id="c1",
        question="Q?",
        results={
            Condition.MCP: [
                ExpectationResult(
                    name="x", score=0.8, threshold=0.5, mandatory=True, passed=True, reason="ok"
                ),
                ExpectationResult(
                    name="y", score=0.9, threshold=0.5, mandatory=False, passed=True, reason="ok"
                ),
            ],
        },
    )
    assert r.condition_pass(Condition.MCP) is True


def test_eval_report_ci_pass():
    results = [
        CaseResult(
            case_id="c1",
            question="Q?",
            results={
                Condition.MCP: [
                    ExpectationResult(
                        name="x", score=0.9, threshold=0.5, mandatory=True, passed=True, reason="ok"
                    ),
                ],
            },
        ),
    ]
    report = EvalReport(results=results, pass_threshold=0.75)
    assert report.mcp_pass_rate == 1.0
    assert report.ci_pass is True


def test_eval_report_ci_fail_mandatory():
    results = [
        CaseResult(
            case_id="c1",
            question="Q?",
            results={
                Condition.MCP: [
                    ExpectationResult(
                        name="x",
                        score=0.3,
                        threshold=0.5,
                        mandatory=True,
                        passed=False,
                        reason="bad",
                    ),
                ],
            },
        ),
    ]
    report = EvalReport(results=results, pass_threshold=0.75)
    assert report.ci_pass is False


def test_case_result_condition_pass_rate():
    r = CaseResult(
        case_id="c1",
        question="Q?",
        results={
            Condition.MCP: [
                ExpectationResult(
                    name="x", score=0.8, threshold=0.5, mandatory=True, passed=True, reason="ok"
                ),
                ExpectationResult(
                    name="y", score=0.3, threshold=0.5, mandatory=False, passed=False, reason="bad"
                ),
            ],
        },
    )
    assert r.condition_pass_rate(Condition.MCP) == 0.5
    assert r.condition_pass_rate(Condition.NO_TOOLS) == 0.0  # missing condition


def test_case_result_condition_pass_missing_condition():
    r = CaseResult(case_id="c1", question="Q?", results={})
    assert r.condition_pass(Condition.MCP) is False
