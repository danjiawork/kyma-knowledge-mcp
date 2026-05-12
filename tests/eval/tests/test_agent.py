"""Unit tests for agent abstraction."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from tests.eval.src.agent import GitHubModelsAgent, web_search
from tests.eval.src.models import Condition


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

    with patch.object(
        agent.client.chat.completions, "create", return_value=mock_response
    ) as mock_create:
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

    with patch.object(
        agent.client.chat.completions, "create", return_value=mock_response
    ) as mock_create:
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

    with patch.object(
        agent.client.chat.completions, "create", side_effect=[first_response, second_response]
    ):
        with patch("tests.eval.src.agent._get_rag_client", return_value=mock_rag):
            result = agent.answer("What is Kyma?", Condition.MCP, collection="user")

    assert "Kyma" in result
