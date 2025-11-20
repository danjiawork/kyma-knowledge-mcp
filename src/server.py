"""MCP Server implementation for Kyma Companion."""

import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .config import settings
from .rag_client import RAGClient

logger = logging.getLogger(__name__)

# Initialize RAG client
rag_client = RAGClient()

# Create MCP server instance
app = Server(settings.server_name)


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
                        "default": 5,
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
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10,
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
        Tool(
            name="list_kyma_components",
            description=(
                "List all available Kyma components that have documentation indexed "
                "in the system. Use this to discover what Kyma components are available "
                "and can be queried for more information."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
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
                            "The Kyma component to get troubleshooting info for. " "Examples: 'api-gateway', 'serverless', 'eventing'"
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
        elif name == "list_kyma_components":
            return await handle_list_kyma_components(arguments)
        elif name == "get_troubleshooting_guide":
            return await handle_get_troubleshooting_guide(arguments)
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
    top_k = arguments.get("top_k", 5)

    logger.info(f"Searching Kyma docs: query='{query}', top_k={top_k}")

    response = await rag_client.search_documents(query=query, top_k=top_k)

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
    top_k = arguments.get("top_k", 5)

    logger.info(f"Getting component docs: component='{component}', top_k={top_k}")

    # Create a targeted query for the component
    query = f"{component} component documentation overview configuration"
    response = await rag_client.search_documents(query=query, top_k=top_k)

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
    response = await rag_client.search_documents(query=query, top_k=3)

    # Format the response
    result_text = f"# Explanation: {concept}\n\n"

    if response.count > 0:
        # Combine the top results for a comprehensive explanation
        for doc in response.documents:
            result_text += f"{doc.content}\n\n"
    else:
        result_text += f"No documentation found for concept: {concept}\n"

    return [TextContent(type="text", text=result_text)]


async def handle_list_kyma_components(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle list_kyma_components tool call."""
    logger.info("Listing Kyma components")

    topics_data = await rag_client.list_topics()

    result_text = "# Available Kyma Components\n\n"
    result_text += f"Total components: {topics_data.get('count', 0)}\n\n"

    topics = topics_data.get("topics", [])
    for topic in topics:
        result_text += f"- **{topic}**\n"

    result_text += f"\n{topics_data.get('description', '')}\n"

    return [TextContent(type="text", text=result_text)]


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

    response = await rag_client.search_documents(query=query, top_k=5)

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


async def run_server() -> None:
    """Run the MCP server with stdio transport."""
    logger.info(f"Starting {settings.server_name} v{settings.server_version}")

    # Check RAG API health before starting
    is_healthy = await rag_client.health_check()
    if not is_healthy:
        logger.warning("RAG API health check failed, but server will start anyway")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
