#!/usr/bin/env python3
"""CLI entry point for the MCP eval framework.

Usage:
  # CI (GitHub Models, all conditions)
  python tests/eval/run_eval.py

  # Local (Claude CLI, filter to apirule cases)
  python tests/eval/run_eval.py --agent claude-cli --filter apirule

  # Custom threshold
  python tests/eval/run_eval.py --threshold 0.80

  # Save results and generate report
  python tests/eval/run_eval.py --save-results --report html
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

CASES_DIR = Path(__file__).parent / "cases"
RESULTS_DIR = Path(__file__).parent / "results"
REPORT_DIR = Path(__file__).parent.parent.parent / "docs" / "eval-report"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP eval framework")
    parser.add_argument(
        "--agent",
        choices=["github-models", "claude-cli"],
        default="github-models",
        help="Agent backend to use (default: github-models for CI)",
    )
    parser.add_argument(
        "--judge-model",
        default="gpt-4o-mini",
        help="Model for GEval judge (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--agent-model",
        default="gpt-4o-mini",
        help="Model for the tested agent (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--filter",
        default="",
        help="Only run cases whose ID contains this string",
    )
    parser.add_argument(
        "--conditions",
        nargs="+",
        choices=["no_tools", "web_search", "mcp"],
        default=None,
        help="Conditions to run (default: all three)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.environ.get("EVAL_PASS_THRESHOLD", "0.75")),
        help="MCP pass rate threshold for CI gate (default: 0.75)",
    )
    parser.add_argument(
        "--save-results",
        action="store_true",
        help="Write JSON results to tests/eval/results/",
    )
    parser.add_argument(
        "--report",
        choices=["html", "markdown", "both"],
        default=None,
        help="Generate report(s) after eval",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="ThreadPoolExecutor max_workers (default: 4)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    from tests.eval.src.agent import ClaudeCliAgent, GitHubModelsAgent
    from tests.eval.src.judge import GEvalJudge
    from tests.eval.src.judge_model import GitHubModelsLLM
    from tests.eval.src.models import Condition, TestCase
    from tests.eval.src.report import generate_html, generate_markdown
    from tests.eval.src.runner import run_eval

    # Load all test cases
    cases: list[TestCase] = []
    for yaml_file in sorted(CASES_DIR.glob("*.yaml")):
        cases.extend(TestCase.load_from_yaml(yaml_file))

    if args.filter:
        cases = [c for c in cases if args.filter in c.id]

    if not cases:
        print(f"No cases found (filter: '{args.filter}')", file=sys.stderr)
        sys.exit(1)

    print(f"Running {len(cases)} test cases with agent={args.agent}", flush=True)

    # Build agent
    if args.agent == "github-models":
        agent = GitHubModelsAgent(model=args.agent_model)
    else:
        agent = ClaudeCliAgent(model=args.agent_model)

    # Build GEval judge model
    judge_model = GitHubModelsLLM(model=args.judge_model)
    llm_judge = GEvalJudge(model=judge_model)

    # Parse conditions
    conditions = None
    if args.conditions:
        conditions = [Condition(c) for c in args.conditions]

    # Run
    report = run_eval(
        cases=cases,
        agent=agent,
        llm_judge=llm_judge,
        conditions=conditions,
        pass_threshold=args.threshold,
        max_workers=args.workers,
    )

    # Summary
    print("\n" + "=" * 60, flush=True)
    print(f"MCP pass rate : {report.mcp_pass_rate:.0%}", flush=True)
    print(f"MCP mandatory : {'PASS' if report.mcp_mandatory_pass else 'FAIL'}", flush=True)
    print(f"CI result     : {'✅ PASS' if report.ci_pass else '❌ FAIL'}", flush=True)
    print("=" * 60, flush=True)

    # Save JSON results
    if args.save_results:
        RESULTS_DIR.mkdir(exist_ok=True)
        import subprocess

        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        ts = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M")
        out_path = RESULTS_DIR / f"{ts}_{sha}.json"
        out_path.write_text(report.model_dump_json(indent=2))
        print(f"Results saved to {out_path}", flush=True)

    # Generate report
    if args.report in ("html", "both"):
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        html = generate_html(report)
        html_path = REPORT_DIR / "index.html"
        html_path.write_text(html)
        print(f"HTML report: {html_path}", flush=True)

    if args.report in ("markdown", "both"):
        md = generate_markdown(report)
        md_path = RESULTS_DIR / "latest.md"
        RESULTS_DIR.mkdir(exist_ok=True)
        md_path.write_text(md)
        print(f"Markdown report: {md_path}", flush=True)

    sys.exit(0 if report.ci_pass else 1)


if __name__ == "__main__":
    main()
