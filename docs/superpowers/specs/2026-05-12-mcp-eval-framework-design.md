# MCP Eval Framework Design

**Date:** 2026-05-12  
**Status:** Approved

## Goal

Build an evaluation framework inside `kyma-knowledge-mcp` that measures how much the knowledge MCP improves answer quality for any general LLM agent. The framework runs three conditions side-by-side and produces a scored, shareable report on GitHub Pages.

---

## Context

The MCP provides two RAG-based search tools over local ChromaDB indexes:
- `search_kyma_docs` — Kyma user documentation
- `search_kyma_contributor_docs` — Kyma contributor/developer documentation

The eval answers the question: **"Given a Kyma question, are the chunks returned by the MCP sufficient for an LLM to answer correctly — and how does that compare to answering without any tools?"**

---

## Three Evaluation Conditions

| Condition | Tools Available | Purpose |
|-----------|----------------|---------|
| A — no-tools | none | Baseline: LLM training knowledge only |
| B — web-search | web search | Real-world alternative: LLM + internet |
| C — mcp | `search_kyma_docs` / `search_kyma_contributor_docs` | MCP value measurement |

**CI pass/fail gates only on condition C.** Conditions A and B are comparison baselines — they are expected to score lower and do not affect CI outcome.

---

## Directory Structure

```
tests/
├── unit/
├── integration/
└── eval/
    ├── cases/
    │   ├── user_docs.yaml          # User-facing Kyma questions (incl. APIRule)
    │   └── contributor_docs.yaml   # Developer/contributor questions
    ├── src/
    │   ├── agent.py        # LLM agent abstraction (Claude CLI / GitHub Models)
    │   ├── judge.py        # Keyword match + DeepEval GEval judge
    │   ├── runner.py       # Parallel orchestration, retry, GA output, exit code
    │   └── report.py       # JSON results → HTML + Markdown reports
    ├── results/            # Historical results committed to repo
    │   └── YYYY-MM-DD_HH-MM_<git-sha>.json
    └── run_eval.py         # CLI entry point
```

---

## Test Case Format

Test cases are YAML files under `cases/`. Each entry has:

```yaml
- id: user_01_what_is_kyma
  question: "What is Kyma?"
  collection: user              # which MCP tool to use in condition C
  source: joule_inspired        # joule_inspired | original
  expectations:
    - name: mentions_kubernetes
      description: "Response mentions Kubernetes or k8s"
      threshold: 0.5
      mandatory: true
      kind: keyword             # keyword | llm
      pattern: "Kubernetes|k8s"
    - name: describes_purpose
      description: "Explains Kyma as an application extension runtime"
      threshold: 0.5
      mandatory: false
      kind: llm

- id: apirule_02_jwt_config
  question: "How do I configure JWT authentication for an APIRule?"
  collection: user
  source: original
  expectations:
    - name: mentions_jwt
      description: "Mentions JWT or token-based authentication"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "jwt|JWT|token"
    - name: shows_yaml_example
      description: "Provides a YAML configuration example or spec fields for APIRule"
      threshold: 0.6
      mandatory: true
      kind: llm
```

**Fields:**
- `collection`: `user` or `contributor` — maps to which MCP tool is called in condition C
- `source`: `joule_inspired` (topic taken from joule-capability feature files) or `original`
- `kind: keyword` — regex match, binary score (1.0 if matched, 0.0 if not); free and deterministic, used in CI
- `kind: llm` — DeepEval GEval judge, produces a continuous score (0.0–1.0)
- `mandatory: true` — must pass (`score >= threshold`) for the test case to pass overall
- `threshold` — minimum score to pass; keyword expectations should use 0.5 (effectively "must match")

### Planned Test Case Coverage

| File | Count | Topics |
|------|-------|--------|
| `user_docs.yaml` | ~15 | What is Kyma, modules, eventing, serverless, telemetry, Istio, BTP, KEDA, regions, hyperscalers, expose endpoint, CLI install, **APIRule JWT auth (v2), APIRule NoAuth (v2), APIRule v1→v2 migration** |

