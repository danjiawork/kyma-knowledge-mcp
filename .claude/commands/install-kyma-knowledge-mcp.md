# Install Kyma Knowledge MCP Server

Help the user install, connect, and verify the `kyma-knowledge-mcp` MCP server.
For Claude Code: run every command directly — never just show them and ask the user to run.
Do the warm-up query yourself to confirm the server is healthy before finishing.

## Pre-check — detect existing installation

Before asking anything, run:

```bash
claude mcp list 2>&1
```

**If `kyma-knowledge-mcp` appears in the output:**

Check the `claude mcp list` output for the scope label next to `kyma-knowledge-mcp` (shown as `user` or `project`).

Tell the user which scope it is currently at, then offer these options:

- **Keep current scope** — proceed directly to verify the connection
- **Switch to project scope** (only available in this workspace) — removes and re-adds at project scope
- **Switch to user scope** (available in all Claude Code sessions) — removes and re-adds at user scope

Wait for their answer:

- If they want to keep current scope or verify only: skip to Step 3 (Warm-up and verify).
- If they want to switch to project scope: run the following, then skip to Step 3:

  ```bash
  claude mcp remove kyma-knowledge-mcp
  claude mcp add kyma-knowledge-mcp \
    -- uvx --from git+https://github.com/danjiawork/kyma-knowledge-mcp kyma-knowledge-mcp
  ```

  Tell the user: "Switched to project scope. Verifying connection now."

- If they want to switch to user scope: run the following, then skip to Step 3:

  ```bash
  claude mcp remove kyma-knowledge-mcp
  claude mcp add kyma-knowledge-mcp --scope user \
    -- uvx --from git+https://github.com/danjiawork/kyma-knowledge-mcp kyma-knowledge-mcp
  ```

  Tell the user: "Switched to user scope. Verifying connection now."

**If `kyma-knowledge-mcp` is NOT in the output:**

Proceed with Step 1 below (normal install flow).

---

## Step 1 — Identify the client

Ask which MCP client they are using:

- **Claude Code** (CLI or VS Code extension)
- **Cline** (VS Code)
- **Claude Desktop**
- Other

---

## Step 2 — Install

### Claude Code

Ask: project-level (this workspace only) or user/global (all Claude Code sessions)?

Check that `uvx` is available first:

```bash
uvx --version 2>&1
```

If missing, install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then ask the user to open a new terminal so `uvx` is on PATH, and come back.

**Run the install command using the Bash tool** (do not show it and ask them to run it):

Project-level:

```bash
claude mcp add kyma-knowledge-mcp \
  -- uvx --from git+https://github.com/danjiawork/kyma-knowledge-mcp kyma-knowledge-mcp
```

User (global):

```bash
claude mcp add kyma-knowledge-mcp --scope user \
  -- uvx --from git+https://github.com/danjiawork/kyma-knowledge-mcp kyma-knowledge-mcp
```

Tell the user: "Registered. Now I'll verify the connection by running a warm-up query — this may take 1–3 minutes on first run while the index downloads."

### Cline (VS Code)

Show the config and tell them which file to edit:

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

Tell them: "Add this to your `cline_mcp_settings.json`, save, and restart VS Code. Once restarted, let me know and I'll verify the connection."

### Claude Desktop

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

Tell them: "Add this to `claude_desktop_config.json`, save, and quit + reopen Claude Desktop. Once restarted, let me know and I'll verify the connection."

---

## Step 3 — Warm-up and verify

Explain before starting:

"Verifying connection now. On first run the server downloads the Kyma docs index (~50 MB) and loads the embedding model — this takes 1–3 minutes. This is a one-time setup; every future session starts in seconds."

Call the `search_kyma_docs` MCP tool with query `"what is Kyma"`.

**If the tool responds successfully:**
Go to Step 4.

**If the tool is not available (not found or connection error) on Claude Code:**
Tell the user: "The server is registered but this session started before it was added. Please open a new Claude Code session — the server will connect automatically. Run `/install-kyma-knowledge-mcp` again in the new session and I'll complete the verification there."

**If the warm-up query times out or errors:**
Go to the Troubleshooting section.

---

## Step 4 — Confirm ready and show examples

Once the warm-up query returns results, tell the user:

"✅ All set — `kyma-knowledge-mcp` is installed, connected, and healthy. Here's what you can ask:"

**User documentation** (for anyone deploying, configuring, or operating Kyma):

- "How do I configure an APIRule with OAuth2?"
- "What Kyma modules are available and how do I enable them?"
- "How do I expose a service externally on SAP BTP Kyma?"
- "My eventing subscription isn't triggering — how do I debug it?"
- "What regions does Kyma support?"

**Contributor documentation** (for anyone developing or contributing to Kyma itself):

- "How do I run api-gateway integration tests locally?"
- "What is the PR process for Kyma?"
- "Show me architecture decisions (ADRs) for eventing-manager."
- "How do I set up a local dev environment for telemetry-manager?"

"Just ask in natural language — you don't need to call any tool directly. Claude picks the right tool automatically."

---

## Troubleshooting

**Warm-up query hangs for more than 5 minutes:**
Check internet access — the index downloads from GitHub Releases (~50 MB).
If behind a proxy or firewall, use a local index:

```bash
claude mcp add kyma-knowledge-mcp \
  --env LOCAL_INDEX_PATH=/path/to/kyma-docs-index.tar.gz \
  -- uvx --from git+https://github.com/danjiawork/kyma-knowledge-mcp kyma-knowledge-mcp
```

**`uvx: command not found`:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart the terminal, then re-run from Step 2.

**Server shows as disconnected or tools unavailable after a new session:**

```bash
claude mcp remove kyma-knowledge-mcp
```

Re-run the install step.

**Want to use a manually built index:**
Pass `LOCAL_INDEX_PATH` pointing to a directory or `.tar.gz` archive produced by `kyma-knowledge-mcp-build-index`.
