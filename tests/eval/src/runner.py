"""Parallel eval runner with retry and GitHub Actions output."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from tests.eval.src.agent import Agent
from tests.eval.src.judge import GEvalJudge, score_expectation
from tests.eval.src.models import CaseResult, Condition, EvalReport, TestCase


def run_case(
    case: TestCase,
    agent: Agent,
    llm_judge: GEvalJudge,
    conditions: list[Condition],
    max_retries: int = 3,
) -> CaseResult:
    result = CaseResult(case_id=case.id, question=case.question)
    for condition in conditions:
        response = ""
        for attempt in range(max_retries):
            try:
                response = agent.answer(case.question, condition, case.collection)
                break
            except Exception as exc:
                if attempt == max_retries - 1:
                    response = f"[ERROR after {max_retries} retries] {exc}"
        exp_results = [score_expectation(exp, response, llm_judge) for exp in case.expectations]
        result.results[condition] = exp_results
    return result


def run_eval(
    cases: list[TestCase],
    agent: Agent,
    llm_judge: GEvalJudge,
    conditions: list[Condition] | None = None,
    pass_threshold: float = 0.75,
    max_workers: int = 4,
    max_retries: int = 3,
) -> EvalReport:
    if conditions is None:
        conditions = list(Condition)

    case_results: list[CaseResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_case, case, agent, llm_judge, conditions, max_retries): case
            for case in cases
        }
        for future in as_completed(futures):
            case = futures[future]
            _ga_group_start(case.id)
            try:
                result = future.result()
                case_results.append(result)
                _print_case_result(result, conditions)
            except Exception as exc:
                print(f"  [FATAL] {case.id} failed: {exc}", flush=True)
            finally:
                _ga_group_end()

    return EvalReport(results=case_results, pass_threshold=pass_threshold)


def _ga_group_start(name: str) -> None:
    print(f"::group::{name}", flush=True)


def _ga_group_end() -> None:
    print("::endgroup::", flush=True)


def _print_case_result(result: CaseResult, conditions: list[Condition]) -> None:
    for condition in conditions:
        exps = result.results.get(condition, [])
        if not exps:
            continue
        passed_count = sum(1 for e in exps if e.passed)
        rate = passed_count / len(exps)
        mandatory_ok = all(e.passed for e in exps if e.mandatory)
        status = "✅" if mandatory_ok and rate >= 0.75 else "❌"
        print(
            f"  [{condition.value:12s}] {passed_count}/{len(exps)} passed "
            f"({rate:.0%}) mandatory={'PASS' if mandatory_ok else 'FAIL'} {status}",
            flush=True,
        )
        for e in exps:
            icon = "✓" if e.passed else "✗"
            print(f"    {icon} {e.name}: {e.score:.2f} — {e.reason[:80]}", flush=True)
