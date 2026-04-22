"""Tests for MCP server tool definitions and handlers."""

import pytest
from unittest.mock import AsyncMock, patch

from kyma_companion_mcp.rag_client import SearchResponse, DocumentResult
from kyma_companion_mcp.server import (
    list_tools,
    handle_search_kyma_docs,
    handle_get_component_docs,
    handle_explain_kyma_concept,
    handle_get_troubleshooting_guide,
)


# --- Tool registry ---

@pytest.mark.asyncio
async def test_list_tools_returns_four_tools():
    tools = await list_tools()
    names = {t.name for t in tools}
    assert names == {
        "search_kyma_docs",
        "get_component_docs",
        "explain_kyma_concept",
        "get_troubleshooting_guide",
    }


@pytest.mark.asyncio
async def test_all_tools_have_required_schema_fields():
    tools = await list_tools()
    for tool in tools:
        assert tool.name
        assert tool.description
        assert "properties" in tool.inputSchema
        assert "required" in tool.inputSchema


# --- Handler helpers ---

def _make_search_response(content: str = "doc content") -> SearchResponse:
    return SearchResponse(
        query="test",
        documents=[DocumentResult(content=content, metadata={"source": "test.md"})],
        count=1,
    )


def _empty_search_response() -> SearchResponse:
    return SearchResponse(query="test", documents=[], count=0)


# --- search_kyma_docs ---

@pytest.mark.asyncio
async def test_search_kyma_docs_returns_results():
    with patch("kyma_companion_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_make_search_response("kyma info"))
        result = await handle_search_kyma_docs({"query": "APIRule", "top_k": 3})

    assert len(result) == 1
    assert "APIRule" in result[0].text
    assert "kyma info" in result[0].text


@pytest.mark.asyncio
async def test_search_kyma_docs_default_top_k():
    with patch("kyma_companion_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_empty_search_response())
        await handle_search_kyma_docs({"query": "test"})
        mock_rag.search_documents.assert_called_once_with(query="test", top_k=5)


# --- get_component_docs ---

@pytest.mark.asyncio
async def test_get_component_docs_builds_query():
    with patch("kyma_companion_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_make_search_response())
        await handle_get_component_docs({"component": "api-gateway"})
        call_args = mock_rag.search_documents.call_args
        assert "api-gateway" in call_args.kwargs["query"]


@pytest.mark.asyncio
async def test_get_component_docs_formats_heading():
    with patch("kyma_companion_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_make_search_response())
        result = await handle_get_component_docs({"component": "serverless"})
        assert "Serverless" in result[0].text


# --- explain_kyma_concept ---

@pytest.mark.asyncio
async def test_explain_kyma_concept_found():
    with patch("kyma_companion_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_make_search_response("modules are..."))
        result = await handle_explain_kyma_concept({"concept": "Kyma modules"})
        assert "modules are..." in result[0].text


@pytest.mark.asyncio
async def test_explain_kyma_concept_not_found():
    with patch("kyma_companion_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_empty_search_response())
        result = await handle_explain_kyma_concept({"concept": "unknown"})
        assert "No documentation found" in result[0].text


# --- get_troubleshooting_guide ---

@pytest.mark.asyncio
async def test_get_troubleshooting_guide_with_issue():
    with patch("kyma_companion_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_make_search_response())
        await handle_get_troubleshooting_guide({"component": "api-gateway", "issue": "503 error"})
        call_args = mock_rag.search_documents.call_args
        assert "503 error" in call_args.kwargs["query"]


@pytest.mark.asyncio
async def test_get_troubleshooting_guide_without_issue():
    with patch("kyma_companion_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_make_search_response())
        await handle_get_troubleshooting_guide({"component": "serverless"})
        call_args = mock_rag.search_documents.call_args
        assert "serverless" in call_args.kwargs["query"]


@pytest.mark.asyncio
async def test_get_troubleshooting_guide_no_results():
    with patch("kyma_companion_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_empty_search_response())
        result = await handle_get_troubleshooting_guide({"component": "eventing"})
        assert "No troubleshooting guides found" in result[0].text
