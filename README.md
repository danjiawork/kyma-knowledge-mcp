# Kyma Companion MCP Server

An MCP (Model Context Protocol) server that provides Kyma documentation and context through integration with Kyma Companion's RAG pipeline.

## Overview

This MCP server enables AI agents (like Cline) to access Kyma-specific knowledge by querying the Kyma Companion RAG API. It works alongside Kubernetes MCP servers to provide comprehensive Kyma context for AI-assisted operations.

## Architecture

```
AI Agent (Cline) [MCP Client]
    │
    ├─── K8s MCP Server (K8s operations)
    │
    └─── Kyma MCP Server (this project)
              │
              └─── HTTP API
                    │
                    └─── Kyma Companion (RAG backend)
```

## Features

### Available Tools

- **search_kyma_docs** - Semantic search across Kyma documentation
- **get_component_docs** - Retrieve component-specific documentation
- **explain_kyma_concept** - Get explanations of Kyma concepts and terminology
- **list_kyma_components** - List available Kyma components
- **get_troubleshooting_guide** - Access troubleshooting documentation

## Prerequisites

- Python 3.12+
- Poetry
- Running Kyma Companion instance with RAG API enabled

## Quick Start

1. **Install dependencies:**
```bash
poetry install
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your Kyma Companion URL
```

3. **Run the server:**
```bash
poetry run kyma-companion-mcp
```

## Configuration

Configure via `.env` file or environment variables:

```bash
KYMA_COMPANION_URL=http://localhost:8000  # Kyma Companion API URL
REQUEST_TIMEOUT=30                        # Request timeout in seconds
LOG_LEVEL=INFO                           # Logging level
```

## Usage with Cline

Add to Cline's MCP configuration:

```json
{
  "mcpServers": {
    "kyma-companion-mcp-server": {
      "disabled": false,
      "command": "poetry",
      "args": ["run", "kyma-companion-mcp"],
      "cwd": "/path/to/kyma-companion-mcp"
    }
  }
}
```

## Example Workflows

**Create a Kyma Function:**
```
User: "Create a Kyma Function for HTTP requests"
→ Cline calls: search_kyma_docs("Kyma Function configuration")
→ Cline applies: kubernetes.apply_manifest(function_yaml)
```

**Configure API Gateway:**
```
User: "Set up API Gateway with OAuth"
→ Cline calls: search_kyma_docs("APIRule OAuth")
→ Cline creates: kubernetes.create_secret(oauth_credentials)
→ Cline applies: kubernetes.apply_manifest(apirule_yaml)
```
