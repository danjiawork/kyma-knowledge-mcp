"""Unit tests for report generation."""

from tests.eval.src.models import CaseResult, Condition, EvalReport, ExpectationResult
from tests.eval.src.report import generate_html, generate_markdown


def _sample_report() -> EvalReport:
    results = [
        CaseResult(
            case_id="user_01_what_is_kyma",
            question="What is Kyma?",
            results={
                Condition.NO_TOOLS: [
                    ExpectationResult(
                        name="k8s",
                        score=0.0,
                        threshold=0.5,
                        mandatory=True,
                        passed=False,
                        reason="not found",
                    ),
                ],
                Condition.WEB_SEARCH: [
                    ExpectationResult(
                        name="k8s",
                        score=1.0,
                        threshold=0.5,
                        mandatory=True,
                        passed=True,
                        reason="matched",
                    ),
                ],
                Condition.MCP: [
                    ExpectationResult(
                        name="k8s",
                        score=1.0,
                        threshold=0.5,
                        mandatory=True,
                        passed=True,
                        reason="matched",
                    ),
                ],
            },
        ),
    ]
    return EvalReport(results=results, pass_threshold=0.75)


def test_generate_markdown_contains_case_id():
    md = generate_markdown(_sample_report())
    assert "user_01_what_is_kyma" in md


def test_generate_markdown_contains_all_conditions():
    md = generate_markdown(_sample_report())
    assert "no_tools" in md.lower() or "No Tools" in md
    assert "web_search" in md.lower() or "Web Search" in md
    assert "mcp" in md.lower() or "MCP" in md


def test_generate_markdown_shows_pass_rate():
    md = generate_markdown(_sample_report())
    assert "%" in md


def test_generate_html_contains_case_id():
    html = generate_html(_sample_report())
    assert "user_01_what_is_kyma" in html


def test_generate_html_is_valid_html():
    html = generate_html(_sample_report())
    assert "<html" in html
    assert "</html>" in html


def test_generate_html_shows_ci_status():
    html = generate_html(_sample_report())
    assert "PASS" in html or "FAIL" in html
