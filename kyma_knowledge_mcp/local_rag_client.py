"""Local RAG client using ChromaDB + fastembed. No credentials required."""

import json
import logging
import tarfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import chromadb
from fastembed import TextEmbedding
from flashrank import Ranker, RerankRequest
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".kyma-knowledge-mcp"
_INDEX_DOWNLOAD_URL = (
    "https://github.com/danjiawork/kyma-knowledge-mcp"
    "/releases/download/docs-index-latest/kyma-docs-index.tar.gz"
)
_FALLBACK_EMBED_MODEL = "BAAI/bge-base-en-v1.5"
_CACHE_MAX_AGE_DAYS = 8  # re-download if cached index is older than this


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
    is absent (e.g. hand-built test indexes), _FALLBACK_EMBED_MODEL is used.

    If index_path is empty, the latest index is auto-downloaded from GitHub
    Releases on first run and cached in ~/.kyma-knowledge-mcp/. The cache is
    refreshed automatically when it is older than _CACHE_MAX_AGE_DAYS.

    When reranker_model is set, a cross-encoder reranker (via flashrank) is
    loaded and used to re-score candidates fetched from the vector store before
    returning the final top_k results.  Set fetch_multiplier to control how
    many extra candidates are fetched for reranking (fetch_n = top_k × multiplier).
    """

    def __init__(
        self,
        index_path: str = "",
        embed_model_override: str = "",
        collection_name: str = "kyma_docs",
        reranker_model: str = "",
        fetch_multiplier: int = 3,
    ):
        resolved = self._ensure_index(index_path)

        meta = self._read_meta(resolved)
        embed_model = embed_model_override or meta.get("embed_model", "") or _FALLBACK_EMBED_MODEL
        build_date = meta.get("build_date", "unknown")

        logger.info(f"Loading local ChromaDB from: {resolved}")
        logger.info(f"Index build date: {build_date}")
        chroma_client = chromadb.PersistentClient(path=str(resolved))
        try:
            self._collection: chromadb.Collection | None = chroma_client.get_collection(
                collection_name
            )
            self._available = True
        except ValueError:
            logger.warning(
                f"Collection '{collection_name}' not found in index at {resolved}. "
                "Rebuild the index to enable this collection."
            )
            self._collection = None
            self._available = False
            return
        logger.info(f"Loading fastembed model: {embed_model}")
        self._model = TextEmbedding(model_name=embed_model)
        logger.info(f"LocalRAGClient ready — {self._collection.count()} docs indexed")

        self._reranker: Ranker | None = None
        self._fetch_multiplier = fetch_multiplier
        if reranker_model:
            reranker_cache = str(_CACHE_DIR / "reranker")
            logger.info(f"Loading reranker model: {reranker_model}")
            self._reranker = Ranker(model_name=reranker_model, cache_dir=reranker_cache)
            logger.info("Reranker ready")

    @staticmethod
    def _read_meta(chroma_dir: Path) -> dict[str, Any]:
        """Read meta.json and return its contents, or empty dict if absent."""
        meta = chroma_dir / "meta.json"
        if meta.exists():
            try:
                return dict(json.loads(meta.read_text()))
            except Exception:
                logger.warning(f"Failed to parse meta.json at {meta}")
        return {}

    @staticmethod
    def _is_cache_stale(chroma_dir: Path, max_age_days: int = _CACHE_MAX_AGE_DAYS) -> bool:
        """Return True if the cached index is older than max_age_days."""
        meta = chroma_dir / "meta.json"
        if not meta.exists():
            return True
        try:
            data = json.loads(meta.read_text())
            build_date_str = data.get("build_date", "")
            if not build_date_str:
                return True
            build_date = datetime.strptime(build_date_str, "%Y-%m-%d").replace(tzinfo=UTC)
            age_days = (datetime.now(UTC) - build_date).days
            if age_days >= max_age_days:
                logger.info(f"Cached index is {age_days} days old — refreshing")
                return True
            return False
        except Exception:
            return True

    @classmethod
    def _ensure_index(cls, index_path: str) -> Path:
        if index_path:
            return cls._resolve_path(Path(index_path))

        cached = _CACHE_DIR / "index"
        chroma_sqlite = next(cached.rglob("chroma.sqlite3"), None) if cached.exists() else None
        if chroma_sqlite and not cls._is_cache_stale(chroma_sqlite.parent):
            logger.info(f"Using cached index: {chroma_sqlite.parent}")
            return chroma_sqlite.parent

        return cls._download_and_cache()

    @classmethod
    def _download_and_cache(cls) -> Path:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        archive = _CACHE_DIR / "kyma-docs-index.tar.gz"
        dest = _CACHE_DIR / "index"

        logger.info(f"Downloading Kyma docs index → {archive}")
        logger.info("One-time download (~50 MB), cached in ~/.kyma-knowledge-mcp/")
        try:
            urllib.request.urlretrieve(_INDEX_DOWNLOAD_URL, archive)
        except Exception as e:
            raise RuntimeError(
                f"Auto-download failed: {e}\n"
                "Set LOCAL_INDEX_PATH to a manually downloaded index archive."
                "\n"
                f"Download from: {_INDEX_DOWNLOAD_URL}"
            ) from e

        dest.mkdir(exist_ok=True)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(dest, filter="data")
        archive.unlink()

        chroma_dir = next((p for p in dest.rglob("chroma.sqlite3")), None)
        return chroma_dir.parent if chroma_dir else dest

    @staticmethod
    def _resolve_path(p: Path) -> Path:
        if p.suffix in {".gz", ".tgz"} or str(p).endswith(".tar.gz"):
            if not any(p.parent.rglob("chroma.sqlite3")):
                with tarfile.open(p, "r:gz") as tar:
                    tar.extractall(p.parent, filter="data")
            chroma_dir = next(p.parent.rglob("chroma.sqlite3"), None)
            return chroma_dir.parent if chroma_dir else p.parent
        return p

    async def search_documents(self, query: str, top_k: int = 10) -> SearchResponse:
        if not self._available or self._collection is None:
            return SearchResponse(query=query, documents=[], count=0)

        fetch_n = (
            min(top_k * self._fetch_multiplier, self._collection.count())
            if self._reranker
            else top_k
        )
        logger.info(f"Local search: query='{query}', top_k={top_k}, fetch_n={fetch_n}")

        query_vec = list(self._model.embed([query]))[0].tolist()
        results = self._collection.query(
            query_embeddings=[query_vec],
            n_results=fetch_n,
            include=["documents", "metadatas"],
        )
        assert results["documents"] is not None
        assert results["metadatas"] is not None
        documents = [
            DocumentResult(content=doc, metadata=dict(meta) if meta else {})
            for doc, meta in zip(results["documents"][0], results["metadatas"][0], strict=False)
        ]

        if self._reranker and documents:
            passages = [{"id": i, "text": doc.content} for i, doc in enumerate(documents)]
            reranked = self._reranker.rerank(RerankRequest(query=query, passages=passages))
            id_to_doc = dict(enumerate(documents))
            documents = [id_to_doc[r["id"]] for r in reranked[:top_k]]

        return SearchResponse(query=query, documents=documents, count=len(documents))

    async def health_check(self) -> bool:
        return self._available and self._collection is not None and self._collection.count() > 0
