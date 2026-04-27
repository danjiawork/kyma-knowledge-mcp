"""Local ChromaDB indexer using fastembed — no cloud credentials required."""

import gc
import hashlib
import json
import logging
import re
import tarfile
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import chromadb
import tiktoken
from fastembed import TextEmbedding
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

logger = logging.getLogger(__name__)

_encoding = tiktoken.encoding_for_model("gpt-4o")

HEADER1 = ("#", "Header1")
HEADER2 = ("##", "Header2")
HEADER3 = ("###", "Header3")
HEADER_LEVELS = [[HEADER1], [HEADER1, HEADER2], [HEADER1, HEADER2, HEADER3]]

COLLECTION_NAME = "kyma_docs"
COLLECTION_NAME_DEV = "kyma_docs_developer"
EMBED_BATCH_SIZE = 8
FASTEMBED_BATCH_SIZE = 4


# ── header text helpers ──────────────────────────────────────────────────────


def _remove_parentheses(text: str) -> str:
    return re.compile(r"\([^\[\]\(\)\{\}]+?\)").sub("", text)


def _remove_brackets(text: str) -> str:
    return re.compile(r"\[[^\[\]\(\)\{\}]+?\]").sub("", text)


def _remove_braces(text: str) -> str:
    return re.compile(r"\{[^\[\]\(\)\{\}]+?\}").sub("", text)


def _remove_header_brackets(text: str) -> str:
    current = len(text)
    while True:
        text = _remove_parentheses(_remove_brackets(_remove_braces(text)))
        if len(text) < current:
            current = len(text)
        else:
            break
    return text


def _extract_first_title(text: str) -> str | None:
    m = re.compile(r"^\s*#{1,6}\s+(.+?)(?:\n|$)", re.MULTILINE).search(text)
    return m.group(1).strip() if m else None


# ── document loading ─────────────────────────────────────────────────────────


def _load_markdown_files(docs_path: str) -> list[Document]:
    docs = []
    for p in Path(docs_path).rglob("*.md"):
        docs.append(
            Document(
                page_content=p.read_text(errors="replace"),
                metadata={"source": str(p)},
            )
        )
    return docs


# ── embedding wrapper ────────────────────────────────────────────────────────


class FastEmbedEmbeddings:
    """Thin wrapper around fastembed.TextEmbedding compatible with langchain."""

    def __init__(self, model_name: str, threads: int = 2) -> None:
        self._model = TextEmbedding(model_name, threads=threads)
        self.model_name = model_name

    def embed_documents(self, texts: list[str], batch_size: int = 8) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(texts, batch_size=batch_size)]

    def embed_query(self, text: str) -> list[float]:
        return [float(x) for x in list(self._model.embed([text]))[0]]


# ── indexer ──────────────────────────────────────────────────────────────────


def _clean_metadata(metadata: dict) -> dict:
    return {k: (v if v is not None else "") for k, v in metadata.items()}


