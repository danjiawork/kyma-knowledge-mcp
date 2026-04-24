"""Unit tests for the local ChromaDB indexer (fake embeddings, no network)."""

import json
import tarfile
from pathlib import Path

import chromadb

from kyma_knowledge_mcp.indexing.indexer import LocalFileIndexer, _clean_metadata


class _FakeEmbedding:
    """Deterministic fake embeddings — avoids downloading a real model."""

    model_name = "fake-model"

    def embed_documents(self, texts: list[str], batch_size: int = 8) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    def embed_query(self, text: str) -> list[float]:  # noqa: ARG002
        return [0.1] * 384


def test_clean_metadata_replaces_none() -> None:
    result = _clean_metadata({"a": "hello", "b": None, "c": 42})
    assert result == {"a": "hello", "b": "", "c": 42}


def test_local_file_indexer_creates_chromadb(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "intro.md").write_text(
        "# Introduction\n\n" + ("Kyma is an application runtime. " * 10)
    )
    (docs_dir / "api.md").write_text(
        "# API Gateway\n\n## APIRule\n\n" + ("An APIRule exposes a service. " * 10)
    )

    output_dir = str(tmp_path / "chroma")
    LocalFileIndexer(
        docs_path=str(docs_dir),
        embedding=_FakeEmbedding(),  # type: ignore[arg-type]
        output_dir=output_dir,
    ).index()

    collection = chromadb.PersistentClient(path=output_dir).get_collection("kyma_docs")
    assert collection.count() > 0

    meta = json.loads((Path(output_dir) / "meta.json").read_text())
    assert meta["embed_model"] == "fake-model"
    assert "build_date" in meta


def test_package_creates_tar_gz(tmp_path: Path) -> None:
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()
    (chroma_dir / "dummy.db").write_text("data")

    archive_path = str(tmp_path / "index.tar.gz")
    LocalFileIndexer.package(str(chroma_dir), archive_path)

    assert Path(archive_path).exists()
    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
    assert any("dummy.db" in n for n in names)
