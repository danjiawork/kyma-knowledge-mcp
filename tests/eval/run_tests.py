#!/usr/bin/env python3
"""
Kyma Capability Test Runner
---------------------------
Runs Kyma capability e2e tests using Claude Code directly.
For question-only tests (empty resourceName/namespace), no cluster is needed.
For cluster tests (resourceName set), a kubeconfig must be provided.
A second Claude instance acts as judge for each test.

Usage:
  python run_tests.py                        # run all tests (needs kubeconfig for cluster tests)
  python run_tests.py --filter question      # run only question tests (no cluster needed)
  python run_tests.py --no-mcp               # answer from training knowledge only, no tools
  python run_tests.py --timeout 120          # per-test timeout in seconds (default 180)
  python run_tests.py --trace                # save stream-json trace per test to results/
  python run_tests.py --kubeconfig <path>    # kubeconfig for cluster tests
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
FEATURE_DIR = SCRIPT_DIR / "features"
SYSTEM_PROMPT_FILE = SCRIPT_DIR / "system_prompt.md"
RESULTS_DIR = SCRIPT_DIR / "results"
ENV_FILE = SCRIPT_DIR / ".env"
KUBECONFIG_FILE = Path(os.environ.get("KUBECONFIG", "kubeconfig.yaml"))

_NO_MCP_SYSTEM_PROMPT = """\
You are an expert in Kyma and Kubernetes.
Answer the question using only your own training knowledge. No tools are available.
If you are not confident about an answer, say so rather than guessing.
Always respond in Markdown.
"""


# ── Env loading ───────────────────────────────────────────────────────────────


def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


# ── Feature file parser ───────────────────────────────────────────────────────


def parse_feature_file(path: Path, env: dict) -> dict | None:
    """Extract context, question, and assertions from a .feature file."""
    text = path.read_text()

    # Substitute env placeholders
    for key, val in env.items():
        text = text.replace(f"${{{key}}}", val)

    # Extract application context JSON
    ctx_match = re.search(
        r'Given the application context:\s*"""\s*(\{.*?\})\s*"""', text, re.DOTALL
    )
    if not ctx_match:
        return None
    try:
        context = json.loads(ctx_match.group(1))
    except json.JSONDecodeError:
        return None

    # Extract question
    q_match = re.search(r'When I say "(.+?)"', text)
    if not q_match:
        return None
    question = q_match.group(1)

    # Extract assertions
    assertions = []

    # contains assertions
    for m in re.finditer(r'message content at index \d+ contains "(.+?)"', text):
        assertions.append({"type": "contains", "value": m.group(1)})

    # relates_to assertions (multiline doc string)
    for m in re.finditer(r'response relates to\s*"""\s*(.*?)\s*"""', text, re.DOTALL):
        assertions.append({"type": "relates_to", "value": m.group(1).strip()})

    return {
        "feature_file": path.name,
        "context": context,
        "question": question,
        "assertions": assertions,
    }


# ── Claude invocations ────────────────────────────────────────────────────────


def run_tested_claude(
    system_prompt: str,
    user_message: str,
    timeout: int,
    kubeconfig: str,
    no_mcp: bool = False,
    trace_path: Path | None = None,
) -> tuple[str, str]:
    """
    Run Claude as the tested agent.
    Returns (response_text, error_message).
    If trace_path is set, saves the raw stream-json to that file.
    """
    env = os.environ.copy()
    env.setdefault("GCTL_SESSION_ID", "capability-test")

    if no_mcp:
        # Pure training knowledge — no tools, no kubeconfig injection
        prompt = system_prompt
        extra_flags = ["--tools", ""]
    else:
        # Inject kubeconfig path so Claude uses it explicitly in every kubectl command.
        prompt = (
            system_prompt
            + f"\n\n## Cluster Access\n\nAlways use this kubeconfig explicitly in every kubectl command:\n```\nkubectl --kubeconfig={kubeconfig} ...\n```\n"
        )
        env["KUBECONFIG"] = kubeconfig
        extra_flags = ["--dangerously-skip-permissions"]

    if trace_path:
        output_format = "stream-json"
        extra_flags += ["--verbose"]
    else:
        output_format = "json"

    if no_mcp:
        # --tools "" requires the prompt via stdin, not as a positional arg
        cmd = [
            "claude",
            "-p",
            "--system-prompt",
            prompt,
            "--output-format",
            output_format,
            "--model",
            "claude-sonnet-4-6",
            *extra_flags,
        ]
        stdin_input = user_message
    else:
        cmd = [
            "claude",
            "-p",
            "--system-prompt",
            prompt,
            "--output-format",
            output_format,
            "--model",
            "claude-sonnet-4-6",
            *extra_flags,
            user_message,
        ]
        stdin_input = None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            input=stdin_input,
        )
        if result.returncode != 0:
            return "", f"claude exited {result.returncode}: {result.stderr[:500]}"

        if trace_path:
            trace_path.write_text(result.stdout)
            # Extract final result from stream-json: last line with type=result
            response = ""
            for line in result.stdout.splitlines():
                try:
                    event = json.loads(line)
                    if event.get("type") == "result":
                        response = event.get("result", "")
                except json.JSONDecodeError:
                    continue
            return response, ""
        else:
            try:
                data = json.loads(result.stdout)
                return data.get("result", result.stdout), ""
            except json.JSONDecodeError:
                return result.stdout, ""

    except subprocess.TimeoutExpired:
        return "", f"timed out after {timeout}s"
    except Exception as e:
        return "", str(e)


def run_judge_claude(
    question: str, response: str, relates_to_assertions: list[dict], timeout: int = 60
) -> list[dict]:
    """
    Run Claude as a judge to evaluate relates_to assertions.
    Returns the assertions list with 'passed' and 'reason' filled in.
    """
    if not relates_to_assertions:
        return []

    assertions_text = "\n".join(
        f'{i + 1}. "{a["value"]}"' for i, a in enumerate(relates_to_assertions)
    )

    judge_prompt = f"""You are a strict test judge evaluating an AI assistant's response.

