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
┌─────────────────────────────────────────────────────────┐
│                  kyma-knowledge-mcp                     │
│                                                         │
│  User tool                   Contributor tool             │
│  ─────────────────           ───────────────────────    │
│  search_kyma_docs      ───►  search_kyma_contributor_   │
│                              docs                       │
│                        │       │                        │
│                      ▼       ▼                          │
│              LocalRAGClient  LocalRAGClient             │
│              (user)          (contributor)              │
│                      │       │                          │
│                      ▼       ▼                          │
│        ChromaDB collection  ChromaDB collection         │
│        "kyma_docs"          "kyma_docs_contributor"     │
│        (user-facing docs)   (contributor docs)          │
│                      └───────┘                          │
│                      same on-disk database              │
│                      fastembed (in-proc)                │
│                      flashrank reranker (in-proc)       │
└─────────────────────────────────────────────────────────┘
         ▲
         │  first run: auto-download index (~50 MB)
         │  cache: ~/.kyma-knowledge-mcp/index/
         │
    GitHub Releases
    (kyma-docs-index.tar.gz)
```

There is no remote RAG backend. All embedding and vector search runs locally inside the server process. The two collections share one ChromaDB database on disk but are queried independently, so user and contributor content never compete for top-k slots.

## Index lifecycle

The ChromaDB index is built separately from the MCP server (typically in CI) and shipped as a `.tar.gz` release artifact on GitHub Releases.

```
GitHub repos                    CI / developer machine
(kyma docs)                     ──────────────────────────────────
     │                          kyma-knowledge-mcp-build-index
     │  git clone --depth=1          │
     ▼                               │  Step 1a: fetch user sources
DocumentsFetcher                     │   (collection: "user" in docs_sources.json)
(fetcher.py)                         │   clone repos → ./data/user/
     │                               │
     │                               │  Step 1b: fetch contributor sources
     │                               │   (collection: "contributor" in docs_sources.json)
     │                               │   clone repos → ./data/contributor/
     │                               │
     ▼                               │  Step 2a: index user docs
LocalFileIndexer                     │   chunk → embed → ChromaDB "kyma_docs"
(indexer.py)                         │
     │                               │  Step 2b: index contributor docs
     │                               │   chunk → embed → ChromaDB "kyma_docs_contributor"
     ▼                               ▼
ChromaDB dir  ──► tar.gz ──► GitHub Release (docs-index-latest)
(both collections in same dir)
```

Sources are tagged with `"collection": "user"` or `"collection": "contributor"` in `docs_sources.json`. Entries without a tag default to `"user"`.

At MCP server startup, `LocalRAGClient` checks `~/.kyma-knowledge-mcp/index/`. If absent or stale (> 8 days), it auto-downloads and extracts the latest release archive. The embedding model name is recorded in `meta.json` inside the archive so that query-time embedding always matches build-time embedding. The contributor `LocalRAGClient` starts gracefully even if the `kyma_docs_contributor` collection is absent (e.g. on older cached indexes), returning an informative message instead of crashing.

## Why two tools instead of one

Both tools call `LocalRAGClient.search_documents()`. The reason to keep them separate is **collection isolation**: user docs and contributor docs are stored in different ChromaDB collections so they never compete for top-k slots in the same query.

**User tool** — queries `kyma_docs` (user-facing documentation):

| Tool                  | Usage                                                    |
|-----------------------|----------------------------------------------------------|
| `search_kyma_docs`    | Any question about using, configuring, or operating Kyma |

**Contributor tool** — queries `kyma_docs_contributor` (contributor documentation):

| Tool                           | Usage                                                                        |
|--------------------------------|------------------------------------------------------------------------------|
| `search_kyma_contributor_docs` | Questions specifically about developing, extending, or contributing to Kyma  |

Two tools with clear descriptions are enough for agents to route correctly. Wrapper tools that pre-format queries (`get_component_docs`, `explain_kyma_concept`, etc.) added decision overhead without improving retrieval quality.

## Module responsibilities

```
kyma_knowledge_mcp/
├── main.py              — entry point, logging setup, asyncio runner
├── server.py            — MCP tool registry, request routing, response formatting
├── local_rag_client.py  — ChromaDB + fastembed + flashrank: index auto-download, cache, two-stage query pipeline
├── config.py            — Pydantic settings (LOCAL_INDEX_PATH, DEFAULT_TOP_K, RERANKER_MODEL, …)
├── build_index.py       — CLI entry point: kyma-knowledge-mcp-build-index
└── indexing/
    ├── fetcher.py       — clone GitHub repos, filter & copy markdown files
    └── indexer.py       — chunk, embed (fastembed), write ChromaDB collection
```

`server.py` is the only file that knows about MCP. `local_rag_client.py` has no MCP dependency and can be tested or reused independently. The `indexing/` package is only used at index-build time, not at query time.

## Request flow

```
call_tool("search_kyma_docs", {query: "api-gateway 503 error", top_k: 10})
    │
    ▼  server.py
handle_search_kyma_docs()
    ▼  local_rag_client.py
LocalRAGClient.search_documents(query=..., top_k=10)
    │  fastembed: query → vector (in-process, no HTTP)
    │  ChromaDB: cosine similarity → fetch top_k × fetch_multiplier candidates
    │  flashrank: cross-encoder re-scores candidates → trim to top_k
    ▼
SearchResponse → formatted markdown → TextContent[]
```
