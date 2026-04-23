"""Local RAG client using ChromaDB + fastembed. No credentials required."""

import json
import logging
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

import chromadb
from fastembed import TextEmbedding
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".kyma-companion"
_INDEX_DOWNLOAD_URL = (
    "https://github.com/kyma-project/kyma-companion"
    "/releases/download/docs-index-latest/kyma-docs-index.tar.gz"
)
_FALLBACK_EMBED_MODEL = "BAAI/bge-small-en-v1.5"


class DocumentResult(BaseModel):
    content: str = Field(..., description="The document content")
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    documents: list[DocumentResult]
    count: int


class LocalRAGClient:
    """Offline RAG client: ChromaDB on disk + fastembed for query embedding.

    The embedding model is read from meta.json bundled inside the index
    archive, so it stays in sync with the index automatically. If meta.json
    is absent (e.g. hand-built test indexes), LOCAL_EMBED_MODEL is used.

    If index_path is empty, the latest index is auto-downloaded from GitHub
    Releases on first run and cached in ~/.kyma-companion/.
    """

    def __init__(
        self,
        index_path: str = "",
        embed_model_override: str = "",
        collection_name: str = "kyma_docs",
    ):
        resolved = self._ensure_index(index_path)

        # Model priority: override → meta.json → fallback
        embed_model = (
            embed_model_override
            or self._read_meta_model(resolved)
            or _FALLBACK_EMBED_MODEL
        )

        logger.info(f"Loading local ChromaDB from: {resolved}")
        self._collection = (
            chromadb.PersistentClient(path=str(resolved))
            .get_collection(collection_name)
        )
        logger.info(f"Loading fastembed model: {embed_model}")
        self._model = TextEmbedding(model_name=embed_model)
        logger.info(
            f"LocalRAGClient ready — {self._collection.count()} docs indexed"
        )

    @staticmethod
    def _read_meta_model(chroma_dir: Path) -> str:
        """Read the embedding model name from meta.json if present."""
        meta = chroma_dir / "meta.json"
        if meta.exists():
            data = json.loads(meta.read_text())
            model = data.get("embed_model", "")
            if model:
                logger.info(f"Embedding model from meta.json: {model}")
            return model
        return ""

    @classmethod
    def _ensure_index(cls, index_path: str) -> Path:
        if index_path:
            return cls._resolve_path(Path(index_path))

        cached = _CACHE_DIR / "index"
        if (cached / "chroma.sqlite3").exists():
            logger.info(f"Using cached index: {cached}")
            return cached

        return cls._download_and_cache()

    @classmethod
    def _download_and_cache(cls) -> Path:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        archive = _CACHE_DIR / "kyma-docs-index.tar.gz"
        dest = _CACHE_DIR / "index"

        logger.info(f"Downloading Kyma docs index → {archive}")
        logger.info("One-time download (~50 MB), cached in ~/.kyma-companion/")
        try:
            urllib.request.urlretrieve(_INDEX_DOWNLOAD_URL, archive)
        except Exception as e:
            raise RuntimeError(
                f"Auto-download failed: {e}\n"
                "Set LOCAL_INDEX_PATH to a manually downloaded index archive.\n"
                f"Download from: {_INDEX_DOWNLOAD_URL}"
            ) from e

        dest.mkdir(exist_ok=True)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(dest)
        archive.unlink()

        chroma_dir = next((p for p in dest.rglob("chroma.sqlite3")), None)
        return chroma_dir.parent if chroma_dir else dest

    @staticmethod
    def _resolve_path(p: Path) -> Path:
        if p.suffix in {".gz", ".tgz"} or str(p).endswith(".tar.gz"):
            if not any(p.parent.rglob("chroma.sqlite3")):
                with tarfile.open(p, "r:gz") as tar:
                    tar.extractall(p.parent)
            chroma_dir = next(p.parent.rglob("chroma.sqlite3"), None)
            return chroma_dir.parent if chroma_dir else p.parent
        return p

    async def search_documents(self, query: str, top_k: int = 5) -> SearchResponse:
        logger.info(f"Local search: query='{query}', top_k={top_k}")
        query_vec = list(self._model.embed([query]))[0].tolist()
        results = self._collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            include=["documents", "metadatas"],
        )
        documents = [
            DocumentResult(content=doc, metadata=meta or {})
            for doc, meta in zip(
                results["documents"][0], results["metadatas"][0]
            )
        ]
        return SearchResponse(query=query, documents=documents, count=len(documents))

    async def health_check(self) -> bool:
        return self._collection.count() > 0
