"""Unit tests for configuration settings."""

from kyma_knowledge_mcp.config import Settings


def test_defaults(monkeypatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    s = Settings(_env_file=None)
    assert s.log_level == "INFO"
    assert s.server_name == "kyma-knowledge-mcp"
    assert s.server_version == "0.1.0"
    assert s.local_collection_name == "kyma_docs"
    assert s.reranker_model == "ms-marco-TinyBERT-L-2-v2"
    assert s.reranker_fetch_multiplier == 3
    assert s.default_top_k == 10


def test_local_index_path_override(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_INDEX_PATH", "/tmp/my-index")
    s = Settings(_env_file=None)
    assert s.local_index_path == "/tmp/my-index"
