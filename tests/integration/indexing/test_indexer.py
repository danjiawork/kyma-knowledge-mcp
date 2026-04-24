"""Integration tests for the indexer — uses real fastembed (downloads model on first run)."""

import os
import chromadb
from pathlib import Path

from kyma_knowledge_mcp.indexing.indexer import FastEmbedEmbeddings, LocalFileIndexer

_EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")


def test_fast_embed_embeddings_returns_correct_shape() -> None:
    emb = FastEmbedEmbeddings(_EMBED_MODEL)
    vecs = emb.embed_documents(["Kyma is great", "APIRule exposes a service"])
    assert len(vecs) == 2
    assert all(len(v) == 384 for v in vecs)

    q = emb.embed_query("What is an APIRule?")
    assert len(q) == 384


def test_full_index_pipeline(tmp_path: Path) -> None:
    """Index real markdown files with real fastembed, verify chunks are stored."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "api-gateway.md").write_text(
        "# API Gateway\n\n## APIRule\n\n"
        "An APIRule exposes Kyma services via the API Gateway. "
        "Configure routing rules and authentication.\n\n" * 5
    )
    (docs_dir / "eventing.md").write_text(
        "# Eventing\n\n## Subscriptions\n\n"
        "Kyma Eventing uses NATS to deliver cloud events. "
        "Create a Subscription resource to receive events.\n\n" * 5
    )

    output_dir = str(tmp_path / "chroma")
    LocalFileIndexer(
        docs_path=str(docs_dir),
        embedding=FastEmbedEmbeddings(_EMBED_MODEL),
        output_dir=output_dir,
    ).index()

    col = chromadb.PersistentClient(path=output_dir).get_collection("kyma_docs")
    assert col.count() > 0
    docs = col.peek(col.count())["documents"]
    assert any("APIRule" in d for d in docs)
    assert any("Eventing" in d for d in docs)
