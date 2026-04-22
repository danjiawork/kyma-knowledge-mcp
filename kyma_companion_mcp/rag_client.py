"""RAG client for communicating with Kyma Companion API."""

import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

from .config import settings

logger = logging.getLogger(__name__)


class DocumentResult(BaseModel):
    """A single document result from RAG search."""

    content: str = Field(..., description="The document content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class SearchResponse(BaseModel):
    """Response model for RAG search."""

    query: str = Field(..., description="The original query")
    documents: list[DocumentResult] = Field(..., description="List of relevant documents")
    count: int = Field(..., description="Number of documents returned")

    @classmethod
    def from_api_response(cls, query: str, api_data: dict[str, Any]) -> "SearchResponse":
        """
        Create SearchResponse from various API response formats.

        Handles both:
        - Legacy format: {"results": ["text1", "text2"]}
        - Standard format: {"query": "...", "documents": [...], "count": 3}

        Args:
            query: The original query string
            api_data: Raw API response data

        Returns:
            SearchResponse instance
        """
        # Handle legacy format with 'results' field
        if "results" in api_data and "documents" not in api_data:
            results = api_data.get("results", [])
            documents = [
                DocumentResult(content=result, metadata={})
                for result in results
                if isinstance(result, str)
            ]
            return cls(query=query, documents=documents, count=len(documents))

        # Handle standard format or create from existing structure
        return cls(
            query=api_data.get("query", query),
            documents=api_data.get("documents", []),
            count=api_data.get("count", len(api_data.get("documents", [])))
        )


class RAGClient:
    """Client for interacting with Kyma Companion RAG API."""

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        self.base_url = base_url or settings.rag_api_base_url
        self.timeout = timeout or settings.request_timeout
        self._token: str | None = None
        self._token_expires_at: float = 0
        logger.info(f"Initialized RAG client with base URL: {self.base_url}")

    def _oauth2_configured(self) -> bool:
        return bool(
            settings.oauth2_token_url
            and settings.oauth2_client_id
            and settings.oauth2_client_secret
        )

    async def _get_access_token(self) -> str:
        # Return cached token if still valid (with 30s buffer)
        if self._token and time.monotonic() < self._token_expires_at - 30:
            return self._token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                settings.oauth2_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.oauth2_client_id,
                    "client_secret": settings.oauth2_client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

        self._token = data["access_token"]
        self._token_expires_at = time.monotonic() + data.get("expires_in", 3600)
        logger.info("OAuth2 access token acquired")
        return self._token

    async def _auth_headers(self) -> dict[str, str]:
        if not self._oauth2_configured():
            return {}
        token = await self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    async def health_check(self) -> bool:
        try:
            headers = await self._auth_headers()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{settings.kyma_companion_url}/readyz", headers=headers)
                response.raise_for_status()
                data = response.json()
                is_healthy = data.get("status") == "healthy"
                logger.info(f"RAG API health check: {'healthy' if is_healthy else 'unhealthy'}")
                return is_healthy
        except Exception as e:
            logger.error(f"RAG API health check failed: {e}")
            return False

    async def search_documents(self, query: str, top_k: int = 5) -> SearchResponse:
        logger.info(f"Searching documents: query='{query}', top_k={top_k}")

        try:
            headers = await self._auth_headers()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    json={"query": query, "top_k": top_k},
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                search_response = SearchResponse.from_api_response(query, data)
                logger.info(f"Found {search_response.count} documents")
                return search_response

        except httpx.HTTPError as e:
            logger.error(f"RAG search failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during RAG search: {e}")
            raise
