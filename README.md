# Kyma Companion MCP Server

An MCP server that gives AI agents (Claude Code, Cline, Github Copilot, etc.) semantic search access to Kyma documentation.

Two modes — pick the one that fits you:

| Mode | Who it's for | Credentials needed |
| --- | --- | --- |
| **Local** (default) | Any Kyma user | None |
| **Remote** | Kyma Companion developers | KC backend URL + optional OAuth2 |

---

## Local mode (default — no credentials required)

Point the server at a pre-built Kyma docs index on your machine. All searches run entirely offline — no API keys, no network calls.

> **Note:** Automatic index download is not yet available. Download the index archive from the [Releases page](https://github.com/kyma-project/kyma-companion-mcp/releases) and set `LOCAL_INDEX_PATH` as shown below.

### Prerequisites

- [uv](https://docs.astral.sh/uv/):
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Claude Code

```bash
claude mcp add kyma -e LOCAL_INDEX_PATH=/path/to/kyma-docs-index.tar.gz \
  -- uvx --from git+https://github.com/kyma-project/kyma-companion-mcp kyma-companion-mcp
```

### Cline (VS Code)

```json
{
  "mcpServers": {
    "kyma": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/kyma-project/kyma-companion-mcp",
        "kyma-companion-mcp"
      ],
      "env": {
        "LOCAL_INDEX_PATH": "/path/to/kyma-docs-index.tar.gz"
      }
    }
  }
}
```

### Claude Desktop

```json
{
  "mcpServers": {
    "kyma": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/kyma-project/kyma-companion-mcp",
        "kyma-companion-mcp"
      ],
      "env": {
        "LOCAL_INDEX_PATH": "/path/to/kyma-docs-index.tar.gz"
      }
    }
  }
}
```

Replace `/path/to/kyma-docs-index.tar.gz` with the path where you saved the downloaded archive.

### Using an already-extracted index directory

If you have already extracted the archive, you can point directly to the directory:

```json
"env": {
  "LOCAL_INDEX_PATH": "/path/to/kyma_chroma_dir"
}
```

---

## Remote mode (Kyma Companion developers only)

Connect the MCP server to a running Kyma Companion backend instead of the local index.

Set `USE_REMOTE_MODE=true` and provide the backend URL:

```json
"env": {
  "USE_REMOTE_MODE": "true",
  "KYMA_COMPANION_URL": "http://localhost:8000"
}
```

Add OAuth2 credentials if your KC instance requires authentication:

```json
"env": {
  "USE_REMOTE_MODE": "true",
  "KYMA_COMPANION_URL": "https://companion.cp.dev.kyma.cloud.sap",
  "OAUTH2_TOKEN_URL": "https://<your-idp>/oauth2/token",
  "OAUTH2_CLIENT_ID": "<client-id>",
  "OAUTH2_CLIENT_SECRET": "<client-secret>"
}
```

---

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `USE_REMOTE_MODE` | `false` | Set to `true` to use KC backend instead of local index |
| `LOCAL_INDEX_PATH` | _(empty)_ | Path to index archive or directory; auto-downloads if empty |
| `LOCAL_EMBED_MODEL_OVERRIDE` | _(empty)_ | Override the embedding model (read from `meta.json` by default) |
| `LOCAL_COLLECTION_NAME` | `kyma_docs` | ChromaDB collection name |
| `KYMA_COMPANION_URL` | `http://localhost:8000` | KC backend URL (remote mode only) |
| `OAUTH2_TOKEN_URL` | _(empty)_ | OAuth2 token endpoint (remote mode only) |
| `OAUTH2_CLIENT_ID` | _(empty)_ | OAuth2 client ID (remote mode only) |
| `OAUTH2_CLIENT_SECRET` | _(empty)_ | OAuth2 client secret (remote mode only) |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout in seconds (remote mode only) |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Available tools

Once registered, describe what you need in natural language — the agent picks the right tool automatically:

| What you say | Tool invoked |
|---|---|
| _"How do I configure APIRule with OAuth2?"_ | `search_kyma_docs` |
| _"Show me the eventing-manager documentation"_ | `get_component_docs` |
| _"What are Kyma modules?"_ | `explain_kyma_concept` |
| _"api-gateway keeps crashing, help me debug"_ | `get_troubleshooting_guide` |

---

## Development

```bash
git clone https://github.com/kyma-project/kyma-companion-mcp
cd kyma-companion-mcp
uv sync --dev
uv run pytest
```

### Running locally against a local index

Set `LOCAL_INDEX_PATH` in the `.env` file at the project root:

```bash
LOCAL_INDEX_PATH=/path/to/kyma-docs-index.tar.gz
```

Then run:

```bash
uv run kyma-companion-mcp
```

Startup logs confirm which mode is active:

```text
INFO: Mode: LOCAL (ChromaDB, no credentials required)
# or
INFO: Mode: REMOTE (Kyma Companion backend)
```

### Running against a local KC backend

```bash
USE_REMOTE_MODE=true
KYMA_COMPANION_URL=http://localhost:8000
```

Start KC as usual (`poetry run fastapi dev src/main.py`), then start this server.
