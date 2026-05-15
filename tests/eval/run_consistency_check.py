#!/usr/bin/env python3
"""
Consistency Check Runner
------------------------
Runs the full test suite N times and produces a report showing
which tests fail consistently across runs vs. flakily.

Usage:
  python run_consistency_check.py              # 3 runs (default)
  python run_consistency_check.py --runs 5
  python run_consistency_check.py --runs 3 --filter 01_bitnami
  python run_consistency_check.py --from-results results/2026-04-12_14-35.json results/2026-04-12_15-10.json
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
RESULTS_DIR = SCRIPT_DIR / "results"


def run_suite(
    run_index: int,
    total_runs: int,
    filter_str: str,
    timeout: int,
    no_mcp: bool = False,
    kubeconfig: str = "",
) -> Path:
    """Run run_tests.py once, return the path to the JSON result file."""
    print(f"\n{'━' * 60}")
    print(f"  Run {run_index}/{total_runs}")
    print(f"{'━' * 60}\n")

    cmd = [sys.executable, str(SCRIPT_DIR / "run_tests.py")]
    if filter_str:
        cmd += ["--filter", filter_str]
    if timeout:
        cmd += ["--timeout", str(timeout)]
    if no_mcp:
        cmd += ["--no-mcp"]
    if kubeconfig:
        cmd += ["--kubeconfig", kubeconfig]

    existing_json = set(RESULTS_DIR.glob("*.json"))
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode not in (0, 1):
        print(f"ERROR: run_tests.py exited with code {result.returncode}")
        sys.exit(1)

    new_json = sorted(RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    new_json = [p for p in new_json if p not in existing_json]
    if not new_json:
        print("ERROR: no result JSON found after run")
        sys.exit(1)
    return new_json[-1]


def load_results(path: Path) -> dict[str, bool]:
    """Return {feature_file: passed} from a result JSON."""
    data = json.loads(path.read_text())
    return {r["feature_file"]: r["passed"] for r in data}


def build_consistency_report(run_results: list[tuple[str, dict[str, bool]]], timestamp: str) -> str:
    """
    run_results: list of (run_label, {feature_file: passed})
    """
    # Collect all test names in a stable order
    all_tests = sorted({t for _, r in run_results for t in r})
    n_runs = len(run_results)

    # Compute pass count per test
    pass_counts = {t: sum(1 for _, r in run_results if r.get(t, False)) for t in all_tests}

    # Sort: consistently failing first (0 passes), then flaky, then consistently passing
    def sort_key(t):
        p = pass_counts[t]
        if p == 0:
            return (0, t)  # always fail → top
        if p == n_runs:
            return (2, t)  # always pass → bottom
        return (1, t)  # flaky → middle

    sorted_tests = sorted(all_tests, key=sort_key)

    lines = [
        "# Consistency Check Report",
        "",
        f"Run: {timestamp}  ",
        f"Runs: {n_runs}  ",
        f"Tests: {len(all_tests)}",
        "",
        "## Legend",
        "",
        "| Symbol | Meaning |",
        "|--------|---------|",
        "| ✅ | Passed |",
        "| ❌ | Failed |",
        "| — | Not run |",
        "",
        "## Results",
        "",
    ]

    # Header row
    run_labels = [label for label, _ in run_results]
    header = "| Test | " + " | ".join(run_labels) + " | Passed |"
    separator = "|------|" + "|".join(["--------"] * n_runs) + "|--------|"
    lines += [header, separator]

    for t in sorted_tests:
        p = pass_counts[t]
        name = t.replace(".feature", "")
        cells = []
        for _, r in run_results:
            if t in r:
                cells.append("✅" if r[t] else "❌")
            else:
                cells.append("—")

        # Highlight the pass count: bold if never passed, normal otherwise
        pass_str = f"**{p}/{n_runs}**" if p == 0 else f"{p}/{n_runs}"
        if p == n_runs:
            pass_str = f"✅ {p}/{n_runs}"

        lines.append(f"| {name} | " + " | ".join(cells) + f" | {pass_str} |")

    # Summary section
    always_fail = [t for t in all_tests if pass_counts[t] == 0]
    flaky = [t for t in all_tests if 0 < pass_counts[t] < n_runs]
    always_pass = [t for t in all_tests if pass_counts[t] == n_runs]

    lines += [
        "",
        "## Summary",
        "",
        f"- 🔴 **Always failing** ({len(always_fail)}): "
        + (", ".join(t.replace(".feature", "") for t in always_fail) if always_fail else "none"),
        f"- 🟡 **Flaky** ({len(flaky)}): "
        + (", ".join(t.replace(".feature", "") for t in flaky) if flaky else "none"),
        f"- 🟢 **Always passing** ({len(always_pass)}): "
        + (", ".join(t.replace(".feature", "") for t in always_pass) if always_pass else "none"),
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run test suite N times and compare consistency")
    parser.add_argument(
        "--runs", type=int, default=3, help="Number of times to run the suite (default 3)"
    )
    parser.add_argument(
        "--filter", default="", help="Only run feature files matching this substring"
    )
    parser.add_argument(
        "--no-mcp",
        action="store_true",
        help="Pass --no-mcp to run_tests.py (training knowledge only)",
    )
    parser.add_argument(
        "--timeout", type=int, default=180, help="Per-test timeout passed to run_tests.py"
    )
    parser.add_argument(
        "--from-results",
        nargs="+",
        metavar="JSON",
        help="Skip running tests; compare existing result JSON files instead",
    )
    parser.add_argument(
        "--kubeconfig", default="", help="Path to kubeconfig (forwarded to run_tests.py)"
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    if args.from_results:
        # Load existing result files
        run_results = []
        for path_str in args.from_results:
            path = Path(path_str)
            if not path.is_absolute():
                path = SCRIPT_DIR / path
            label = path.stem
            run_results.append((label, load_results(path)))
        print(f"Loaded {len(run_results)} result file(s)")
    else:
        # Run the suite N times
        run_results = []
        for i in range(1, args.runs + 1):
            json_path = run_suite(
                i,
                args.runs,
                args.filter,
                args.timeout,
                no_mcp=args.no_mcp,
                kubeconfig=args.kubeconfig,
            )
            label = f"Run {i}"
            run_results.append((label, load_results(json_path)))

    # Write consistency report
    RESULTS_DIR.mkdir(exist_ok=True)
    report_path = RESULTS_DIR / f"{timestamp}_consistency.md"
    report_path.write_text(build_consistency_report(run_results, timestamp))

    print(f"\n{'━' * 60}")
    print(f"Consistency report: {report_path}")

    # Print quick summary to stdout
    all_tests = sorted({t for _, r in run_results for t in r})
    n_runs = len(run_results)
    pass_counts = {t: sum(1 for _, r in run_results if r.get(t, False)) for t in all_tests}
    always_fail = [t for t in all_tests if pass_counts[t] == 0]
    flaky = [t for t in all_tests if 0 < pass_counts[t] < n_runs]
    always_pass = [t for t in all_tests if pass_counts[t] == n_runs]
    print(f"🔴 Always failing: {len(always_fail)}")
    print(f"🟡 Flaky:          {len(flaky)}")
    print(f"🟢 Always passing: {len(always_pass)}")


if __name__ == "__main__":
    main()
