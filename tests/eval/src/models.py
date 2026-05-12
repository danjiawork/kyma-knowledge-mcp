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
    def keyword_needs_pattern(self) -> Expectation:
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
    def load_from_yaml(cls, path: Path) -> list[TestCase]:
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
