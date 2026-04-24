# Install Kyma Knowledge MCP Server

Help the user install and configure the `kyma-knowledge-mcp` MCP server. Ask clarifying questions before providing instructions, then give the exact commands or config needed.

## Step 1 — identify the client

Ask which MCP client(s) the user is using:

- **Claude Code** (CLI / VS Code extension)
- **Cline** (VS Code)
- **Claude Desktop**
- Other

## Step 2 — identify the scope (Claude Code only)

If the user is on Claude Code, ask:

- **Project-level**: only available in the current workspace (stored in `.mcp.json`)
- **User**: available in all Claude Code sessions (stored in `~/.claude/`)

## Step 3 — provide the install command

### Claude Code — project-level

```bash
claude mcp add kyma-knowledge-mcp \
  -- uvx --from git+https://github.com/danjiawork/kyma-knowledge-mcp kyma-knowledge-mcp
```

### Claude Code — user (global)

```bash
claude mcp add kyma-knowledge-mcp --scope user \
  -- uvx --from git+https://github.com/danjiawork/kyma-knowledge-mcp kyma-knowledge-mcp
```

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

### Claude Desktop

Add to `claude_desktop_config.json`:

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

## Step 4 — local index (optional)

Ask if the user wants to use a manually built or downloaded index instead of the auto-downloaded one.

If yes, tell them to add this to the `.env` file in their project root:

```bash
LOCAL_INDEX_PATH=/path/to/kyma-docs-index.tar.gz
```

To revert to the auto-downloaded index, remove that line.

## Notes

- On first run the server auto-downloads the pre-built index (~50 MB) to `~/.kyma-knowledge-mcp/`. No credentials needed.
- The MCP connection is instant; the first search query may take a minute while the index loads, subsequent queries are fast.
- `uvx` requires `uv` to be installed. If not present: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- After adding, verify with `claude mcp list` (Claude Code) or by restarting the client.
