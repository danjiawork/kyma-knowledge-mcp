"""Tests for RAGClient and response models."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from kyma_companion_mcp.rag_client import RAGClient, SearchResponse, DocumentResult


# --- SearchResponse parsing ---

def test_parse_standard_format():
    data = {
        "query": "APIRule",
        "documents": [
            {"content": "doc1", "metadata": {"source": "a.md"}},
            {"content": "doc2", "metadata": {}},
        ],
        "count": 2,
    }
    resp = SearchResponse.from_api_response("APIRule", data)
    assert resp.count == 2
    assert resp.documents[0].content == "doc1"
    assert resp.documents[0].metadata["source"] == "a.md"


def test_parse_legacy_format():
    data = {"results": ["text one", "text two", "text three"]}
    resp = SearchResponse.from_api_response("query", data)
    assert resp.count == 3
    assert resp.documents[1].content == "text two"
    assert resp.documents[0].metadata == {}


def test_parse_legacy_skips_non_strings():
    data = {"results": ["valid", 123, None, "also valid"]}
    resp = SearchResponse.from_api_response("query", data)
    assert resp.count == 2
    assert resp.documents[0].content == "valid"
    assert resp.documents[1].content == "also valid"


def test_parse_empty_documents():
    data = {"query": "x", "documents": [], "count": 0}
    resp = SearchResponse.from_api_response("x", data)
    assert resp.count == 0
    assert resp.documents == []


# --- RAGClient.health_check ---

@pytest.mark.asyncio
async def test_health_check_healthy():
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "healthy"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        client = RAGClient(base_url="http://test", timeout=5)
        assert await client.health_check() is True


@pytest.mark.asyncio
async def test_health_check_unhealthy():
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "degraded"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        client = RAGClient(base_url="http://test", timeout=5)
        assert await client.health_check() is False


@pytest.mark.asyncio
async def test_health_check_connection_error():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        client = RAGClient(base_url="http://test", timeout=5)
        assert await client.health_check() is False


# --- RAGClient.search_documents ---

@pytest.mark.asyncio
async def test_search_documents_success():
    api_data = {
        "query": "APIRule",
        "documents": [{"content": "doc content", "metadata": {"source": "docs.md"}}],
        "count": 1,
    }
    mock_response = MagicMock()
    mock_response.json.return_value = api_data
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        client = RAGClient(base_url="http://test", timeout=5)
        result = await client.search_documents(query="APIRule", top_k=3)

    assert result.count == 1
    assert result.documents[0].content == "doc content"
    mock_client.post.assert_called_once_with(
        "http://test/search",
        json={"query": "APIRule", "top_k": 3},
    )


@pytest.mark.asyncio
async def test_search_documents_http_error():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock())
        )
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        client = RAGClient(base_url="http://test", timeout=5)
        with pytest.raises(httpx.HTTPError):
            await client.search_documents(query="test")
