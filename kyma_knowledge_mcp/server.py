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
rag_client_dev: LocalRAGClient | None = None
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


async def _get_dev_rag() -> LocalRAGClient:
    global rag_client_dev
    if rag_client_dev is not None:
        return rag_client_dev
    async with _init_lock:
        if rag_client_dev is None:
            logger.info("Initializing developer RAG client on first use...")
            rag_client_dev = await asyncio.to_thread(
                LocalRAGClient,
                settings.local_index_path,
                settings.local_embed_model_override,
                settings.local_dev_collection_name,
                settings.reranker_model,
                settings.reranker_fetch_multiplier,
            )
    return rag_client_dev


@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    List all available MCP tools.

    Returns:
        List of Tool definitions
    """
    return [
        Tool(
            name="search_kyma_docs",
            description=(
                "Search Kyma documentation for information about Kyma components, "
                "configuration, tutorials, and best practices. Use this when you need "
                "to find specific information about Kyma features like APIRule, Function, "
                "Eventing, Telemetry, Serverless, BTP integration, etc. "
                "This tool performs semantic search across all indexed Kyma documentation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "The search query. Can be a question or keywords about Kyma. "
                            "Examples: 'How to configure APIRule with OAuth', "
                            "'Kyma Function runtime options', 'Eventing backend setup'"
                        ),
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
            name="get_component_docs",
            description=(
                "Get comprehensive documentation for a specific Kyma component. "
                "Use this when you need detailed information about a particular "
                "Kyma component like api-gateway, serverless, eventing-manager, "
                "telemetry-manager, btp-manager, istio, etc. Returns overview, "
                "configuration options, and usage examples for the specified component."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": (
                            "Name of the Kyma component. Examples: 'api-gateway', "
                            "'serverless', 'eventing-manager', 'telemetry-manager', "
                            "'btp-manager', 'istio', 'nats-manager', 'cloud-manager'"
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of documentation chunks to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["component"],
            },
        ),
        Tool(
            name="explain_kyma_concept",
            description=(
                "Get a detailed explanation of Kyma concepts and terminology. "
                "Use this when you need to understand Kyma-specific terms, "
                "architectures, or design patterns. Examples: 'Kyma modules', "
                "'Eventing architecture', 'Serverless Functions', 'APIRule vs Ingress', "
                "'BTP integration'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "concept": {
                        "type": "string",
                        "description": (
                            "The Kyma concept to explain. Can be a feature name, "
                            "architectural pattern, or terminology. Examples: "
                            "'Kyma modules', 'Function runtime', 'Eventing subscriptions'"
                        ),
                    },
                },
                "required": ["concept"],
            },
        ),
        # Note: list_kyma_components tool removed as it's not essential
        # Users can discover components through search_kyma_docs instead
        Tool(
            name="get_troubleshooting_guide",
            description=(
                "Get troubleshooting guides and common issues for Kyma components. "
                "Use this when you need to debug problems or understand common "
                "error scenarios. Searches for troubleshooting documentation, "
                "error messages, and resolution steps."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": (
                            "The Kyma component to get troubleshooting info for. "
                            "Examples: 'api-gateway', 'serverless', 'eventing'"
                        ),
                    },
                    "issue": {
                        "type": "string",
                        "description": ("Optional: Specific issue or error message to search for"),
                    },
                },
                "required": ["component"],
            },
        ),
        Tool(
            name="search_kyma_contributor_docs",
            description=(
                "Search Kyma contributor documentation for information about how to "
                "develop, contribute to, or extend Kyma components. Use this when you "
                "need information about development setup, architecture decisions, "
                "contribution guidelines, or internal component design. "
                "This tool searches the developer-facing documentation collection."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "The search query. Examples: 'how to run api-gateway tests', "
                            "'eventing-manager architecture', 'contributing to serverless'"
                        ),
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
            name="get_contribution_guide",
            description=(
                "Get the contribution guide for a specific Kyma component. "
                "Use this when you need to understand how to contribute to a "
                "Kyma module — development environment setup, testing approach, "
                "PR process, or coding conventions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": (
                            "Name of the Kyma component. Examples: 'api-gateway', "
                            "'serverless', 'eventing-manager', 'telemetry-manager'"
                        ),
                    },
                },
                "required": ["component"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """
    Handle tool calls from MCP clients.

    Args:
        name: Name of the tool to call
        arguments: Tool arguments as dictionary

    Returns:
        List of TextContent responses
    """
    try:
        if name == "search_kyma_docs":
            return await handle_search_kyma_docs(arguments)
        elif name == "get_component_docs":
            return await handle_get_component_docs(arguments)
        elif name == "explain_kyma_concept":
            return await handle_explain_kyma_concept(arguments)
        elif name == "get_troubleshooting_guide":
            return await handle_get_troubleshooting_guide(arguments)
        elif name == "search_kyma_contributor_docs":
            return await handle_search_kyma_contributor_docs(arguments)
        elif name == "get_contribution_guide":
            return await handle_get_contribution_guide(arguments)
        else:
            return [
                TextContent(
                    type="text",
                    text=f"Unknown tool: {name}",
                )
            ]
    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}", exc_info=True)
        return [
            TextContent(
                type="text",
                text=f"Error executing tool {name}: {str(e)}",
            )
        ]


async def handle_search_kyma_docs(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle search_kyma_docs tool call."""
    query = arguments.get("query", "")
    top_k = arguments.get("top_k", _DEFAULT_TOP_K)

    logger.info(f"Searching Kyma docs: query='{query}', top_k={top_k}")

    response = await (await _get_rag()).search_documents(query=query, top_k=top_k)

    # Format the response
    result_text = f"# Search Results for: {query}\n\n"
    result_text += f"Found {response.count} relevant documents:\n\n"

    for i, doc in enumerate(response.documents, 1):
        result_text += f"## Document {i}\n\n"
        result_text += f"{doc.content}\n\n"
        if doc.metadata:
            result_text += f"**Source:** {doc.metadata.get('source', 'Unknown')}\n\n"
        result_text += "---\n\n"

    return [TextContent(type="text", text=result_text)]


