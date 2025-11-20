# Architecture Documentation

## System Overview

The Kyma Companion MCP Server is a bridge between AI agents and Kyma documentation, leveraging the Model Context Protocol (MCP) to provide Kyma-specific knowledge through integration with Kyma Companion's RAG pipeline.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Agent Layer                           │
│                    (Cline, Claude Desktop, etc.)                │
└────────────────────┬──────────────────────┬─────────────────────┘
                     │                      │
                     │ MCP Protocol         │ MCP Protocol
                     │ (stdio)              │ (stdio)
                     ▼                      ▼
         ┌────────────────────┐  ┌──────────────────────────┐
         │  Kubernetes MCP    │  │  Kyma Companion MCP      │
         │     Server         │  │      Server              │
         │                    │  │   (This Project)         │
         │  - kubectl ops     │  │  - search_kyma_docs      │
         │  - apply manifests │  │  - get_component_docs    │
         │  - get resources   │  │  - explain_concept       │
         └────────────────────┘  └───────────┬──────────────┘
                                             │
                                             │ HTTP/REST
                                             │ (httpx async)
                                             ▼
                              ┌──────────────────────────────┐
                              │   Kyma Companion Service     │
                              │                              │
                              │  ┌────────────────────────┐  │
                              │  │   RAG API Endpoints    │  │
                              │  │  /api/v1/rag/search    │  │
                              │  │  /api/v1/rag/health    │  │
                              │  │  /api/v1/rag/topics    │  │
                              │  └───────────┬────────────┘  │
                              │              │               │
                              │              ▼               │
                              │  ┌────────────────────────┐  │
                              │  │    RAG Pipeline        │  │
                              │  │  - Query Generation    │  │
                              │  │  - Vector Search       │  │
                              │  │  - Reranking          │  │
                              │  └───────────┬────────────┘  │
                              │              │               │
                              │              ▼               │
                              │  ┌────────────────────────┐  │
                              │  │  HanaDB Vector Store   │  │
                              │  │  - Embedded Docs       │  │
                              │  │  - 13+ Components      │  │
                              │  └────────────────────────┘  │
                              └──────────────────────────────┘
```

## Component Architecture

### 1. MCP Server Core (`src/server.py`)

```python
┌─────────────────────────────────────┐
│         MCP Server (stdio)          │
│                                     │
│  ┌──────────────────────────────┐   │
│  │    Tool Registry             │   │
│  │  - search_kyma_docs          │   │
│  │  - get_component_docs        │   │
│  │  - explain_kyma_concept      │   │
│  │  - list_kyma_components      │   │
│  │  - get_troubleshooting_guide │   │
│  └──────────────────────────────┘   │
│                                     │
│  ┌──────────────────────────────┐   │
│  │    Request Handlers          │   │
│  │  - Parse MCP requests        │   │
│  │  - Route to tool handler     │   │
│  │  - Format responses          │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

**Responsibilities:**
- Implement MCP protocol (list_tools, call_tool)
- Define tool schemas and descriptions
- Handle tool execution and error recovery
- Format responses as structured markdown

### 2. RAG Client (`src/rag_client.py`)

```python
┌─────────────────────────────────────┐
│         RAG Client                  │
│                                     │
│  ┌──────────────────────────────┐   │
│  │    HTTP Client (httpx)       │   │
│  │  - Async request handling    │   │
│  │  - Timeout management        │   │
│  │  - Connection pooling        │   │
│  └──────────────────────────────┘   │
│                                     │
│  ┌──────────────────────────────┐   │
│  │    API Methods               │   │
│  │  - health_check()            │   │
│  │  - search_documents()        │   │
│  │  - list_topics()             │   │
│  └──────────────────────────────┘   │
│                                     │
│  ┌──────────────────────────────┐   │
│  │    Response Models           │   │
│  │  - SearchResponse            │   │
│  │  - DocumentResult            │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

**Responsibilities:**
- Abstract HTTP communication
- Handle request/response serialization
- Manage connection lifecycle
- Provide typed interfaces

### 3. Configuration (`src/config.py`)

```python
┌─────────────────────────────────────┐
│    Configuration Management         │
│                                     │
│  ┌──────────────────────────────┐   │
│  │  Pydantic Settings           │   │
│  │  - kyma_companion_url        │   │
│  │  - request_timeout           │   │
│  │  - log_level                 │   │
│  │  - server metadata           │   │
│  └──────────────────────────────┘   │
│                                     │
└─────────────────────────────────────┘
```

**Responsibilities:**
- Centralized configuration management
- Environment-based configuration
- Type-safe settings access
- Validation and defaults


## Extension Points

### Adding New Tools

1. **Define tool schema** in `list_tools()`:
```python
Tool(
    name="new_tool",
    description="Clear description for AI agents",
    inputSchema={...}
)
```

2. **Implement handler**:
```python
async def handle_new_tool(arguments: dict) -> list[TextContent]:
    # Implementation
    pass
```

3. **Register in router**:
```python
if name == "new_tool":
    return await handle_new_tool(arguments)
```

### Adding New RAG Endpoints

1. Add method in `rag_client.py`
2. Update tool handlers to use new endpoint
3. Consider if new tool is needed
