# Architecture

## Purpose

Kyma Knowledge MCP Server bridges AI agents and Kyma documentation. It implements the [Model Context Protocol](https://modelcontextprotocol.io) over stdio, so any MCP-compatible agent can query Kyma knowledge without cloud credentials or a running backend service.

The server is intentionally narrow in scope: **Kyma knowledge only**. Kubernetes operations belong in a separate MCP server registered alongside this one.

## System Architecture

```
AI Agent (Claude Code, Cline, Claude Desktop, ...)
    │
    │  MCP Protocol (stdio)
    ▼
┌─────────────────────────────────────────────────┐
│            kyma-knowledge-mcp                   │
│                                                 │
│  search_kyma_docs                               │
│  get_component_docs          ───► LocalRAGClient│
│  explain_kyma_concept                │          │
│  get_troubleshooting_guide           │          │
│                                      ▼          │
│                             ChromaDB (on disk)  │
│                             fastembed (in-proc) │
└─────────────────────────────────────────────────┘
         ▲
         │  first run: auto-download index (~50 MB)
         │  cache: ~/.kyma-knowledge-mcp/index/
         │
    GitHub Releases
    (kyma-docs-index.tar.gz)
```

There is no remote RAG backend. All embedding and vector search runs locally inside the server process.

## Index lifecycle

The ChromaDB index is built separately from the MCP server (typically in CI) and shipped as a `.tar.gz` release artifact on GitHub Releases.

```
GitHub repos                    CI / developer machine
(kyma docs)                     ──────────────────────────────
     │                          kyma-knowledge-mcp-build-index
     │  git clone --depth=1          │
     ▼                               │  Step 1: fetch
DocumentsFetcher                     │   clone repos → ./data/
(fetcher.py)                         │
     │                               │  Step 2: index
     ▼                               │   chunk markdown (MarkdownHeaderTextSplitter)
LocalFileIndexer                     │   embed with fastembed (BAAI/bge-small-en-v1.5)
(indexer.py)                         │   store in ChromaDB PersistentClient
     │                               │
     ▼                               ▼
ChromaDB dir  ──► tar.gz ──► GitHub Release (docs-index-latest)
```

At MCP server startup, `LocalRAGClient` checks `~/.kyma-knowledge-mcp/index/`. If absent or stale (> 8 days), it auto-downloads and extracts the latest release archive. The embedding model name is recorded in `meta.json` inside the archive so that query-time embedding always matches build-time embedding.

## Why four tools instead of one

All four tools call the same `LocalRAGClient.search_documents()`. The reason to keep them separate is **agent ergonomics**: descriptive tool names and targeted descriptions help the agent choose the right tool without needing explicit instruction. Each tool constructs a different query string to steer the vector search:

| Tool | Query pattern |
|---|---|
| `search_kyma_docs` | raw user query |
| `get_component_docs` | `{component} component documentation overview configuration` |
| `explain_kyma_concept` | `What is {concept} in Kyma? Explain {concept}` |
| `get_troubleshooting_guide` | `{component} troubleshooting {issue} error common issues` |

## Module responsibilities

```
kyma_knowledge_mcp/
├── main.py              — entry point, logging setup, asyncio runner
├── server.py            — MCP tool registry, request routing, response formatting
├── local_rag_client.py  — ChromaDB + fastembed: index auto-download, cache, vector search
├── config.py            — Pydantic settings (LOCAL_INDEX_PATH, log level, …)
├── build_index.py       — CLI entry point: kyma-knowledge-mcp-build-index
└── indexing/
    ├── fetcher.py       — clone GitHub repos, filter & copy markdown files
    └── indexer.py       — chunk, embed (fastembed), write ChromaDB collection
```

`server.py` is the only file that knows about MCP. `local_rag_client.py` has no MCP dependency and can be tested or reused independently. The `indexing/` package is only used at index-build time, not at query time.

## Request flow

```
call_tool("get_troubleshooting_guide", {component: "api-gateway", issue: "503"})
    │
    ▼  server.py
handle_get_troubleshooting_guide()
    │  builds query: "api-gateway troubleshooting 503 error common issues"
    ▼  local_rag_client.py
LocalRAGClient.search_documents(query=..., top_k=5)
    │  fastembed: query → vector (in-process, no HTTP)
    │  ChromaDB: cosine similarity search
    ▼
SearchResponse → formatted markdown → TextContent[]
```
