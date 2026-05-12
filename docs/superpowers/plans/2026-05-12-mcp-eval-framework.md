# MCP Eval Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an eval framework under `tests/eval/` that compares LLM answer quality across three conditions (no-tools, web-search, MCP) and publishes results to GitHub Pages.

**Architecture:** Test cases are YAML files with GEval-compatible criteria. A runner executes all cases in parallel via ThreadPoolExecutor, scoring each expectation with DeepEval GEval (llm) or regex (keyword). CI gates on MCP condition: all mandatory expectations pass AND overall pass rate ≥ 75%.

**Tech Stack:** Python 3.12, DeepEval (GEval), OpenAI SDK (GitHub Models), PyYAML, Pydantic, Jinja2, pytest, uv

---

## File Map

| File | Responsibility |
|------|---------------|
| `tests/eval/cases/user_docs.yaml` | ~15 user-facing Kyma test cases incl. APIRule v2 |
| `tests/eval/cases/contributor_docs.yaml` | ~8 contributor/developer test cases |
| `tests/eval/src/models.py` | Pydantic models: `Expectation`, `TestCase`, `ExpectationResult`, `CaseResult`, `EvalReport` |
| `tests/eval/src/judge.py` | `KeywordJudge`, `GEvalJudge`, `score_expectation()` |
| `tests/eval/src/agent.py` | `Condition` enum, `Agent` protocol, `GitHubModelsAgent`, `ClaudeCliAgent`, `web_search()` |
| `tests/eval/src/runner.py` | `run_eval()` — ThreadPoolExecutor, retry, GA output, CI exit code |
| `tests/eval/src/report.py` | `generate_html()`, `generate_markdown()` — reads `EvalReport`, writes files |
| `tests/eval/run_eval.py` | CLI entry point — argparse, wires everything together |
| `tests/eval/templates/report.html.j2` | Jinja2 template for GitHub Pages HTML report |
| `tests/eval/tests/test_models.py` | Unit tests for YAML parsing |
| `tests/eval/tests/test_judge.py` | Unit tests for keyword judge + GEval judge (mocked) |
| `tests/eval/tests/test_runner.py` | Unit tests for runner with mocked agent + judge |
| `tests/eval/tests/test_report.py` | Unit tests for report generation |
| `.github/workflows/eval.yml` | CI: run eval on PR/push, publish HTML to gh-pages on main |

---

## Task 1: Project scaffold and Pydantic models

**Files:**
- Create: `tests/eval/__init__.py`
- Create: `tests/eval/cases/.gitkeep`
- Create: `tests/eval/src/__init__.py`
- Create: `tests/eval/tests/__init__.py`
- Create: `tests/eval/templates/.gitkeep`
- Create: `tests/eval/results/.gitkeep`
- Modify: `pyproject.toml` — add eval dependencies
- Create: `tests/eval/src/models.py`
- Create: `tests/eval/tests/test_models.py`

- [ ] **Step 1: Add eval dependencies to pyproject.toml**

Add to `[dependency-groups]` in `pyproject.toml`:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.15.12",
    "mypy>=1.20.2",
    "taskipy>=1.12.0",
]
eval = [
    "deepeval>=2.0.0",
    "openai>=1.0.0",
    "pyyaml>=6.0",
    "jinja2>=3.1.0",
    "duckduckgo-search>=6.0.0",
]
```

Run: `uv sync --group eval`

Expected: resolves without conflict.

- [ ] **Step 2: Create directory scaffold**

```bash
mkdir -p tests/eval/cases tests/eval/src tests/eval/tests tests/eval/templates tests/eval/results
touch tests/eval/__init__.py tests/eval/src/__init__.py tests/eval/tests/__init__.py
touch tests/eval/results/.gitkeep
```

- [ ] **Step 3: Write failing tests for models**

Create `tests/eval/tests/test_models.py`:

```python
"""Unit tests for eval data models."""
import pytest
import yaml
from pathlib import Path
from tests.eval.src.models import Expectation, TestCase, ExpectationResult, CaseResult, EvalReport, Condition


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
            name="x", description="y", threshold=0.5,
            mandatory=True, kind="keyword",  # missing pattern
        )


