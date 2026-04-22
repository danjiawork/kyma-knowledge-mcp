# Kyma Companion MCP Server

An MCP server that gives AI agents semantic search access to Kyma documentation, backed by the [Kyma Companion](https://github.com/kyma-project/kyma-companion) RAG pipeline.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — install with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- A running Kyma Companion instance with the RAG API enabled

## Installation

### Claude Code

```bash
claude mcp add kyma-companion-mcp -s user \
  -e KYMA_COMPANION_URL=https://<your-kyma-companion-host> \
  -e OAUTH2_TOKEN_URL=https://<your-idp>/oauth2/token \
  -e OAUTH2_CLIENT_ID=<client-id> \
  -e OAUTH2_CLIENT_SECRET=<client-secret> \
  -- uvx --from git+https://github.com/<your-org>/kyma-companion-mcp kyma-companion-mcp
```

Omit the `OAUTH2_*` variables if your Kyma Companion instance does not require authentication.

To change the URL later without re-running the command, edit `~/.claude.json` directly and restart the MCP server.

Verify the server is connected:

```bash
claude mcp list
```

### Cline (VS Code)

Add to Cline's MCP settings (`cline_mcp_settings.json`):

```json
{
  "mcpServers": {
    "kyma-companion-mcp": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/<your-org>/kyma-companion-mcp",
        "kyma-companion-mcp"
      ],
      "env": {
        "KYMA_COMPANION_URL": "https://<your-kyma-companion-host>",
        "OAUTH2_TOKEN_URL": "https://<your-idp>/oauth2/token",
        "OAUTH2_CLIENT_ID": "<client-id>",
        "OAUTH2_CLIENT_SECRET": "<client-secret>"
      }
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kyma-companion-mcp": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/<your-org>/kyma-companion-mcp",
        "kyma-companion-mcp"
      ],
      "env": {
        "KYMA_COMPANION_URL": "https://<your-kyma-companion-host>",
        "OAUTH2_TOKEN_URL": "https://<your-idp>/oauth2/token",
        "OAUTH2_CLIENT_ID": "<client-id>",
        "OAUTH2_CLIENT_SECRET": "<client-secret>"
      }
    }
  }
}
```

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `KYMA_COMPANION_URL` | `http://localhost:8000` | Kyma Companion service URL |
| `OAUTH2_TOKEN_URL` | _(empty)_ | OAuth2 token endpoint of your identity provider |
| `OAUTH2_CLIENT_ID` | _(empty)_ | OAuth2 client ID |
| `OAUTH2_CLIENT_SECRET` | _(empty)_ | OAuth2 client secret |
| `KYMA_COMPANION_API_VERSION` | _(empty)_ | Optional API version prefix |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout in seconds |
| `LOG_LEVEL` | `INFO` | Logging level |

Leave all three `OAUTH2_*` variables empty for unauthenticated (local) access. When all three are set, the server uses the OAuth2 client credentials flow and automatically refreshes the token before expiry.

### Changing the URL after installation

For **Claude Code**, edit `~/.claude.json` and find the `env` block under `kyma-companion-mcp`, then restart the MCP server (`Cmd+Shift+P` → Reload Window in VS Code, or restart Claude Code).

For **local development** (running from a clone), set variables in the `.env` file at the project root instead of passing them via the MCP config. The server reads the `.env` file using an absolute path, so it works regardless of the working directory the MCP host uses to launch the process.

## Usage

Once registered, describe what you need in natural language — the agent picks the right tool automatically:

| What you say | Tool invoked |
|---|---|
| _"How do I configure APIRule with OAuth2?"_ | `search_kyma_docs` |
| _"Show me the eventing-manager documentation"_ | `get_component_docs` |
| _"What are Kyma modules?"_ | `explain_kyma_concept` |
| _"api-gateway keeps crashing, help me debug"_ | `get_troubleshooting_guide` |

To invoke a specific tool explicitly:

> "Use `search_kyma_docs` to find how to expose a service with APIRule"

## Extending with other MCP servers

This server covers Kyma knowledge only. For Kyma documentation queries and concept explanations, it is self-contained.

If you also need to operate a Kyma cluster (apply manifests, inspect resources, read logs), check whether your agent already has built-in Kubernetes support. If not, you can register a K8s MCP server alongside this one. For example:

| Need | Suggested MCP server |
|---|---|
| Kubernetes operations (get, apply, delete, logs, events) | [kubernetes-mcp-server](https://github.com/containers/kubernetes-mcp-server) (maintained by Red Hat) |

Each MCP server is registered independently, so you can add or remove them without affecting others.

## Development

```bash
git clone https://github.com/<your-org>/kyma-companion-mcp
cd kyma-companion-mcp
uv sync --dev
uv run pytest
```

See [architecture.md](architecture.md) for design details.