async def handle_get_component_docs(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle get_component_docs tool call."""
    component = arguments.get("component", "")
    top_k = arguments.get("top_k", _DEFAULT_TOP_K)

    logger.info(f"Getting component docs: component='{component}', top_k={top_k}")

    # Create a targeted query for the component
    query = f"{component} component documentation overview configuration"
    response = await (await _get_rag()).search_documents(query=query, top_k=top_k)

    # Format the response
    result_text = f"# {component.title()} Component Documentation\n\n"
    result_text += f"Found {response.count} relevant documentation sections:\n\n"

    for i, doc in enumerate(response.documents, 1):
        result_text += f"## Section {i}\n\n"
        result_text += f"{doc.content}\n\n"
        result_text += "---\n\n"

    return [TextContent(type="text", text=result_text)]


async def handle_explain_kyma_concept(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle explain_kyma_concept tool call."""
    concept = arguments.get("concept", "")

    logger.info(f"Explaining Kyma concept: concept='{concept}'")

    # Create a query focused on explanation
    query = f"What is {concept} in Kyma? Explain {concept}"
    response = await (await _get_rag()).search_documents(query=query, top_k=5)

    # Format the response
    result_text = f"# Explanation: {concept}\n\n"

    if response.count > 0:
        # Combine the top results for a comprehensive explanation
        for doc in response.documents:
            result_text += f"{doc.content}\n\n"
    else:
        result_text += f"No documentation found for concept: {concept}\n"

    return [TextContent(type="text", text=result_text)]


# Note: handle_list_kyma_components removed as list_topics endpoint is not available


async def handle_get_troubleshooting_guide(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle get_troubleshooting_guide tool call."""
    component = arguments.get("component", "")
    issue = arguments.get("issue", "")

    logger.info(f"Getting troubleshooting guide: component='{component}', issue='{issue}'")

    # Create a troubleshooting-focused query
    if issue:
        query = f"{component} troubleshooting {issue} error common issues"
    else:
        query = f"{component} troubleshooting common issues errors problems"

    response = await (await _get_rag()).search_documents(query=query, top_k=8)

    # Format the response
    result_text = f"# Troubleshooting Guide: {component}\n\n"
    if issue:
        result_text += f"**Issue:** {issue}\n\n"

    if response.count > 0:
        result_text += f"Found {response.count} troubleshooting guides:\n\n"
        for i, doc in enumerate(response.documents, 1):
            result_text += f"## Guide {i}\n\n"
            result_text += f"{doc.content}\n\n"
            result_text += "---\n\n"
    else:
        result_text += f"No troubleshooting guides found for {component}\n"

    return [TextContent(type="text", text=result_text)]


_DEV_NOT_INDEXED = (
    "Developer documentation not yet indexed. "
    "Rebuild the index after adding developer sources to docs_sources.json."
)


async def handle_search_kyma_contributor_docs(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle search_kyma_contributor_docs tool call."""
    query = arguments.get("query", "")
    top_k = arguments.get("top_k", _DEFAULT_TOP_K)

    logger.info(f"Searching contributor docs: query='{query}', top_k={top_k}")

    dev_rag = await _get_dev_rag()
    if not dev_rag._available:
        return [TextContent(type="text", text=_DEV_NOT_INDEXED)]

    response = await dev_rag.search_documents(query=query, top_k=top_k)

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


async def handle_get_contribution_guide(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle get_contribution_guide tool call."""
    component = arguments.get("component", "")

    logger.info(f"Getting contribution guide: component='{component}'")

    dev_rag = await _get_dev_rag()
    if not dev_rag._available:
        return [TextContent(type="text", text=_DEV_NOT_INDEXED)]

    query = f"{component} contribution guide development setup architecture testing"
    response = await dev_rag.search_documents(query=query, top_k=5)

    result_text = f"# Contribution Guide: {component}\n\n"
    if response.count == 0:
        result_text += f"No contribution guide found for {component}.\n"
    else:
        for doc in response.documents:
            result_text += f"{doc.content}\n\n"

    return [TextContent(type="text", text=result_text)]


async def run_server() -> None:
    """Run the MCP server with stdio transport."""
    logger.info(f"Starting {settings.server_name} v{settings.server_version}")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
