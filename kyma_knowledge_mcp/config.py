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
    local_dev_collection_name: str = "kyma_docs_developer"

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
