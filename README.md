# Kyma Knowledge MCP Server

An MCP server that gives AI agents semantic search access to Kyma documentation - no credentials or backend service required. The index is auto-downloaded on first run and cached locally; subsequent queries run fully offline.

---

## Quick start

> **Tip:** The fastest way to install is via [Plugin Marketplace](#plugin-marketplace-recommended) below. For Cline or Claude Desktop, see the sections below.

### Plugin Marketplace (recommended)

**Terminal**:

```bash
claude plugin marketplace add danjiawork/kyma-knowledge-mcp
claude plugin install kyma-knowledge-mcp@kyma-plugins
```

The MCP server is registered immediately at user scope. A skill `/install-kyma-knowledge-mcp` is bundled with the plugin - run it to verify the connection, change scope, or see example queries.

To confirm the server is connected, run `/mcp` inside Claude Code or `claude mcp list` in your terminal.

### Claude Code

**Project-level** (this workspace only):

```bash
claude mcp add kyma-knowledge-mcp \
  -- uvx --from git+https://github.com/danjiawork/kyma-knowledge-mcp kyma-knowledge-mcp
```

**Global** (all Claude Code sessions):

```bash
claude mcp add kyma-knowledge-mcp --scope user \
  -- uvx --from git+https://github.com/danjiawork/kyma-knowledge-mcp kyma-knowledge-mcp
```

After running, verify the server is registered and connected in one of two ways:

```bash
claude mcp list          # run from the same project folder for project-level installs
```

Or inside a Claude Code session, run `/mcp` to view and manage all active MCP servers.

> **Project-level install:** `claude mcp list` and `/mcp` only show the server when you are inside the project folder where you ran `claude mcp add`. If you don't see it, check that your terminal / Claude Code session is opened from that directory.

You should see `kyma-knowledge-mcp` with status **connected**. If it shows as disconnected, start a new Claude Code session, the server connects automatically on the next startup.

> **First query:** On first run the server downloads the Kyma docs index (~60 MB) to `~/.kyma-knowledge-mcp/` and loads the embedding model. This takes **1–3 minutes** and happens once. Subsequent queries in this and all future sessions are fast. Wait for the first response before assuming something is wrong.

### Cline (VS Code)

Add to `cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "kyma-knowledge-mcp": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/danjiawork/kyma-knowledge-mcp",
        "kyma-knowledge-mcp"
      ]
    }
  }
}
```

---

## Available tools

Once registered, describe what you need in natural language — the agent picks the right tool automatically:

| What you say | Tool invoked |
| --- | --- |
| _"How do I configure APIRule with OAuth2?"_ | `search_kyma_docs` |
| _"Show me the eventing-manager documentation"_ | `search_kyma_docs` |
| _"What are Kyma modules?"_ | `search_kyma_docs` |
| _"api-gateway keeps crashing, help me debug"_ | `search_kyma_docs` |
| _"How do I contribute to telemetry-manager?"_ | `search_kyma_contributor_docs` |
| _"What is the testing strategy for api-gateway?"_ | `search_kyma_contributor_docs` |

`search_kyma_docs` searches **user-facing documentation** (how to deploy, configure, and operate Kyma). `search_kyma_contributor_docs` searches **contributor documentation** (architecture decisions, development setup, testing guides, contribution workflows).

---

## Configuration reference

Set these as environment variables or in a `.env` file at the project root. See [.env.example](.env.example) for a template.

| Variable | Default | Description |
| --- | --- | --- |
| `LOCAL_INDEX_PATH` | _(empty)_ | Path to index directory or `.tar.gz` archive; auto-downloads if empty |
| `LOCAL_EMBED_MODEL_OVERRIDE` | _(empty)_ | Override the embedding model (read from `meta.json` by default) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG` for verbose output) |
| `DEFAULT_TOP_K` | `10` | Default number of results for user-facing search tools |
| `RERANKER_MODEL` | `ms-marco-TinyBERT-L-2-v2` | Cross-encoder reranker model. Set to empty string to disable. See [Query Pipeline](#query-pipeline) below. |
| `RERANKER_FETCH_MULTIPLIER` | `3` | Candidates fetched per final result (`fetch_n = top_k × multiplier`). Only used when `RERANKER_MODEL` is set. |

---

## Query Pipeline

By default the server uses a **two-stage pipeline**:

1. **Retrieve** — bi-encoder vector search (fastembed + ChromaDB) fetches `top_k × RERANKER_FETCH_MULTIPLIER` candidates.
2. **Rerank** — a [flashrank](https://github.com/PrithivirajDamodaran/FlashRank) cross-encoder (`ms-marco-TinyBERT-L-2-v2`) re-scores every candidate against the full query and returns the top `top_k` results.

Cross-encoders compare query and document jointly, catching relevance signals that pure vector similarity misses. The overhead is ~100–200 ms per query on CPU, negligible for an MCP server used by AI agents. The reranker model (~30 MB, Apache 2.0) is downloaded once on first startup and cached in `~/.kyma-knowledge-mcp/reranker/`.

To disable reranking (pure vector search, faster):

```bash
RERANKER_MODEL=
```

**Higher-quality model** (slower ~4–5×, ~130 MB, Apache 2.0): `ms-marco-MiniLM-L-12-v2`

---

## Building the index locally

### Usage

```bash
uv sync

# Fetch docs, build index, and package into a distributable archive
uv run kyma-knowledge-mcp-build-index \
  --sources kyma_knowledge_mcp/indexing/docs_sources.json \
  --data-dir /tmp/kmc-data \
  --tmp-dir /tmp/kmc-tmp \
  --output-dir /tmp/kmc-index \
  --package kyma-docs-index.tar.gz

# Re-index without re-fetching (docs already downloaded)
uv run kyma-knowledge-mcp-build-index \
  --skip-fetch \
  --data-dir /tmp/kmc-data \
  --output-dir /tmp/kmc-index
```

See [docs_sources.json](kyma_knowledge_mcp/indexing/docs_sources.json) for the full sources list, or [e2e_docs_sources.json](kyma_knowledge_mcp/indexing/e2e_docs_sources.json) for a minimal example.

### All options

| Option | Default | Description |
| --- | --- | --- |
| `--sources` | `kyma_knowledge_mcp/indexing/docs_sources.json` | Path to the sources JSON file |
| `--data-dir` | `./data/user` | Directory to store fetched user-doc markdown files |
| `--contributor-data-dir` | `./data/contributor` | Directory to store fetched contributor markdown files |
| `--tmp-dir` | `./tmp` | Temporary directory for git clones |
| `--output-dir` | `~/.kyma-knowledge-mcp/index` | ChromaDB output directory (both collections written here) |
| `--embed-model` | `BAAI/bge-small-en-v1.5` | fastembed model name |
| `--package` | _(empty)_ | If set, create a `.tar.gz` archive at this path |
| `--skip-fetch` | `false` | Skip fetch and reuse existing `--data-dir` |
| `--log-level` | `INFO` | Logging level |

### Using a local index

After building, point the server at the index by setting `LOCAL_INDEX_PATH` in your `.env`:

```bash
LOCAL_INDEX_PATH=/tmp/kmc-index         # directory produced by --output-dir
# or
LOCAL_INDEX_PATH=/tmp/kyma-docs-index.tar.gz  # archive produced by --package
```

To go back to the auto-downloaded index, remove the line.

---

## Development

```bash
git clone https://github.com/danjiawork/kyma-knowledge-mcp
cd kyma-knowledge-mcp
uv sync
uv run pytest  # runs all unit and integration tests
```