class LocalFileIndexer:
    """Indexes markdown documents into a local ChromaDB persistent store."""

    def __init__(
        self,
        docs_path: str,
        embedding: FastEmbedEmbeddings,
        output_dir: str,
        collection_name: str = COLLECTION_NAME,
        min_chunk_token_count: int = 20,
        max_chunk_token_count: int = 1000,
    ) -> None:
        self.docs_path = docs_path
        self.embedding = embedding
        self.output_dir = output_dir
        self.collection_name = collection_name
        self.min_chunk_token_count = min_chunk_token_count
        self.max_chunk_token_count = max_chunk_token_count

    def _build_title(self, doc: Document) -> str:
        parts = [
            _remove_header_brackets(doc.metadata.get(h, "")).strip()
            for h in ("Header1", "Header2", "Header3")
        ]
        return " - ".join(p for p in parts if p)

    def _process_doc(
        self,
        doc: Document,
        level: int = 0,
        parent_title: str = "",
        module: str = "kyma",
        module_version: str = "latest",
    ) -> Generator[Document]:
        tokens = len(_encoding.encode(doc.page_content))
        if tokens <= self.min_chunk_token_count:
            return

        if tokens <= self.max_chunk_token_count or level >= len(HEADER_LEVELS):
            yield Document(
                page_content=doc.page_content,
                metadata={
                    "source": doc.metadata.get("source", ""),
                    "title": doc.metadata.get("title") or _extract_first_title(doc.page_content),
                    "module": module,
                    "version": module_version,
                },
            )
            return

        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=HEADER_LEVELS[level], strip_headers=False
        )
        for sub_doc in splitter.split_text(doc.page_content):
            if not sub_doc.metadata:
                logger.warning("skip chunk - no metadata")
                continue
            title = self._build_title(sub_doc)
            if not title:
                logger.warning("skip chunk - no title")
                continue
            if parent_title != title and (parent_title + " - ") not in title:
                title = f"{parent_title} - {title}" if parent_title else title

            chunk = Document(
                page_content=sub_doc.page_content,
                metadata={
                    "source": doc.metadata.get("source", ""),
                    "title": title,
                    "module": module,
                    "version": module_version,
                },
            )
            yield from self._process_doc(
                chunk, level + 1, parent_title=title if level == 0 else parent_title
            )

    def _get_chunks(self, docs: list[Document]) -> Generator[Document]:
        for doc in docs:
            yield from self._process_doc(doc)

    def _add_titles(self, docs: list[Document]) -> Generator[Document]:
        for chunk in self._get_chunks(docs):
            if chunk.metadata.get("title") is None:
                yield chunk
            else:
                t = chunk.metadata["title"]
                body = chunk.page_content
                prefix = f"# {t}\n" if body.strip().startswith(("#", "##", "###")) else f"# {t}\n\n"
                yield Document(
                    page_content=prefix + body.split("\n", 1)[-1]
                    if body.strip().startswith(("#", "##", "###"))
                    else prefix + body,
                    metadata=chunk.metadata,
                )

    def index(self) -> None:
        """Load, chunk, embed, and store documents in a ChromaDB persistent store."""

        docs = _load_markdown_files(self.docs_path)
        chunks = list(self._add_titles(docs))

        seen: set[str] = set()
        deduped: list[Document] = []
        for chunk in chunks:
            if chunk.page_content not in seen:
                seen.add(chunk.page_content)
                deduped.append(chunk)
        if len(deduped) < len(chunks):
            logger.warning(
                f"Removed {len(chunks) - len(deduped)} duplicate chunks before indexing."
            )
        chunks = deduped

        logger.info(f"Prepared {len(chunks)} chunks for indexing.")

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=self.output_dir)

        try:
            client.delete_collection(self.collection_name)
            logger.info(f"Deleted existing collection '{self.collection_name}'.")
        except Exception:
            pass

        collection = client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        total = len(chunks)
        for i in range(0, total, EMBED_BATCH_SIZE):
            batch = chunks[i : i + EMBED_BATCH_SIZE]
            texts = [d.page_content for d in batch]
            vectors = self.embedding.embed_documents(texts, batch_size=FASTEMBED_BATCH_SIZE)
            collection.add(
                ids=[hashlib.sha256(t.encode()).hexdigest() for t in texts],
                embeddings=vectors,  # type: ignore[arg-type]
                documents=texts,
                metadatas=[_clean_metadata(d.metadata) for d in batch],  # type: ignore[arg-type]
            )
            batch_num = i // EMBED_BATCH_SIZE + 1
            logger.info(f"Indexed batch {batch_num}/{(total - 1) // EMBED_BATCH_SIZE + 1}")
            gc.collect()

        meta_path = Path(self.output_dir) / "meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "embed_model": self.embedding.model_name,
                    "build_date": datetime.now(UTC).strftime("%Y-%m-%d"),
                }
            )
        )
        logger.info(f"Successfully indexed {total} chunks to '{self.output_dir}'.")

    @staticmethod
    def package(output_dir: str, archive_path: str) -> None:
        """Package the ChromaDB directory into a .tar.gz archive."""
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(output_dir, arcname=Path(output_dir).name)
        logger.info(f"Created archive: {archive_path}")
