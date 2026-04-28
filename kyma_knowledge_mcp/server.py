"""MCP Server implementation for Kyma Context."""

import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import settings
from .local_rag_client import LocalRAGClient

logger = logging.getLogger(__name__)

_DEFAULT_TOP_K = settings.default_top_k

rag_client: LocalRAGClient | None = None
rag_client_contributor: LocalRAGClient | None = None
_init_lock = asyncio.Lock()

# Create MCP server instance
app = Server(settings.server_name)


async def _get_rag() -> LocalRAGClient:
    global rag_client
    if rag_client is not None:
        return rag_client
    async with _init_lock:
        if rag_client is None:
            logger.info("Initializing RAG client on first use (may take a moment)...")
            rag_client = await asyncio.to_thread(
                LocalRAGClient,
                settings.local_index_path,
                settings.local_embed_model_override,
                settings.local_collection_name,
                settings.reranker_model,
                settings.reranker_fetch_multiplier,
            )
    return rag_client


async def _get_contributor_rag() -> LocalRAGClient:
    global rag_client_contributor
    if rag_client_contributor is not None:
        return rag_client_contributor
    async with _init_lock:
        if rag_client_contributor is None:
            logger.info("Initializing contributor RAG client on first use...")
            rag_client_contributor = await asyncio.to_thread(
                LocalRAGClient,
                settings.local_index_path,
                settings.local_embed_model_override,
                settings.local_contributor_collection_name,
                settings.reranker_model,
                settings.reranker_fetch_multiplier,
            )
    return rag_client_contributor


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available MCP tools."""
    return [
        Tool(
            name="search_kyma_docs",
            description=(
                "Search Kyma user documentation. Use for any question about using, "
                "configuring, or operating Kyma — including component docs (APIRule, "
                "Serverless, Eventing, Telemetry, Istio, BTP integration), "
                "troubleshooting errors, tutorials, and general Kyma concepts. "
                "Examples: 'How to configure APIRule with OAuth', "
                "'Kyma Function runtime options', 'eventing subscription not triggering', "
                "'what regions does Kyma support', 'how to enable a Kyma module'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query — a question or keywords about Kyma.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (1-20)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="search_kyma_contributor_docs",
            description=(
                "Search Kyma contributor documentation. Use only when the "
                "question is specifically about developing, extending, or contributing to "
                "Kyma itself — such as development environment setup, running tests, "
                "architecture decisions (ADRs), PR process, or coding conventions for a "
                "specific Kyma component. "
                "Examples: 'how to run api-gateway integration tests', "
                "'eventing-manager architecture decisions', 'contributing to serverless module'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query about contributing to or developing Kyma.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (1-20)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls from MCP clients."""
    try:
        if name == "search_kyma_docs":
            return await handle_search_kyma_docs(arguments)
        elif name == "search_kyma_contributor_docs":
            return await handle_search_kyma_contributor_docs(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error executing tool {name}: {str(e)}")]


async def handle_search_kyma_docs(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle search_kyma_docs tool call."""
    query = arguments.get("query", "")
    top_k = arguments.get("top_k", _DEFAULT_TOP_K)

    logger.info(f"Searching Kyma docs: query='{query}', top_k={top_k}")

    response = await (await _get_rag()).search_documents(query=query, top_k=top_k)

    result_text = f"# Search Results for: {query}\n\n"
    result_text += f"Found {response.count} relevant documents:\n\n"

    for i, doc in enumerate(response.documents, 1):
        result_text += f"## Document {i}\n\n"
        result_text += f"{doc.content}\n\n"
        if doc.metadata:
            result_text += f"**Source:** {doc.metadata.get('source', 'Unknown')}\n\n"
        result_text += "---\n\n"

    return [TextContent(type="text", text=result_text)]


_CONTRIBUTOR_NOT_INDEXED = (
    "Contributor documentation not yet indexed. "
    "Rebuild the index after adding contributor sources to docs_sources.json."
)


async def handle_search_kyma_contributor_docs(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle search_kyma_contributor_docs tool call."""
    query = arguments.get("query", "")
    top_k = arguments.get("top_k", _DEFAULT_TOP_K)

    logger.info(f"Searching contributor docs: query='{query}', top_k={top_k}")

    contributor_rag = await _get_contributor_rag()
    if not contributor_rag._available:
        return [TextContent(type="text", text=_CONTRIBUTOR_NOT_INDEXED)]

    response = await contributor_rag.search_documents(query=query, top_k=top_k)

    result_text = f"# Contributor Docs Search: {query}\n\n"
    if response.count == 0:
        result_text += "No contributor documentation found for this query.\n"
    else:
        result_text += f"Found {response.count} relevant sections:\n\n"
        for i, doc in enumerate(response.documents, 1):
            result_text += f"## Result {i}\n\n"
            result_text += f"{doc.content}\n\n"
            if doc.metadata:
                result_text += f"**Source:** {doc.metadata.get('source', 'Unknown')}\n\n"
            result_text += "---\n\n"

    return [TextContent(type="text", text=result_text)]


async def run_server() -> None:
    """Run the MCP server with stdio transport."""
    logger.info(f"Starting {settings.server_name} v{settings.server_version}")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
