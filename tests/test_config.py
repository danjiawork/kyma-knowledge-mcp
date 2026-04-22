"""Tests for configuration settings."""

from kyma_companion_mcp.config import Settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("KYMA_COMPANION_URL", raising=False)
    monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    s = Settings(_env_file=None)
    assert s.kyma_companion_url == "http://localhost:8000"
    assert s.request_timeout == 30
    assert s.log_level == "INFO"
    assert s.server_name == "kyma-companion-mcp"
    assert s.server_version == "0.1.0"


def test_rag_api_base_url_no_version():
    s = Settings(kyma_companion_url="http://example.com", kyma_companion_api_version="")
    assert s.rag_api_base_url == "http://example.com/api/tools/kyma"


def test_rag_api_base_url_with_version():
    s = Settings(kyma_companion_url="http://example.com", kyma_companion_api_version="v1")
    assert s.rag_api_base_url == "http://example.com/api/v1/tools/kyma"


def test_env_override(monkeypatch):
    monkeypatch.setenv("KYMA_COMPANION_URL", "http://custom:9000")
    monkeypatch.setenv("REQUEST_TIMEOUT", "60")
    s = Settings()
    assert s.kyma_companion_url == "http://custom:9000"
    assert s.request_timeout == 60