Question asked: {question}

Response to evaluate:
<response>
{response}
</response>

For each assertion below, determine if the response satisfies it.
Return ONLY a valid JSON array, no other text.

Assertions:
{assertions_text}

Required output format (JSON array, one object per assertion, in order):
[
  {{"value": "<assertion text>", "passed": true/false, "reason": "<one sentence why>"}}
]"""

    cmd = [
        "claude",
        "-p",
        "--tools",
        "",
        "--output-format",
        "json",
        "--model",
        "claude-sonnet-4-6",
        "--system-prompt",
        "You are a strict test judge. Respond only with a valid JSON array as instructed. No markdown, no explanation outside the JSON.",
        judge_prompt,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return [
                dict(a, passed=False, reason=f"judge error: {result.stderr[:200]}")
                for a in relates_to_assertions
            ]

        try:
            outer = json.loads(result.stdout)
            raw = outer.get("result", result.stdout)
        except json.JSONDecodeError:
            raw = result.stdout

        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())

        try:
            verdicts = json.loads(raw)
            out = []
            for i, a in enumerate(relates_to_assertions):
                v = verdicts[i] if i < len(verdicts) else {}
                out.append(
                    {
                        "type": "relates_to",
                        "value": a["value"],
                        "passed": bool(v.get("passed", False)),
                        "reason": v.get("reason", ""),
                    }
                )
            return out
        except (json.JSONDecodeError, IndexError) as e:
            return [
                dict(a, passed=False, reason=f"judge parse error: {e}")
                for a in relates_to_assertions
            ]

    except subprocess.TimeoutExpired:
        return [dict(a, passed=False, reason="judge timed out") for a in relates_to_assertions]
    except Exception as e:
        return [dict(a, passed=False, reason=str(e)) for a in relates_to_assertions]


# ── Assertion evaluation ──────────────────────────────────────────────────────


def evaluate_contains(response: str, assertions: list[dict]) -> list[dict]:
    results = []
    for a in assertions:
        if a["type"] != "contains":
            continue
        passed = a["value"].lower() in response.lower()
        results.append(
            {
                "type": "contains",
                "value": a["value"],
                "passed": passed,
                "reason": "" if passed else f'response does not contain "{a["value"]}"',
            }
        )
    return results


# ── Output formatting ─────────────────────────────────────────────────────────


def build_markdown_report(results: list[dict], timestamp: str) -> str:
    passed_count = sum(1 for r in results if r["passed"])
    total = len(results)

    lines = [
        "# Kyma Capability Test Results",
        "",
        f"Run: {timestamp}",
        f"**Total: {passed_count}/{total} passed**",
        "",
        "---",
        "",
    ]

    for i, r in enumerate(results, 1):
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        feature = r["feature_file"].replace(".feature", "")

        lines += [
            f"## {i}. {feature}",
            "",
            f"**Question:** {r['question']}  ",
            f"**Result:** {status}",
            "",
        ]

        if r.get("error"):
            lines += [f"**Agent error:** {r['error']}", ""]
        else:
            # Assertion checklist
            lines.append("**Assertions:**")
            for a in r.get("assertions", []):
                icon = "✅" if a["passed"] else "❌"
                label = "contains" if a["type"] == "contains" else "relates to"
                reason = f" — {a['reason']}" if not a["passed"] and a.get("reason") else ""
                lines.append(f"- {icon} `[{label}]` {a['value']}{reason}")
            lines.append("")

            # Model response
            if r.get("response"):
                lines += [
                    "<details>",
                    "<summary>Model response</summary>",
                    "",
                    r["response"],
                    "",
                    "</details>",
                    "",
                ]

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Run Kyma tests with Claude")
    parser.add_argument(
        "--filter", default="", help="Only run feature files matching this substring"
    )
    parser.add_argument(
        "--no-mcp",
        action="store_true",
        help="Answer from training knowledge only — no tools, no MCP, no kubeconfig needed",
    )
    parser.add_argument(
        "--timeout", type=int, default=180, help="Per-test timeout in seconds (default 180)"
    )
    parser.add_argument(
        "--trace", action="store_true", help="Save stream-json tool call trace per test to results/"
    )
    parser.add_argument(
        "--kubeconfig", default="", help="Path to kubeconfig file (overrides KUBECONFIG env var)"
    )
    parser.add_argument(
        "--results-dir",
        default="",
        help="Override results output directory (default: <script_dir>/results/)",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir).resolve() if args.results_dir else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)

    # Load env
    env = load_env(ENV_FILE)

    # Select system prompt
    if args.no_mcp:
        system_prompt = _NO_MCP_SYSTEM_PROMPT
    else:
        if not SYSTEM_PROMPT_FILE.exists():
            print(f"ERROR: {SYSTEM_PROMPT_FILE} not found")
            sys.exit(1)
        system_prompt = SYSTEM_PROMPT_FILE.read_text()

    # Resolve kubeconfig (only needed for cluster tests)
    if args.kubeconfig:
        kubeconfig = args.kubeconfig
    elif env.get("KUBECONFIG"):
        kubeconfig = env["KUBECONFIG"]
    else:
        kubeconfig = str(KUBECONFIG_FILE)
    if not args.no_mcp and not Path(kubeconfig).exists():
        print(
            f"WARNING: kubeconfig not found at {kubeconfig}, kubectl may not work for cluster tests"
        )

    # Discover feature files
    feature_files = sorted(FEATURE_DIR.glob("*.feature"))
    if args.filter:
        feature_files = [f for f in feature_files if args.filter in f.name]
    if not feature_files:
        print(f"No feature files found matching filter '{args.filter}'")
        sys.exit(1)

    print(f"Found {len(feature_files)} test(s) to run\n")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    all_results = []

    for feature_file in feature_files:
        print(f"── {feature_file.name}")

        parsed = parse_feature_file(feature_file, env)
        if not parsed:
            print("   SKIP: could not parse\n")
            continue

        # Build user message
        user_message = f"""Context:
{json.dumps(parsed["context"], indent=2)}