**APIRule version accuracy tests** (within `user_docs.yaml`): These specifically verify that the MCP returns up-to-date v2 information, as this is a common RAG failure mode (returning stale v1 docs):

```yaml
- id: apirule_v2_version_check
  question: "What is the latest version of APIRule in Kyma and what changed from v1?"
  collection: user
  source: original
  expectations:
    - name: mentions_v2
      description: "States that the current/latest APIRule version is v2 (apiVersion: gateway.kyma-project.io/v2)"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: no_accessstrategies
      description: "Does NOT recommend using the accessStrategies field, or explicitly states it was removed in v2"
      threshold: 0.5
      mandatory: true
      kind: llm

- id: apirule_jwt_v2
  question: "How do I configure JWT authentication for an APIRule in Kyma?"
  collection: user
  source: original
  expectations:
    - name: uses_v2_apiversion
      description: "Uses apiVersion: gateway.kyma-project.io/v2 in any YAML example, not v1beta1 or v1"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: no_accessstrategies_field
      description: "Does not include accessStrategies field in the configuration (this field does not exist in v2)"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: mentions_jwt_config
      description: "Mentions JWT issuer, JWKS URI, or token authentication configuration"
      threshold: 0.5
      mandatory: false
      kind: keyword
      pattern: "jwt|JWT|issuer|jwks"
```
| `contributor_docs.yaml` | ~8 | api-gateway contribution, eventing architecture, serverless tests, lifecycle manager, module creation, telemetry pipeline |

---

## Scoring & Pass/Fail Logic

Same approach as kyma-companion: **GEval per expectation, threshold-based pass/fail, no ground truth needed.**

### Per expectation

- `kind: keyword` — binary: 1.0 if regex matches, 0.0 otherwise; passes if `score >= threshold`
- `kind: llm` — DeepEval `GEval` with `evaluation_steps=[expectation.description]`, `evaluation_params=[INPUT, ACTUAL_OUTPUT]`; passes if `score >= threshold`

The `description` field is the ground truth in criteria form — it expresses what a correct answer must contain, without requiring a full reference answer. GEval evaluates whether the actual response satisfies each criterion. This is the same pattern as kyma-companion's `expectation.statement` and joule's `response relates to` assertions.

### CI gate — MCP condition only

Conditions A (no-tools) and B (web-search) are **report-only**. They do not affect CI outcome.

```python
PASS_THRESHOLD = 0.75  # configurable via env var EVAL_PASS_THRESHOLD

# pass rate = fraction of all expectations that pass under condition C
total         = len(all_expectations_across_all_cases)
passed        = sum(1 for e in all_expectations if e.score >= e.threshold)
mcp_pass_rate = passed / total

ci_pass = mcp_pass_rate >= PASS_THRESHOLD
exit(0 if ci_pass else 1)
```

**Why pass rate, not average score:** "75% of all criteria satisfied" is directly interpretable. Average score mixes GEval floats from criteria of different difficulty and produces a number that is hard to reason about.

---

## Agent Abstraction

`agent.py` exposes a single interface. The model backend is injected via config:

```python
class Agent(Protocol):
    async def answer(self, question: str, condition: Condition) -> str: ...
```

**Local (Claude Code CLI):**
```python
ClaudeCliAgent(model="claude-sonnet-4-6")
# Conditions A/B: claude -p --model ... (no tools / web search enabled)
# Condition C:    claude -p --mcp-config mcp_config.json --model ...
```

**CI (GitHub Models — free via GITHUB_TOKEN):**
```python
GitHubModelsAgent(
    model="gpt-4o-mini",            # or "meta-llama-3.1-70b-instruct"
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ["GITHUB_TOKEN"],
)
# Uses openai-compatible SDK with tool call loop
```

For condition C, the agent receives the MCP tools as OpenAI-compatible tool definitions (`search_kyma_docs`, `search_kyma_contributor_docs`). When the LLM returns a tool call, the runner intercepts it and calls `LocalRAGClient.query()` directly in Python — no MCP subprocess needed for eval. This keeps tests fast and avoids protocol overhead.

