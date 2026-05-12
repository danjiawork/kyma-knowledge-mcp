"""LLM agent abstraction for eval conditions."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import subprocess
from typing import Protocol, runtime_checkable

from duckduckgo_search import DDGS
from openai import OpenAI

from tests.eval.src.models import Condition

MAX_TOOL_ROUNDS = 10


def web_search(query: str, max_results: int = 5) -> str:
    """Free web search via DuckDuckGo — no API key required."""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    if not results:
        return "No results found."
    return "\n\n".join(f"Title: {r['title']}\nURL: {r['href']}\n{r['body']}" for r in results)


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


def _get_rag_client(collection: str) -> LocalRAGClient:  # noqa: F821
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
        github_models_limiter.wait()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": question}],
        )
        return response.choices[0].message.content or ""

    def _call_with_web_search(self, question: str) -> str:
        messages: list[dict] = [{"role": "user", "content": question}]
        for _ in range(MAX_TOOL_ROUNDS):
            github_models_limiter.wait()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[_WEB_SEARCH_TOOL],
                tool_choice="auto",
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                return msg.content or ""
            # Append assistant message; fall back if model_dump() unavailable
            try:
                messages.append(msg.model_dump(exclude_none=True))
            except AttributeError:
                messages.append(
                    {"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls}
                )
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                result = web_search(args["query"])
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
        raise RuntimeError(f"Tool call loop exceeded {MAX_TOOL_ROUNDS} rounds")

    def _call_with_mcp(self, question: str, collection: str) -> str:
        rag = _get_rag_client(collection)
        tool_def = (
            _SEARCH_KYMA_DOCS_TOOL if collection == "user" else _SEARCH_KYMA_CONTRIBUTOR_DOCS_TOOL
        )
        messages: list[dict] = [{"role": "user", "content": question}]
        for _ in range(MAX_TOOL_ROUNDS):
            github_models_limiter.wait()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[tool_def],
                tool_choice="auto",
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                return msg.content or ""
            # Append assistant message; fall back if model_dump() unavailable
            try:
                messages.append(msg.model_dump(exclude_none=True))
            except AttributeError:
                messages.append(
                    {"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls}
                )
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(
                        asyncio.run,
                        rag.search_documents(args["query"], top_k=args.get("top_k", 5)),
                    )
                    search_result = fut.result()
                content = "\n\n".join(d.content for d in search_result.documents)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": content,
                    }
                )
        raise RuntimeError(f"Tool call loop exceeded {MAX_TOOL_ROUNDS} rounds")


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
        import json as _json

        cmd = [
            "claude",
            "-p",
            "--model",
            self.model,
            "--output-format",
            "json",
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
        import json as _json
        import tempfile

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
                "claude",
                "-p",
                "--model",
                self.model,
                "--mcp-config",
                config_path,
                "--output-format",
                "json",
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
