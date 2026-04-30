"""Configuration for Kyma Knowledge MCP Server."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Local index — if empty, auto-downloaded from GitHub Releases on first run
    local_index_path: str = ""
    # Override the embedding model read from meta.json (usually not needed)
    local_embed_model_override: str = ""
    local_collection_name: str = "kyma_docs"
    local_contributor_collection_name: str = "kyma_contributor_docs"

    # Default number of results returned by user-facing search tools.
    # Tools that expose top_k use this as their fallback when the caller omits it.
    default_top_k: int = 10

    # Reranker — cross-encoder model used to re-score vector-search candidates.
    # Enabled by default with a lightweight TinyBERT model (~30 MB, Apache 2.0).
    # Set to empty string to disable. Alternative: "ms-marco-MiniLM-L-12-v2" (higher
    # quality, ~130 MB, ~4-5× slower).
    reranker_model: str = "ms-marco-TinyBERT-L-2-v2"
    # Candidates fetched per final result: fetch_n = top_k × multiplier
    reranker_fetch_multiplier: int = 3

    # Logging
    log_level: str = "INFO"

    # MCP Server settings
    server_name: str = "kyma-knowledge-mcp"
    server_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