For condition B (web search), both locally and in CI, a simple DuckDuckGo search function is provided as a tool (no API key required). If web search is unavailable, condition B is skipped and marked as `N/A` in the report rather than failing CI.

---

## Judge Design

`judge.py` evaluates each expectation against the agent's response:

```
kind=keyword → regex match (free, deterministic, used in CI)
kind=llm     → DeepEval GEval metric
```

**GEval setup (same pattern as kyma-companion):**
```python
from deepeval.metrics import GEvalMetric
from deepeval.test_case import LLMTestCase

metric = GEvalMetric(
    name=expectation.name,
    criteria=expectation.description,
    threshold=expectation.threshold,
    model=judge_model,   # same configurable backend as agent
)
test_case = LLMTestCase(input=question, actual_output=response)
metric.measure(test_case)
score = metric.score  # 0.0–1.0
```

---

## Runner Design

`runner.py` orchestrates execution, mirroring kyma-companion's `run_evaluation.py`:

```
For each test case (parallel via ThreadPoolExecutor):
  For each condition (A, B, C):
    1. Call agent.answer(question, condition)     → response
    2. Retry up to 3x if LLM judge raises error
    3. Score all expectations
    4. Record result

Aggregate scores per condition
Determine CI pass/fail (condition C only)
Write results/YYYY-MM-DD_HH-MM_<sha>.json
Print GitHub Actions grouped output (::group:: / ::endgroup::)
Exit 0 (pass) or 1 (fail)
```

**Parallelism:** Each test case runs as a `Future` in a `ThreadPoolExecutor`. The three conditions within a test case run sequentially to avoid rate-limiting.

**GitHub Actions output format:**
```
::group::user_01_what_is_kyma
  [A no-tools]    score=0.58  mandatory=PASS  optional=0.42
  [B web-search]  score=0.74  mandatory=PASS  optional=0.71
  [C mcp]         score=0.93  mandatory=PASS  optional=0.91  ✅
::endgroup::
```

---

## CLI Entry Point

```bash
# Run all cases, all conditions (CI default)
python run_eval.py

# Local: use Claude CLI, run only APIRule cases
python run_eval.py --agent claude-cli --filter apirule

# Override pass threshold
python run_eval.py --threshold 0.80

# Save results and generate report
python run_eval.py --save-results --report html
```

---

## Report & GitHub Pages

`report.py` reads the latest JSON result and generates:

1. **`results/latest.md`** — Markdown table, committed to repo
2. **`docs/eval-report/index.html`** — Published to GitHub Pages

### HTML report layout

**Header:** Three-bar chart comparing overall scores (A / B / C)

**Summary table:**

| Test Case | Question | No Tools | Web Search | MCP |
|-----------|----------|----------|------------|-----|
| user_01 | What is Kyma? | 58% | 74% | 93% ✅ |
| apirule_02 | JWT auth config | 33% | 61% | 87% ✅ |
| ... | | | | |
| **Overall** | | **47%** | **71%** | **89% ✅** |

**Detail (expandable per test case):** Each expectation with score, kind, and judge reason.

### GitHub Pages setup

- Branch: `gh-pages`
- Path: `docs/eval-report/index.html`
- CI workflow pushes updated HTML after each eval run on `main`

---

## CI Workflow (`.github/workflows/eval.yml`)

**Triggers:** Push to `main`, PR to `main`

**Steps:**
1. Checkout repo
2. Install Python deps (`uv sync`)
3. Start MCP server subprocess (for condition C)
4. Run `python tests/eval/run_eval.py --agent github-models`
5. Upload `results/*.json` as artifact
6. On `main` push only: regenerate HTML report and push to `gh-pages`

**Secrets needed:** Only `GITHUB_TOKEN` (automatically available in GitHub Actions — no extra setup required).

---

## What We Do NOT Include (vs kyma-companion)

| kyma-companion feature | Our decision |
|------------------------|--------------|
| Redis token tracking | Not needed — our scope is small |
| K8s cluster provisioning | Not needed — MCP is a local process |
| Companion API client | Not needed — we call MCP tools directly |
| Namespace-scoped scenario loading | Not needed |
