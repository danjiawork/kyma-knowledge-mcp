# Architecture

## Purpose

Kyma Companion MCP Server bridges AI agents and Kyma documentation. It implements the [Model Context Protocol](https://modelcontextprotocol.io) over stdio, so any MCP-compatible agent can query Kyma knowledge without being aware of the underlying RAG infrastructure.

The server is intentionally narrow in scope: **Kyma knowledge only**. Kubernetes operations belong in a separate MCP server registered alongside this one.

## System Architecture

```
AI Agent (Claude Code, Cline, Claude Desktop, ...)
    │
    │  MCP Protocol (stdio)
    ▼
┌──────────────────────────────────────┐
│       kyma-companion-mcp             │
│                                      │
│  search_kyma_docs                    │
│  get_component_docs          ────────┼──► POST /api/tools/kyma/search
│  explain_kyma_concept                │
│  get_troubleshooting_guide           │
└──────────────────────────────────────┘
                                           │
                                           ▼
                              ┌────────────────────────┐
                              │   Kyma Companion       │
                              │                        │
                              │   RAG Pipeline         │
                              │   ├─ Vector search     │
                              │   └─ Reranking         │
                              │                        │
                              │   HanaDB Vector Store  │
                              │   (13+ components)     │
                              └────────────────────────┘
```

## Why four tools instead of one

All four tools call the same `POST /search` endpoint. The reason to keep them separate is **agent ergonomics**: descriptive tool names and targeted descriptions help the agent choose the right tool without needing explicit instruction. Each tool also constructs a different query string to steer the RAG search:

| Tool | Query pattern |
|---|---|
| `search_kyma_docs` | raw user query |
| `get_component_docs` | `{component} component documentation overview configuration` |
| `explain_kyma_concept` | `What is {concept} in Kyma? Explain {concept}` |
| `get_troubleshooting_guide` | `{component} troubleshooting {issue} error common issues` |

If the agent calling this server is well-instructed and constructs queries itself, a single `search_kyma_docs` tool is sufficient.

## Module responsibilities

```
kyma_companion_mcp/
├── main.py        — entry point, logging setup, asyncio runner
├── server.py      — MCP tool registry, request routing, response formatting
├── rag_client.py  — async HTTP client for the Kyma Companion RAG API
└── config.py      — Pydantic settings, reads from env / .env file
```

`server.py` is the only file that knows about MCP. `rag_client.py` is pure HTTP — it has no MCP dependency and can be tested or reused independently.

## Request flow

```
call_tool("get_troubleshooting_guide", {component: "api-gateway", issue: "503"})
    │
    ▼  server.py
handle_get_troubleshooting_guide()
    │  builds query: "api-gateway troubleshooting 503 error common issues"
    ▼  rag_client.py
search_documents(query=..., top_k=5)
    │  POST {KYMA_COMPANION_URL}/api/tools/kyma/search
    ▼
SearchResponse → formatted markdown → TextContent[]
```
