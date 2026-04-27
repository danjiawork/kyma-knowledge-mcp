"""Unit tests for MCP server tool definitions and handlers."""

from unittest.mock import AsyncMock, patch

from kyma_knowledge_mcp.local_rag_client import DocumentResult, SearchResponse
from kyma_knowledge_mcp.server import (
    handle_search_kyma_contributor_docs,
    handle_search_kyma_docs,
    list_tools,
)


def _make_response(content: str = "doc content") -> SearchResponse:
    return SearchResponse(
        query="test",
        documents=[DocumentResult(content=content, metadata={"source": "test.md"})],
        count=1,
    )


def _empty_response() -> SearchResponse:
    return SearchResponse(query="test", documents=[], count=0)


async def test_list_tools_returns_two_tools() -> None:
    tools = await list_tools()
    names = {t.name for t in tools}
    assert names == {"search_kyma_docs", "search_kyma_contributor_docs"}


async def test_all_tools_have_required_schema_fields() -> None:
    for tool in await list_tools():
        assert tool.name and tool.description
        assert "properties" in tool.inputSchema and "required" in tool.inputSchema


async def test_search_kyma_docs_returns_results() -> None:
    with patch("kyma_knowledge_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_make_response("kyma info"))
        result = await handle_search_kyma_docs({"query": "APIRule", "top_k": 3})
    assert "APIRule" in result[0].text and "kyma info" in result[0].text


async def test_search_kyma_docs_default_top_k() -> None:
    with patch("kyma_knowledge_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_empty_response())
        await handle_search_kyma_docs({"query": "test"})
        mock_rag.search_documents.assert_called_once_with(query="test", top_k=10)


async def test_search_kyma_docs_top_k_passed_through() -> None:
    with patch("kyma_knowledge_mcp.server.rag_client") as mock_rag:
        mock_rag.search_documents = AsyncMock(return_value=_empty_response())
        await handle_search_kyma_docs({"query": "test", "top_k": 3})
        mock_rag.search_documents.assert_called_once_with(query="test", top_k=3)


async def test_search_kyma_contributor_docs_returns_results() -> None:
    mock_dev = AsyncMock()
    mock_dev._available = True
    mock_dev.search_documents = AsyncMock(return_value=_make_response("contrib info"))
    with patch("kyma_knowledge_mcp.server.rag_client_dev", mock_dev):
        result = await handle_search_kyma_contributor_docs(
            {"query": "how to contribute", "top_k": 3}
        )
    assert "contrib info" in result[0].text


async def test_search_kyma_contributor_docs_not_indexed() -> None:
    mock_dev = AsyncMock()
    mock_dev._available = False
    with patch("kyma_knowledge_mcp.server.rag_client_dev", mock_dev):
        result = await handle_search_kyma_contributor_docs({"query": "test"})
    assert "not yet indexed" in result[0].text


async def test_search_kyma_contributor_docs_default_top_k() -> None:
    mock_dev = AsyncMock()
    mock_dev._available = True
    mock_dev.search_documents = AsyncMock(return_value=_empty_response())
    with patch("kyma_knowledge_mcp.server.rag_client_dev", mock_dev):
        await handle_search_kyma_contributor_docs({"query": "test"})
        mock_dev.search_documents.assert_called_once_with(query="test", top_k=10)
