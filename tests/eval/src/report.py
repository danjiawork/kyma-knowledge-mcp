"""Generate HTML and Markdown reports from EvalReport."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from tests.eval.src.models import Condition, EvalReport

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_CONDITION_LABELS = {
    Condition.NO_TOOLS: "No Tools",
    Condition.WEB_SEARCH: "Web Search",
    Condition.MCP: "MCP",
}


def _condition_pass_rate(report: EvalReport, condition: Condition) -> float:
    all_exp = [e for r in report.results for e in r.results.get(condition, [])]
    if not all_exp:
        return 0.0
    return sum(1 for e in all_exp if e.passed) / len(all_exp)


def generate_html(report: EvalReport) -> str:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("report.html.j2")
    condition_rates = {_CONDITION_LABELS[c]: _condition_pass_rate(report, c) for c in Condition}
    return template.render(
        report=report,
        condition_rates=condition_rates,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        Condition=Condition,
    )


def generate_markdown(report: EvalReport) -> str:
    lines = [
        "# MCP Eval Results",
        "",
        f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"CI gate: {'PASS' if report.ci_pass else 'FAIL'}  ",
        f"MCP pass rate: {report.mcp_pass_rate:.0%}  ",
        "",
        "## Summary",
        "",
        "| Condition | Pass Rate |",
        "|-----------|-----------|",
    ]
    for condition in Condition:
        rate = _condition_pass_rate(report, condition)
        label = _CONDITION_LABELS[condition]
        lines.append(f"| {label} | {rate:.0%} |")
    lines += [
        "",
        "## Results",
        "",
        "| Case ID | Question | No Tools | Web Search | MCP |",
        "|---------|----------|----------|------------|-----|",
    ]
    for result in report.results:
        cells = [f"`{result.case_id}`", result.question[:60]]
        for condition in Condition:
            exps = result.results.get(condition, [])
            if not exps:
                cells.append("—")
                continue
            passed = sum(1 for e in exps if e.passed)
            icon = "PASS" if result.condition_pass(condition) else "FAIL"
            cells.append(f"{icon} {passed}/{len(exps)}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