Question: {parsed["question"]}"""

        # Run tested Claude
        print("   Running agent...", flush=True)
        trace_path = (
            results_dir / f"{timestamp}_{feature_file.stem}_trace.jsonl" if args.trace else None
        )
        response, error = run_tested_claude(
            system_prompt,
            user_message,
            args.timeout,
            kubeconfig,
            no_mcp=args.no_mcp,
            trace_path=trace_path,
        )

        if error:
            print(f"   Agent error: {error}")
            result = {
                "feature_file": parsed["feature_file"],
                "question": parsed["question"],
                "response": "",
                "error": error,
                "assertions": [
                    dict(a, passed=False, reason="agent error") for a in parsed["assertions"]
                ],
                "passed": False,
            }
            all_results.append(result)
            print("   Result: ❌ FAIL (agent error)\n")
            continue

        # Evaluate contains assertions in Python
        contains_results = evaluate_contains(
            response, [a for a in parsed["assertions"] if a["type"] == "contains"]
        )

        # Evaluate relates_to assertions with judge Claude
        relates_to = [a for a in parsed["assertions"] if a["type"] == "relates_to"]
        if relates_to:
            print("   Running judge...", flush=True)
            relates_to_results = run_judge_claude(parsed["question"], response, relates_to)
        else:
            relates_to_results = []

        all_assertion_results = contains_results + relates_to_results
        if not all_assertion_results:
            print(f"   WARNING: no assertions defined for {feature_file.name}, skipping")
            continue
        test_passed = all(a["passed"] for a in all_assertion_results)

        result = {
            "feature_file": parsed["feature_file"],
            "question": parsed["question"],
            "response": response,
            "assertions": all_assertion_results,
            "passed": test_passed,
        }
        all_results.append(result)

        status = "✅ PASS" if test_passed else "❌ FAIL"

        failed = [a for a in all_assertion_results if not a["passed"]]
        print(f"   Result: {status}" + (f" ({len(failed)} assertion(s) failed)" if failed else ""))
        for a in failed:
            print(f"     - [{a['type']}] {a['value'][:70]}")
            if a.get("reason"):
                print(f"       {a['reason']}")
        print()

    # Write results
    json_path = results_dir / f"{timestamp}.json"
    md_path = results_dir / f"{timestamp}.md"

    json_path.write_text(json.dumps(all_results, indent=2))
    md_path.write_text(build_markdown_report(all_results, timestamp))

    total = len(all_results)
    passed = sum(1 for r in all_results if r["passed"])
    print(f"{'─' * 50}")
    print(f"Results: {passed}/{total} passed")
    print(f"JSON:    {json_path}")
    print(f"Report:  {md_path}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
