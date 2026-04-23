"""Configuration for Kyma Companion MCP Server."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Kyma Companion API configuration (remote mode, KC developers only)
    kyma_companion_url: str = "http://localhost:8000"
    kyma_companion_api_version: str = ""
    # Set to true to connect to KC backend instead of using local index
    use_remote_mode: bool = False

    # OAuth2 client credentials (optional, leave empty for unauthenticated)
    oauth2_token_url: str = ""
    oauth2_client_id: str = ""
    oauth2_client_secret: str = ""

    # Timeout settings (in seconds)
    request_timeout: int = 30

    # Local index (optional — enables offline mode, no credentials needed)
    local_index_path: str = ""
    # Override the embedding model read from meta.json (usually not needed)
    local_embed_model_override: str = ""
    local_collection_name: str = "kyma_docs"

    # Logging
    log_level: str = "INFO"

    # MCP Server settings
    server_name: str = "kyma-companion-mcp"
    server_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def rag_api_base_url(self) -> str:
        """Get the full RAG API base URL."""
        if self.kyma_companion_api_version:
            v = self.kyma_companion_api_version
            return f"{self.kyma_companion_url}/api/{v}/tools/kyma"
        return f"{self.kyma_companion_url}/api/tools/kyma"


# Global settings instance
settings = Settings()