def test_testcase_parses():
    raw = {
        "id": "user_01_what_is_kyma",
        "question": "What is Kyma?",
        "collection": "user",
        "source": "joule_inspired",
        "expectations": [
            {"name": "k8s", "description": "mentions k8s", "threshold": 0.5,
             "mandatory": True, "kind": "keyword", "pattern": "Kubernetes|k8s"},
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
    r = ExpectationResult(name="x", score=0.8, threshold=0.5, mandatory=True, passed=True, reason="ok")
    assert r.passed is True


def test_case_result_mandatory_fail_means_case_fails():
    r = CaseResult(
        case_id="c1",
        question="Q?",
        results={
            Condition.NO_TOOLS: [
                ExpectationResult(name="x", score=0.3, threshold=0.5, mandatory=True, passed=False, reason="bad"),
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
                ExpectationResult(name="x", score=0.8, threshold=0.5, mandatory=True, passed=True, reason="ok"),
                ExpectationResult(name="y", score=0.9, threshold=0.5, mandatory=False, passed=True, reason="ok"),
            ],
        },
    )
    assert r.condition_pass(Condition.MCP) is True


def test_eval_report_ci_pass():
    from tests.eval.src.models import ExpectationResult, CaseResult, EvalReport, Condition
    results = [
        CaseResult(case_id="c1", question="Q?", results={
            Condition.MCP: [
                ExpectationResult(name="x", score=0.9, threshold=0.5, mandatory=True, passed=True, reason="ok"),
            ],
        }),
    ]
    report = EvalReport(results=results, pass_threshold=0.75)
    assert report.mcp_pass_rate == 1.0
    assert report.ci_pass is True


def test_eval_report_ci_fail_mandatory():
    results = [
        CaseResult(case_id="c1", question="Q?", results={
            Condition.MCP: [
                ExpectationResult(name="x", score=0.3, threshold=0.5, mandatory=True, passed=False, reason="bad"),
            ],
        }),
    ]
    report = EvalReport(results=results, pass_threshold=0.75)
    assert report.ci_pass is False
```

- [ ] **Step 4: Run tests — expect failure**

```bash
cd /Users/I543305/sap/projects/kyma-AI/mcp/kyma-knowledge-mcp
uv run pytest tests/eval/tests/test_models.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` — models don't exist yet.

- [ ] **Step 5: Implement models.py**

Create `tests/eval/src/models.py`:

```python
"""Pydantic models for the MCP eval framework."""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class Condition(str, Enum):
    NO_TOOLS = "no_tools"
    WEB_SEARCH = "web_search"
    MCP = "mcp"


class Expectation(BaseModel):
    name: str
    description: str
    threshold: float = 0.5
    mandatory: bool = True
    kind: Literal["keyword", "llm"]
    pattern: str | None = None

    @model_validator(mode="after")
    def keyword_needs_pattern(self) -> "Expectation":
        if self.kind == "keyword" and not self.pattern:
            raise ValueError("keyword expectation requires a 'pattern' field")
        return self


class TestCase(BaseModel):
    id: str
    question: str
    collection: Literal["user", "contributor"]
    source: Literal["joule_inspired", "original"]
    expectations: list[Expectation] = Field(min_length=1)

    @classmethod
    def load_from_yaml(cls, path: Path) -> list["TestCase"]:
        raw = yaml.safe_load(path.read_text())
        return [cls(**item) for item in raw]


class ExpectationResult(BaseModel):
    name: str
    score: float
    threshold: float
    mandatory: bool
    passed: bool
    reason: str


class CaseResult(BaseModel):
    case_id: str
    question: str
    results: dict[Condition, list[ExpectationResult]] = Field(default_factory=dict)

    def condition_pass(self, condition: Condition) -> bool:
        expectations = self.results.get(condition, [])
        return all(e.passed for e in expectations if e.mandatory)

    def condition_pass_rate(self, condition: Condition) -> float:
        expectations = self.results.get(condition, [])
        if not expectations:
            return 0.0
        return sum(1 for e in expectations if e.passed) / len(expectations)


class EvalReport(BaseModel):
    results: list[CaseResult]
    pass_threshold: float = 0.75

    @property
    def mcp_mandatory_pass(self) -> bool:
        return all(r.condition_pass(Condition.MCP) for r in self.results)

    @property
    def mcp_pass_rate(self) -> float:
        all_exp = [
            e
            for r in self.results
            for e in r.results.get(Condition.MCP, [])
        ]
        if not all_exp:
            return 0.0
        return sum(1 for e in all_exp if e.passed) / len(all_exp)

    @property
    def ci_pass(self) -> bool:
        return self.mcp_mandatory_pass and self.mcp_pass_rate >= self.pass_threshold
```

- [ ] **Step 6: Run tests — expect green**

```bash
uv run pytest tests/eval/tests/test_models.py -v
```

Expected: all 10 tests pass.

- [ ] **Step 7: Commit**

```bash
git add tests/eval/ pyproject.toml
git commit -m "feat(eval): scaffold eval framework with Pydantic models"
```

---

## Task 2: Test case YAML files

**Files:**
- Create: `tests/eval/cases/user_docs.yaml`
- Create: `tests/eval/cases/contributor_docs.yaml`

No code tests needed — the YAML is validated by Task 1's `TestCase.load_from_yaml`.

- [ ] **Step 1: Create user_docs.yaml**

Create `tests/eval/cases/user_docs.yaml`:

```yaml
- id: user_01_what_is_kyma
  question: "What is Kyma?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_kubernetes
      description: "Response mentions Kubernetes or k8s"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "Kubernetes|k8s"
    - name: describes_purpose
      description: "Explains Kyma as a runtime or extension platform for cloud-native applications"
      threshold: 0.5
      mandatory: false
      kind: llm

- id: user_02_kyma_modules
  question: "What modules does Kyma offer and what do they do?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_core_modules
      description: "Mentions at least two of: eventing, serverless, telemetry, Istio, api-gateway"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: describes_module_purpose
      description: "Explains what at least one module is used for"
      threshold: 0.5
      mandatory: false
      kind: llm

- id: user_03_add_module
  question: "How do I add a Kyma module to my cluster?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_module_cr
      description: "Mentions enabling a module via the Kyma custom resource or the Kyma dashboard"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: mentions_kyma_cr
      description: "Mentions the Kyma CR or kyma.operator.kyma-project.io"
      threshold: 0.5
      mandatory: false
      kind: keyword
      pattern: "Kyma CR|kyma\\.operator|KymaCR|spec\\.modules"

- id: user_04_eventing_subscription
  question: "How can I subscribe to events in Kyma?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_subscription_cr
      description: "Mentions the Subscription custom resource"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "Subscription|subscription"
    - name: mentions_event_source
      description: "Mentions the event source or event type that the Subscription listens to"
      threshold: 0.5
      mandatory: true
      kind: llm

- id: user_05_serverless_function
  question: "How do I create a serverless Function in Kyma?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_function_cr
      description: "Mentions the Function custom resource or the serverless module"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "Function|serverless"
    - name: provides_steps_or_yaml
      description: "Provides a YAML example or steps to define and deploy the Function"
      threshold: 0.5
      mandatory: true
      kind: llm

- id: user_06_expose_endpoint
  question: "How do I expose an HTTP endpoint from my application in Kyma?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_apirule
      description: "Mentions APIRule as the mechanism to expose endpoints in Kyma"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "APIRule|apirule|api-rule"
    - name: provides_example
      description: "Provides an example or describes the spec fields needed"
      threshold: 0.5
      mandatory: false
      kind: llm

- id: user_07_btp_service_binding
  question: "How do I bind a SAP BTP service to my application running in Kyma?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_service_resources
      description: "Mentions ServiceInstance or ServiceBinding resources"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "ServiceInstance|ServiceBinding|serviceinstance|servicebinding"
    - name: mentions_btp_operator
      description: "Mentions the BTP Operator or btp-manager module"
      threshold: 0.5
      mandatory: true
      kind: llm

- id: user_08_telemetry_tracing
  question: "How do I configure distributed tracing in Kyma using the telemetry module?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_tracepipeline
      description: "Mentions TracePipeline custom resource or the telemetry module"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "TracePipeline|tracepipeline|telemetry"
    - name: mentions_otlp
      description: "Mentions OTLP or OpenTelemetry as the protocol for trace export"
      threshold: 0.5
      mandatory: false
      kind: keyword
      pattern: "OTLP|otlp|OpenTelemetry|opentelemetry"

- id: user_09_istio_usage
  question: "How do I use Istio in Kyma for traffic management or mutual TLS?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_istio_module
      description: "Mentions the Istio module in Kyma and how to enable it"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "Istio|istio|service mesh"
    - name: describes_use_case
      description: "Describes at least one Istio use case such as mTLS, traffic management, or sidecar injection"
      threshold: 0.5
      mandatory: false
      kind: llm

- id: user_10_kyma_regions
  question: "In which cloud regions is Kyma available?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_regions_or_hyperscalers
      description: "Mentions specific cloud regions or hyperscalers (AWS, GCP, Azure) where Kyma is available"
      threshold: 0.5
      mandatory: true
      kind: llm

- id: user_11_keda_autoscaling
  question: "How do I set up event-driven autoscaling with KEDA in Kyma?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_keda
      description: "Mentions KEDA or the KEDA module in Kyma"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "KEDA|keda"
    - name: mentions_scaledobject
      description: "Mentions ScaledObject or a trigger source for autoscaling"
      threshold: 0.5
      mandatory: false
      kind: keyword
      pattern: "ScaledObject|scaledobject|trigger"

- id: user_12_kyma_cli_install
  question: "How do I install Kyma using the Kyma CLI?"
  collection: user
  source: joule_inspired
  expectations:
    - name: mentions_kyma_cli
      description: "Mentions the Kyma CLI tool or kyma deploy command"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "kyma deploy|kyma CLI|kyma-cli|Kyma CLI"
    - name: provides_install_steps
      description: "Provides steps or commands to install Kyma on a cluster"
      threshold: 0.5
      mandatory: false
      kind: llm

# --- APIRule v2 showcase cases ---
# Expected: fail under no-tools (LLM gives v1 answers), pass under MCP

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
    - name: mentions_jwt_keywords
      description: "Mentions JWT issuer, JWKS URI, or token authentication"
      threshold: 0.5
      mandatory: false
      kind: keyword
      pattern: "jwt|JWT|issuer|jwks|JWKS"

- id: apirule_noauth_v2
  question: "How do I expose an APIRule endpoint without authentication in Kyma?"
  collection: user
  source: original
  expectations:
    - name: uses_v2_noauth
      description: "Shows NoAuth configuration using gateway.kyma-project.io/v2 spec, not accessStrategies: [{handler: noop}]"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: no_noop_handler
      description: "Does not suggest the 'noop' handler from v1 APIRule"
      threshold: 0.5
      mandatory: true
      kind: llm
```

- [ ] **Step 2: Create contributor_docs.yaml**

Create `tests/eval/cases/contributor_docs.yaml`:

```yaml
- id: contrib_01_api_gateway_contribution
  question: "How can I contribute to the Kyma api-gateway module?"
  collection: contributor
  source: joule_inspired
  expectations:
    - name: mentions_contribution_process
      description: "Mentions contribution guidelines, a CONTRIBUTING file, or a pull request process"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: mentions_local_dev
      description: "Mentions how to run tests or set up a local development environment for api-gateway"
      threshold: 0.5
      mandatory: true
      kind: llm

- id: contrib_02_eventing_architecture
  question: "What is the internal architecture of the Kyma eventing-manager?"
  collection: contributor
  source: joule_inspired
  expectations:
    - name: mentions_controllers
      description: "Mentions controllers, reconcilers, or the operator pattern used in eventing-manager"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: mentions_nats
      description: "Mentions NATS or the event backend that eventing-manager manages"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "NATS|nats|event backend|EventBackend"

- id: contrib_03_serverless_tests
  question: "How do I run integration tests for the Kyma serverless module?"
  collection: contributor
  source: joule_inspired
  expectations:
    - name: mentions_test_command
      description: "Provides a make command, go test command, or script to run integration tests"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: mentions_test_env
      description: "Mentions the required environment (e.g., a running cluster or k3d) for integration tests"
      threshold: 0.5
      mandatory: false
      kind: llm

- id: contrib_04_lifecycle_manager
  question: "What is the Kyma lifecycle-manager and how does it work?"
  collection: contributor
  source: joule_inspired
  expectations:
    - name: describes_lifecycle_manager_role
      description: "Describes lifecycle-manager as the component responsible for managing Kyma module lifecycle"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: mentions_kyma_cr
      description: "Mentions the Kyma CR or module CustomResourceDefinitions managed by lifecycle-manager"
      threshold: 0.5
      mandatory: false
      kind: keyword
      pattern: "Kyma CR|KymaCR|moduletemplate|ModuleTemplate|lifecycle"

- id: contrib_05_create_module
  question: "How do I create a new Kyma module from scratch?"
  collection: contributor
  source: joule_inspired
  expectations:
    - name: mentions_module_template
      description: "Mentions a module template, scaffold, or the kyma-module-template repository"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: mentions_operator_pattern
      description: "Mentions the operator pattern or controller-runtime as the basis for a Kyma module"
      threshold: 0.5
      mandatory: false
      kind: llm

- id: contrib_06_telemetry_pipeline_dev
  question: "How does the Kyma telemetry module handle log pipelines internally?"
  collection: contributor
  source: joule_inspired
  expectations:
    - name: mentions_logpipeline
      description: "Mentions LogPipeline CRD or the controller that reconciles log pipeline configuration"
      threshold: 0.5
      mandatory: true
      kind: keyword
      pattern: "LogPipeline|logpipeline|log pipeline"
    - name: mentions_fluent_or_otel
      description: "Mentions Fluent Bit or OTel collector as the underlying pipeline agent"
      threshold: 0.5
      mandatory: false
      kind: keyword
      pattern: "Fluent Bit|fluent-bit|fluentbit|OTel|otel|OpenTelemetry"

- id: contrib_07_api_gateway_integration_tests
  question: "How do I run the api-gateway integration tests locally?"
  collection: contributor
  source: original
  expectations:
    - name: provides_test_command
      description: "Provides a specific make target or command to run api-gateway integration tests"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: mentions_cluster_requirement
      description: "Mentions that a Kubernetes cluster (e.g. k3d or a real cluster) is required"
      threshold: 0.5
      mandatory: false
      kind: llm

- id: contrib_08_pr_process
  question: "What is the pull request process for contributing to a Kyma module repository?"
  collection: contributor
  source: original
  expectations:
    - name: mentions_pr_checks
      description: "Mentions CI checks, review process, or required approvals for merging a PR"
      threshold: 0.5
      mandatory: true
      kind: llm
    - name: mentions_codeowners
      description: "Mentions CODEOWNERS file or required reviewers"
      threshold: 0.5
      mandatory: false
      kind: keyword
      pattern: "CODEOWNERS|codeowners|code owner"
```

- [ ] **Step 3: Validate YAML parses correctly**

```bash
uv run python -c "
from pathlib import Path
from tests.eval.src.models import TestCase
user = TestCase.load_from_yaml(Path('tests/eval/cases/user_docs.yaml'))
contrib = TestCase.load_from_yaml(Path('tests/eval/cases/contributor_docs.yaml'))
print(f'user_docs: {len(user)} cases, contributor_docs: {len(contrib)} cases')
"
```

Expected output: `user_docs: 15 cases, contributor_docs: 8 cases`

- [ ] **Step 4: Commit**

```bash
git add tests/eval/cases/
git commit -m "feat(eval): add user_docs and contributor_docs test cases"
```

---

## Task 3: Agent abstraction

**Files:**
- Create: `tests/eval/src/agent.py`
- Create: `tests/eval/tests/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/eval/tests/test_agent.py`:

```python
"""Unit tests for agent abstraction."""
import json
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from tests.eval.src.models import Condition
from tests.eval.src.agent import GitHubModelsAgent, web_search


def test_web_search_returns_string():
    """web_search wraps duckduckgo and returns a non-empty string."""
    with patch("tests.eval.src.agent.DDGS") as mock_ddgs:
        mock_ddgs.return_value.__enter__.return_value.text.return_value = [
            {"title": "Kyma Docs", "href": "https://kyma-project.io", "body": "Kyma is a platform."}
        ]
        result = web_search("what is Kyma")
    assert "Kyma is a platform" in result


def test_github_models_agent_no_tools_calls_api():
    """no-tools condition calls chat completions without tools."""
    agent = GitHubModelsAgent(model="gpt-4o-mini", api_key="test-token")
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Kyma is a platform."
    mock_response.choices[0].message.tool_calls = None

    with patch.object(agent.client.chat.completions, "create", return_value=mock_response) as mock_create:
        result = agent.answer("What is Kyma?", Condition.NO_TOOLS, collection="user")

    assert result == "Kyma is a platform."
    call_kwargs = mock_create.call_args.kwargs
    assert "tools" not in call_kwargs or call_kwargs.get("tools") is None


def test_github_models_agent_web_search_provides_tool():
    """web-search condition passes web_search tool definition."""
    agent = GitHubModelsAgent(model="gpt-4o-mini", api_key="test-token")
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Kyma is..."
    mock_response.choices[0].message.tool_calls = None

    with patch.object(agent.client.chat.completions, "create", return_value=mock_response) as mock_create:
        agent.answer("What is Kyma?", Condition.WEB_SEARCH, collection="user")

    call_kwargs = mock_create.call_args.kwargs
    tool_names = [t["function"]["name"] for t in call_kwargs.get("tools", [])]
    assert "web_search" in tool_names


def test_github_models_agent_mcp_provides_rag_tools():
    """mcp condition passes search_kyma_docs tool and resolves tool calls."""
    agent = GitHubModelsAgent(model="gpt-4o-mini", api_key="test-token")

    # First call: model returns a tool call
    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = "search_kyma_docs"
    tool_call.function.arguments = json.dumps({"query": "Kyma overview", "top_k": 5})

    first_response = MagicMock()
    first_response.choices[0].message.content = None
    first_response.choices[0].message.tool_calls = [tool_call]

    # Second call: model returns final answer
    second_response = MagicMock()
    second_response.choices[0].message.content = "Kyma is a Kubernetes-based platform."
    second_response.choices[0].message.tool_calls = None

    mock_rag = AsyncMock()
    mock_rag.search_documents.return_value = MagicMock(
        documents=[MagicMock(content="Kyma extends Kubernetes.")]
    )

    with patch.object(agent.client.chat.completions, "create", side_effect=[first_response, second_response]):
        with patch("tests.eval.src.agent._get_rag_client", return_value=mock_rag):
            result = agent.answer("What is Kyma?", Condition.MCP, collection="user")

    assert "Kyma" in result
```

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/eval/tests/test_agent.py -v 2>&1 | head -20
```

Expected: `ImportError` — agent.py doesn't exist yet.

- [ ] **Step 3: Implement agent.py**

Create `tests/eval/src/agent.py`:

```python
"""LLM agent abstraction for eval conditions."""
from __future__ import annotations

import asyncio
import json
import subprocess
from typing import Protocol, runtime_checkable

from duckduckgo_search import DDGS
from openai import OpenAI

from tests.eval.src.models import Condition


def web_search(query: str, max_results: int = 5) -> str:
    """Free web search via DuckDuckGo — no API key required."""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    if not results:
        return "No results found."
    return "\n\n".join(
        f"Title: {r['title']}\nURL: {r['href']}\n{r['body']}" for r in results
    )


_WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for up-to-date information",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}

_SEARCH_KYMA_DOCS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_kyma_docs",
        "description": "Search Kyma user documentation for questions about using Kyma",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
}

_SEARCH_KYMA_CONTRIBUTOR_DOCS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_kyma_contributor_docs",
        "description": "Search Kyma contributor documentation for developer questions",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
}


def _get_rag_client(collection: str):  # type: ignore[return]
    """Lazily load LocalRAGClient directly (bypasses MCP protocol for eval speed)."""
    from kyma_knowledge_mcp.config import settings
    from kyma_knowledge_mcp.local_rag_client import LocalRAGClient

    return LocalRAGClient(
        index_path=settings.local_index_path,
        embed_model_override=settings.local_embed_model_override,
        collection_name=(
            settings.local_collection_name
            if collection == "user"
            else settings.local_contributor_collection_name
        ),
        reranker_model=settings.reranker_model,
        fetch_multiplier=settings.reranker_fetch_multiplier,
    )


@runtime_checkable
class Agent(Protocol):
    def answer(self, question: str, condition: Condition, collection: str) -> str: ...


class GitHubModelsAgent:
    """OpenAI-compatible agent backed by GitHub Models (free via GITHUB_TOKEN)."""

    def __init__(self, model: str = "gpt-4o-mini", api_key: str = "") -> None:
        import os
        self.model = model
        self.client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=api_key or os.environ["GITHUB_TOKEN"],
        )

    def answer(self, question: str, condition: Condition, collection: str) -> str:
        if condition == Condition.NO_TOOLS:
            return self._call_no_tools(question)
        if condition == Condition.WEB_SEARCH:
            return self._call_with_web_search(question)
        return self._call_with_mcp(question, collection)

    def _call_no_tools(self, question: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": question}],
        )
        return response.choices[0].message.content or ""

    def _call_with_web_search(self, question: str) -> str:
        messages: list[dict] = [{"role": "user", "content": question}]
        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[_WEB_SEARCH_TOOL],
                tool_choice="auto",
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                return msg.content or ""
            messages.append(msg.model_dump())
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                result = web_search(args["query"])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

    def _call_with_mcp(self, question: str, collection: str) -> str:
        rag = _get_rag_client(collection)
        tool_def = (
            _SEARCH_KYMA_DOCS_TOOL if collection == "user" else _SEARCH_KYMA_CONTRIBUTOR_DOCS_TOOL
        )
        messages: list[dict] = [{"role": "user", "content": question}]
        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[tool_def],
                tool_choice="auto",
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                return msg.content or ""
            messages.append(msg.model_dump())
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                search_result = asyncio.run(
                    rag.search_documents(args["query"], top_k=args.get("top_k", 5))
                )
                content = "\n\n".join(d.content for d in search_result.documents)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": content,
                })


class ClaudeCliAgent:
    """Local agent backed by Claude Code CLI (uses your active Claude session)."""

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self.model = model

    def answer(self, question: str, condition: Condition, collection: str) -> str:
        if condition == Condition.NO_TOOLS:
            return self._run_claude(question, extra_flags=["--tools", ""])
        if condition == Condition.WEB_SEARCH:
            return self._run_claude(question, extra_flags=[])  # web search is default in Claude
        return self._run_claude_with_mcp(question)

    def _run_claude(self, question: str, extra_flags: list[str]) -> str:
        import os, json as _json
        from pathlib import Path
        cmd = [
            "claude", "-p",
            "--model", self.model,
            "--output-format", "json",
            *extra_flags,
            question,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return f"[ERROR] claude exited {result.returncode}: {result.stderr[:300]}"
        try:
            return _json.loads(result.stdout).get("result", result.stdout)
        except Exception:
            return result.stdout.strip()

    def _run_claude_with_mcp(self, question: str) -> str:
        import json as _json, tempfile, os
        from pathlib import Path
        config = {
            "mcpServers": {
                "kyma-knowledge": {
                    "command": "uv",
                    "args": ["run", "kyma-knowledge-mcp"],
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            _json.dump(config, f)
            config_path = f.name
        try:
            cmd = [
                "claude", "-p",
                "--model", self.model,
                "--mcp-config", config_path,
                "--output-format", "json",
                question,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                return f"[ERROR] claude exited {result.returncode}: {result.stderr[:300]}"
            try:
                return _json.loads(result.stdout).get("result", result.stdout)
            except Exception:
                return result.stdout.strip()
        finally:
            os.unlink(config_path)
```

- [ ] **Step 4: Run tests — expect green**

```bash
uv run pytest tests/eval/tests/test_agent.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/eval/src/agent.py tests/eval/tests/test_agent.py
git commit -m "feat(eval): add agent abstraction for GitHub Models and Claude CLI"
```

---

## Task 4: Judge (keyword + GEval)

**Files:**
- Create: `tests/eval/src/judge.py`
- Create: `tests/eval/tests/test_judge.py`

- [ ] **Step 1: Write failing tests**

Create `tests/eval/tests/test_judge.py`:

```python
"""Unit tests for judge implementations."""
import re
from unittest.mock import MagicMock, patch
import pytest
from tests.eval.src.models import Expectation, ExpectationResult
from tests.eval.src.judge import KeywordJudge, GEvalJudge, score_expectation


def _kw_expectation(pattern: str, mandatory: bool = True) -> Expectation:
    return Expectation(
        name="test", description="test desc", threshold=0.5,
        mandatory=mandatory, kind="keyword", pattern=pattern,
    )


def _llm_expectation(description: str, mandatory: bool = True) -> Expectation:
    return Expectation(
        name="test", description=description, threshold=0.5,
        mandatory=mandatory, kind="llm",
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


def test_geval_judge_pass(monkeypatch):
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


def test_geval_judge_fail(monkeypatch):
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
```

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/eval/tests/test_judge.py -v 2>&1 | head -20
```

Expected: `ImportError`.

- [ ] **Step 3: Implement judge.py**

Create `tests/eval/src/judge.py`:

```python
"""Keyword and GEval judges for eval expectations."""
from __future__ import annotations

import re

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.eval.src.models import Expectation, ExpectationResult


class KeywordJudge:
    """Free, deterministic judge: regex match against the response."""

    def score(self, expectation: Expectation, response: str) -> ExpectationResult:
        pattern = expectation.pattern or ""
        matched = bool(re.search(pattern, response, re.IGNORECASE))
        score = 1.0 if matched else 0.0
        return ExpectationResult(
            name=expectation.name,
            score=score,
            threshold=expectation.threshold,
            mandatory=expectation.mandatory,
            passed=score >= expectation.threshold,
            reason=f"Pattern '{pattern}' {'matched' if matched else 'not found'} in response.",
        )


class GEvalJudge:
    """LLM-as-judge using DeepEval GEval with criteria-as-ground-truth."""

    def __init__(self, model: object) -> None:
        self.model = model

    def score(self, expectation: Expectation, response: str) -> ExpectationResult:
        metric = GEval(
            name=expectation.name,
            evaluation_steps=[expectation.description],
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=expectation.threshold,
            model=self.model,
            async_mode=False,
            verbose_mode=False,
        )
        test_case = LLMTestCase(
            input=expectation.description,
            actual_output=response,
        )
        metric.measure(test_case)
        return ExpectationResult(
            name=expectation.name,
            score=metric.score,
            threshold=expectation.threshold,
            mandatory=expectation.mandatory,
            passed=metric.is_successful(),
            reason=metric.reason or "",
        )


def score_expectation(
    expectation: Expectation,
    response: str,
    llm_judge: GEvalJudge,
) -> ExpectationResult:
    """Route to the correct judge based on expectation kind."""
    if expectation.kind == "keyword":
        return KeywordJudge().score(expectation, response)
    return llm_judge.score(expectation, response)
```

- [ ] **Step 4: Run tests — expect green**

```bash
uv run pytest tests/eval/tests/test_judge.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/eval/src/judge.py tests/eval/tests/test_judge.py
git commit -m "feat(eval): add keyword and GEval judge implementations"
```

---

## Task 5: Runner

**Files:**
- Create: `tests/eval/src/runner.py`
- Create: `tests/eval/tests/test_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/eval/tests/test_runner.py`:

```python
"""Unit tests for the eval runner."""
from unittest.mock import MagicMock, patch
import pytest
from tests.eval.src.models import (
    Condition, TestCase, Expectation, ExpectationResult, EvalReport
)
from tests.eval.src.runner import run_case, run_eval


def _make_case(case_id: str = "c1") -> TestCase:
    return TestCase(
        id=case_id,
        question="What is Kyma?",
        collection="user",
        source="original",
        expectations=[
            Expectation(name="k8s", description="mentions k8s", threshold=0.5,
                        mandatory=True, kind="keyword", pattern="Kubernetes|k8s"),
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
```

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/eval/tests/test_runner.py -v 2>&1 | head -20
```

Expected: `ImportError`.

- [ ] **Step 3: Implement runner.py**

Create `tests/eval/src/runner.py`:

```python
"""Parallel eval runner with retry and GitHub Actions output."""
from __future__ import annotations

import sys
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
        for attempt in range(max_retries):
            try:
                response = agent.answer(case.question, condition, case.collection)
                break
            except Exception as exc:
                if attempt == max_retries - 1:
                    response = f"[ERROR after {max_retries} retries] {exc}"
        exp_results = [
            score_expectation(exp, response, llm_judge)
            for exp in case.expectations
        ]
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
```

- [ ] **Step 4: Run tests — expect green**

```bash
uv run pytest tests/eval/tests/test_runner.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/eval/src/runner.py tests/eval/tests/test_runner.py
git commit -m "feat(eval): add parallel runner with retry and GitHub Actions output"
```

---

## Task 6: Report generation

**Files:**
- Create: `tests/eval/templates/report.html.j2`
- Create: `tests/eval/src/report.py`
- Create: `tests/eval/tests/test_report.py`

- [ ] **Step 1: Write failing tests**

Create `tests/eval/tests/test_report.py`:

```python
"""Unit tests for report generation."""
from pathlib import Path
from tests.eval.src.models import (
    Condition, CaseResult, ExpectationResult, EvalReport
)
from tests.eval.src.report import generate_markdown, generate_html


def _sample_report() -> EvalReport:
    results = [
        CaseResult(
            case_id="user_01_what_is_kyma",
            question="What is Kyma?",
            results={
                Condition.NO_TOOLS: [
                    ExpectationResult(name="k8s", score=0.0, threshold=0.5,
                                      mandatory=True, passed=False, reason="not found"),
                ],
                Condition.WEB_SEARCH: [
                    ExpectationResult(name="k8s", score=1.0, threshold=0.5,
                                      mandatory=True, passed=True, reason="matched"),
                ],
                Condition.MCP: [
                    ExpectationResult(name="k8s", score=1.0, threshold=0.5,
                                      mandatory=True, passed=True, reason="matched"),
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
```

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/eval/tests/test_report.py -v 2>&1 | head -20
```

Expected: `ImportError`.

- [ ] **Step 3: Create Jinja2 HTML template**

Create `tests/eval/templates/report.html.j2`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kyma Knowledge MCP — Eval Report</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 0 auto; padding: 2rem; color: #1a1a1a; }
    h1 { font-size: 1.5rem; }
    .meta { color: #666; font-size: 0.9rem; margin-bottom: 2rem; }
    .summary { display: flex; gap: 1.5rem; margin-bottom: 2rem; }
    .score-card { background: #f5f5f5; border-radius: 8px; padding: 1rem 1.5rem; min-width: 160px; }
    .score-card .label { font-size: 0.8rem; color: #666; text-transform: uppercase; }
    .score-card .value { font-size: 2rem; font-weight: bold; }
    .score-card.mcp .value { color: {% if report.ci_pass %}#16a34a{% else %}#dc2626{% endif %}; }
    .ci-badge { display: inline-block; padding: 0.3rem 0.8rem; border-radius: 4px; font-weight: bold;
                background: {% if report.ci_pass %}#dcfce7{% else %}#fee2e2{% endif %};
                color: {% if report.ci_pass %}#15803d{% else %}#b91c1c{% endif %}; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th { background: #f0f0f0; text-align: left; padding: 0.5rem 0.75rem; font-size: 0.85rem; }
    td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #e5e5e5; font-size: 0.85rem; vertical-align: top; }
    .pass { color: #16a34a; font-weight: 600; }
    .fail { color: #dc2626; font-weight: 600; }
    details summary { cursor: pointer; color: #2563eb; }
    .expectation { margin: 0.2rem 0; font-size: 0.8rem; }
    .bar-chart { display: flex; gap: 0.5rem; align-items: flex-end; height: 80px; margin: 1rem 0; }
    .bar { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; }
    .bar-fill { width: 60px; background: #3b82f6; border-radius: 4px 4px 0 0; }
    .bar-fill.mcp { background: #16a34a; }
    .bar-label { font-size: 0.75rem; color: #666; }
    .bar-pct { font-size: 0.8rem; font-weight: 600; }
  </style>
</head>
<body>
  <h1>Kyma Knowledge MCP — Evaluation Report</h1>
  <div class="meta">
    Generated: {{ generated_at }} &nbsp;·&nbsp;
    CI gate: <span class="ci-badge">{% if report.ci_pass %}PASS{% else %}FAIL{% endif %}</span>
    &nbsp;·&nbsp; Pass threshold: {{ (report.pass_threshold * 100) | int }}%
  </div>

  <div class="summary">
    {% for label, rate in condition_rates.items() %}
    <div class="score-card {% if label == 'MCP' %}mcp{% endif %}">
      <div class="label">{{ label }}</div>
      <div class="value">{{ (rate * 100) | int }}%</div>
      <div style="font-size:0.8rem;color:#666">pass rate</div>
    </div>
    {% endfor %}
  </div>

  <div class="bar-chart">
    {% for label, rate in condition_rates.items() %}
    <div class="bar">
      <div class="bar-pct">{{ (rate * 100) | int }}%</div>
      <div class="bar-fill {% if label == 'MCP' %}mcp{% endif %}"
           style="height: {{ [rate * 72, 4] | max | int }}px"></div>
      <div class="bar-label">{{ label }}</div>
    </div>
    {% endfor %}
  </div>

  <table>
    <thead>
      <tr>
        <th>Test Case</th>
        <th>Question</th>
        <th>No Tools</th>
        <th>Web Search</th>
        <th>MCP</th>
      </tr>
    </thead>
    <tbody>
      {% for result in report.results %}
      <tr>
        <td><code>{{ result.case_id }}</code></td>
        <td>{{ result.question }}</td>
        {% for condition in [Condition.NO_TOOLS, Condition.WEB_SEARCH, Condition.MCP] %}
        {% set exps = result.results.get(condition, []) %}
        <td>
          {% if exps %}
            {% set passed = exps | selectattr('passed') | list | length %}
            {% set total = exps | length %}
            {% set mandatory_ok = exps | selectattr('mandatory') | rejectattr('passed') | list | length == 0 %}
            <span class="{% if mandatory_ok and passed == total %}pass{% elif mandatory_ok %}pass{% else %}fail{% endif %}">
              {{ passed }}/{{ total }}
            </span>
            <details>
              <summary>details</summary>
              {% for e in exps %}
              <div class="expectation">
                {% if e.passed %}✓{% else %}✗{% endif %}
                <strong>{{ e.name }}</strong> ({{ "%.2f"|format(e.score) }}): {{ e.reason[:100] }}
              </div>
              {% endfor %}
            </details>
          {% else %}
            <span style="color:#999">—</span>
          {% endif %}
        </td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
```

- [ ] **Step 4: Implement report.py**

Create `tests/eval/src/report.py`:

```python
"""Generate HTML and Markdown reports from EvalReport."""
from __future__ import annotations

from datetime import datetime, UTC
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
    condition_rates = {
        _CONDITION_LABELS[c]: _condition_pass_rate(report, c) for c in Condition
    }
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
        f"CI gate: {'✅ PASS' if report.ci_pass else '❌ FAIL'}  ",
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
    lines += ["", "## Results", "", "| Case ID | Question | No Tools | Web Search | MCP |",
              "|---------|----------|----------|------------|-----|"]
    for result in report.results:
        cells = [f"`{result.case_id}`", result.question[:60]]
        for condition in Condition:
            exps = result.results.get(condition, [])
            if not exps:
                cells.append("—")
                continue
            passed = sum(1 for e in exps if e.passed)
            icon = "✅" if result.condition_pass(condition) else "❌"
            cells.append(f"{icon} {passed}/{len(exps)}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
```

- [ ] **Step 5: Run tests — expect green**

```bash
uv run pytest tests/eval/tests/test_report.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/eval/src/report.py tests/eval/templates/report.html.j2 tests/eval/tests/test_report.py
git commit -m "feat(eval): add HTML and Markdown report generation"
```

---

## Task 7: CLI entry point and GEval judge model wiring

**Files:**
- Create: `tests/eval/run_eval.py`
- Create: `tests/eval/src/judge_model.py`

- [ ] **Step 1: Create judge_model.py — DeepEval custom model backed by GitHub Models**

Create `tests/eval/src/judge_model.py`:

```python
"""DeepEval custom LLM backed by GitHub Models (free via GITHUB_TOKEN)."""
from __future__ import annotations

import os

from deepeval.models import DeepEvalBaseLLM
from openai import OpenAI


class GitHubModelsLLM(DeepEvalBaseLLM):
    """Wraps GitHub Models OpenAI-compatible endpoint as a DeepEval judge model."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=os.environ["GITHUB_TOKEN"],
        )

    def load_model(self) -> OpenAI:
        return self.client

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content or ""

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return self.model
```

- [ ] **Step 2: Create run_eval.py**

Create `tests/eval/run_eval.py`:

```python
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
import json
import os
import sys
from datetime import datetime, UTC
from pathlib import Path

CASES_DIR = Path(__file__).parent / "cases"
RESULTS_DIR = Path(__file__).parent / "results"
REPORT_DIR = Path(__file__).parent.parent.parent / "docs" / "eval-report"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP eval framework")
    parser.add_argument(
        "--agent", choices=["github-models", "claude-cli"], default="github-models",
        help="Agent backend to use (default: github-models for CI)",
    )
    parser.add_argument(
        "--judge-model", default="gpt-4o-mini",
        help="Model for GEval judge (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--agent-model", default="gpt-4o-mini",
        help="Model for the tested agent (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--filter", default="",
        help="Only run cases whose ID contains this string",
    )
    parser.add_argument(
        "--conditions", nargs="+",
        choices=["no_tools", "web_search", "mcp"], default=None,
        help="Conditions to run (default: all three)",
    )
    parser.add_argument(
        "--threshold", type=float,
        default=float(os.environ.get("EVAL_PASS_THRESHOLD", "0.75")),
        help="MCP pass rate threshold for CI gate (default: 0.75)",
    )
    parser.add_argument(
        "--save-results", action="store_true",
        help="Write JSON results to tests/eval/results/",
    )
    parser.add_argument(
        "--report", choices=["html", "markdown", "both"], default=None,
        help="Generate report(s) after eval",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="ThreadPoolExecutor max_workers (default: 4)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    from tests.eval.src.models import Condition, TestCase
    from tests.eval.src.agent import GitHubModelsAgent, ClaudeCliAgent
    from tests.eval.src.judge import GEvalJudge
    from tests.eval.src.judge_model import GitHubModelsLLM
    from tests.eval.src.runner import run_eval
    from tests.eval.src.report import generate_html, generate_markdown

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
            capture_output=True, text=True,
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
```

- [ ] **Step 3: Smoke test CLI help**

```bash
uv run python tests/eval/run_eval.py --help
```

Expected: prints usage without error.

- [ ] **Step 4: Commit**

```bash
git add tests/eval/run_eval.py tests/eval/src/judge_model.py
git commit -m "feat(eval): add CLI entry point and GitHub Models GEval judge wiring"
```

---

## Task 8: CI workflow and GitHub Pages

**Files:**
- Create: `.github/workflows/eval.yml`
- Create: `docs/eval-report/.gitkeep`

- [ ] **Step 1: Create docs/eval-report directory**

```bash
mkdir -p docs/eval-report
touch docs/eval-report/.gitkeep
git add docs/eval-report/.gitkeep
```

- [ ] **Step 2: Create eval.yml**

Create `.github/workflows/eval.yml`:

```yaml
name: MCP Eval

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: write   # needed for gh-pages push on main
  pages: write
  id-token: write

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --group eval

      - name: Run eval
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          uv run python tests/eval/run_eval.py \
            --agent github-models \
            --save-results \
            --report both

      - name: Upload results artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: eval-results-${{ github.sha }}
          path: tests/eval/results/

      - name: Deploy to GitHub Pages
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: docs/eval-report
          destination_dir: eval-report
```

- [ ] **Step 3: Enable GitHub Pages in repo settings**

In the GitHub repo → Settings → Pages → Source: select `gh-pages` branch, root `/`. After first workflow run the report will be at:
`https://<owner>.github.io/<repo>/eval-report/`

- [ ] **Step 4: Commit and push**

```bash
git add .github/workflows/eval.yml docs/eval-report/.gitkeep
git commit -m "feat(eval): add CI workflow and GitHub Pages deployment"
git push origin main
```

Expected: GitHub Actions triggers, runs eval, deploys HTML to GitHub Pages.

---

## Run all unit tests to verify everything compiles

```bash
uv run pytest tests/eval/tests/ -v
```

Expected: all tests pass (models: 10, judge: 8, runner: 5, report: 6 = 29 total).
