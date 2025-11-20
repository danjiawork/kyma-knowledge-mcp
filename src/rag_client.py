"""RAG client for communicating with Kyma Companion API."""

import logging
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


class RAGClient:
    """Client for interacting with Kyma Companion RAG API."""

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        """
        Initialize RAG client.

        Args:
            base_url: Base URL for Kyma Companion RAG API. Defaults to settings value.
            timeout: Request timeout in seconds. Defaults to settings value.
        """
        self.base_url = base_url or settings.rag_api_base_url
        self.timeout = timeout or settings.request_timeout
        logger.info(f"Initialized RAG client with base URL: {self.base_url}")

    async def health_check(self) -> bool:
        """
        Check if the RAG API is healthy and operational.

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                data = response.json()
                is_healthy = data.get("status") == "healthy"
                logger.info(f"RAG API health check: {'healthy' if is_healthy else 'unhealthy'}")
                return is_healthy
        except Exception as e:
            logger.error(f"RAG API health check failed: {e}")
            return False

    async def search_documents(self, query: str, top_k: int = 5) -> SearchResponse:
        """
        Search Kyma documentation using RAG.

        Args:
            query: The search query text
            top_k: Number of results to return (1-20)

        Returns:
            SearchResponse containing relevant documents

        Raises:
            httpx.HTTPError: If the API request fails
        """
        logger.info(f"Searching documents: query='{query}', top_k={top_k}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    json={"query": query, "top_k": top_k},
                )
                response.raise_for_status()
                data = response.json()

                search_response = SearchResponse(**data)
                logger.info(f"Found {search_response.count} documents")
                return search_response

        except httpx.HTTPError as e:
            logger.error(f"RAG search failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during RAG search: {e}")
            raise

    async def list_topics(self) -> dict[str, Any]:
        """
        List available Kyma documentation topics.

        Returns:
            Dictionary containing available topics and their count

        Raises:
            httpx.HTTPError: If the API request fails
        """
        logger.info("Listing available topics")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/topics")
                response.raise_for_status()
                data = response.json()
                logger.info(f"Retrieved {data.get('count', 0)} topics")
                return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to list topics: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while listing topics: {e}")
            raise
