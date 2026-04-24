# Kyma Knowledge MCP Server

An MCP server that gives AI agents semantic search access to Kyma documentation - entirely offline, no credentials required.

---

## Quick start

> **Tip:** Use the `/install-kyma-knowledge-mcp` skill in Claude Code for a guided setup across different clients (Claude Code, Cline, etc.).

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

On first run the server auto-downloads the pre-built index (~50 MB) and caches it in `~/.kyma-knowledge-mcp/`.

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
| _"Show me the eventing-manager documentation"_ | `get_component_docs` |
| _"What are Kyma modules?"_ | `explain_kyma_concept` |
| _"api-gateway keeps crashing, help me debug"_ | `get_troubleshooting_guide` |

---

## Configuration reference

Set these as environment variables or in a `.env` file at the project root. See [.env.example](.env.example) for a template.

| Variable | Default | Description |
| --- | --- | --- |
| `LOCAL_INDEX_PATH` | _(empty)_ | Path to index directory or `.tar.gz` archive; auto-downloads if empty |
| `LOCAL_EMBED_MODEL_OVERRIDE` | _(empty)_ | Override the embedding model (read from `meta.json` by default) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG` for verbose output) |

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
| `--data-dir` | `./data` | Directory to store fetched markdown files |
| `--tmp-dir` | `./tmp` | Temporary directory for git clones |
| `--output-dir` | `~/.kyma-knowledge-mcp/index` | ChromaDB output directory |
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
