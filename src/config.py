"""Configuration for Kyma Companion MCP Server."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Kyma Companion API configuration
    kyma_companion_url: str = "http://localhost:8000"
    kyma_companion_api_version: str = ""

    # Timeout settings (in seconds)
    request_timeout: int = 30

    # Logging
    log_level: str = "INFO"

    # MCP Server settings
    server_name: str = "kyma-companion-mcp"
    server_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def rag_api_base_url(self) -> str:
        """Get the full RAG API base URL."""
        if self.kyma_companion_api_version:
            return f"{self.kyma_companion_url}/api/{self.kyma_companion_api_version}/rag"
        return f"{self.kyma_companion_url}/api/rag"


# Global settings instance
settings = Settings()
