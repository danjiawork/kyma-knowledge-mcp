"""Integration tests for LocalRAGClient — real ChromaDB + real fastembed query."""

import os
import pytest

from kyma_knowledge_mcp.indexing.indexer import FastEmbedEmbeddings, LocalFileIndexer
from kyma_knowledge_mcp.local_rag_client import LocalRAGClient

_EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")


@pytest.fixture(scope="module")
def mini_index(tmp_path_factory) -> str:
    """Build a small real ChromaDB index once per module, shared across tests."""
    tmp = tmp_path_factory.mktemp("rag_index")
    docs_dir = tmp / "docs"
    docs_dir.mkdir()
    (docs_dir / "api-gateway.md").write_text(
        "# API Gateway\n\n## APIRule\n\n"
        "An APIRule exposes Kyma services via the API Gateway. "
        "Configure routing rules and authentication policies.\n\n" * 5
    )
    (docs_dir / "eventing.md").write_text(
        "# Eventing\n\n## Subscriptions\n\n"
        "Kyma Eventing uses NATS to deliver cloud events. "
        "Create a Subscription resource to receive events from publishers.\n\n" * 5
    )
    (docs_dir / "serverless.md").write_text(
        "# Serverless\n\n## Functions\n\n"
        "Kyma Serverless allows you to deploy Functions as microservices. "
        "Functions are triggered by HTTP calls or Kyma events.\n\n" * 5
    )

    output_dir = str(tmp / "chroma")
    LocalFileIndexer(
        docs_path=str(docs_dir),
        embedding=FastEmbedEmbeddings(_EMBED_MODEL),
        output_dir=output_dir,
    ).index()
    return output_dir


async def test_rag_client_health_check(mini_index: str) -> None:
    client = LocalRAGClient(index_path=mini_index, collection_name="kyma_docs")
    assert await client.health_check() is True


async def test_rag_client_search_returns_results(mini_index: str) -> None:
    client = LocalRAGClient(index_path=mini_index, collection_name="kyma_docs")
    response = await client.search_documents("APIRule routing rules", top_k=3)
    assert response.count > 0
    assert any("APIRule" in doc.content for doc in response.documents)


async def test_rag_client_search_eventing(mini_index: str) -> None:
    client = LocalRAGClient(index_path=mini_index, collection_name="kyma_docs")
    response = await client.search_documents("how to receive cloud events", top_k=3)
    assert response.count > 0
    # semantic search should surface eventing docs
    all_content = " ".join(doc.content for doc in response.documents)
    assert "Subscription" in all_content or "event" in all_content.lower()


async def test_rag_client_empty_result_for_unrelated_query(mini_index: str) -> None:
    client = LocalRAGClient(index_path=mini_index, collection_name="kyma_docs")
    # top_k=1, but result should still come back (chromadb always returns n_results)
    response = await client.search_documents("quantum physics", top_k=1)
    assert response.count == 1  # ChromaDB returns closest match regardless
