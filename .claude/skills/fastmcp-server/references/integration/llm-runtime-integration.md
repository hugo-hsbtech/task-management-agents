# LLM Runtime Integration

How to connect MCP servers to LLM clients — Claude Desktop, Claude Code, GoClaw, and custom clients.

## Transport Overview

MCP servers communicate with clients over one of three transports. The transport determines how clients connect.

| Transport | Use case | Client connects via |
|---|---|---|
| `stdio` | Local dev, CLI tools, Claude Desktop (local) | Subprocess stdin/stdout |
| `streamable-http` | Docker, remote servers, multi-client | HTTP URL (e.g., `http://localhost:8001`) |
| `sse` | Legacy HTTP, browser clients | HTTP URL with `/sse` path |

In the Ezra platform, `MCPSettings.transport` controls this — set via `MCP_TRANSPORT` env var.

## Claude Desktop

Claude Desktop connects to MCP servers via its config file.

### Config file location

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

### STDIO (local development)

Claude Desktop spawns the MCP server as a subprocess. Best for local development — no port management, no Docker needed.

```json
{
  "mcpServers": {
    "api-mcp": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/ezra/platform/backend",
        "run", "--package", "ezra-api",
        "python", "-m", "ezra_api.mcp"
      ],
      "env": {
        "CLERK_SECRET_KEY": "sk_test_...",
        "CLERK_WEBHOOK_SIGNING_SECRET": "whsec_...",
        "CLERK_PUBLISHABLE_KEY": "pk_test_..."
      }
    }
  }
}
```

The `command` + `args` pattern is the MCP standard. Claude Desktop will start and stop the process automatically.

### HTTP (remote or Docker)

For servers running in Docker or on a remote host, start the server with HTTP transport first, then configure Claude Desktop to connect:

```json
{
  "mcpServers": {
    "api-mcp": {
      "url": "http://localhost:8001",
      "transport": "streamable-http"
    }
  }
}
```

Start the server:
```bash
MCP_TRANSPORT=http MCP_PORT=8001 uv run --package ezra-api python -m ezra_api.mcp
```

Or via Docker:
```bash
docker compose --profile dev up api-mcp-dev
```

## Claude Code

Claude Code connects to MCP servers configured in its settings. MCP servers can be configured at the project level (`.claude/settings.json`) or user level (`~/.claude/settings.json`).

### STDIO configuration

```json
{
  "mcpServers": {
    "api-mcp": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/ezra/platform/backend",
        "run", "--package", "ezra-api",
        "python", "-m", "ezra_api.mcp"
      ],
      "env": {
        "CLERK_SECRET_KEY": "sk_test_..."
      }
    }
  }
}
```

### HTTP configuration

```json
{
  "mcpServers": {
    "api-mcp": {
      "url": "http://localhost:8001"
    }
  }
}
```

## GoClaw

GoClaw uses the same MCP config format. Provide the config via its `--mcp-config` flag or configuration file:

```json
{
  "mcpServers": {
    "api-mcp": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/ezra/platform/backend",
        "run", "--package", "ezra-api",
        "python", "-m", "ezra_api.mcp"
      ]
    }
  }
}
```

For HTTP transport, use the URL format:

```json
{
  "mcpServers": {
    "api-mcp": {
      "url": "http://localhost:8001",
      "transport": "streamable-http"
    }
  }
}
```

## Custom Python Clients

Use the FastMCP `Client` class to connect programmatically — useful for testing, automation, or building custom LLM pipelines.

### STDIO

```python
from fastmcp.client import Client

async with Client("path/to/server.py") as client:
    tools = await client.list_tools()
    result = await client.call_tool("ping", {})
    print(result[0].text)
```

### Streamable HTTP

```python
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

transport = StreamableHttpTransport("http://localhost:8001")

async with Client(transport) as client:
    result = await client.call_tool("search_deals", {"query": "solar"})
```

### SSE

```python
from fastmcp.client import Client
from fastmcp.client.transports import SSETransport

transport = SSETransport("http://localhost:8001/sse")

async with Client(transport) as client:
    result = await client.call_tool("ping", {})
```

### With Authentication

```python
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

transport = StreamableHttpTransport(
    "http://localhost:8001",
    headers={"Authorization": "Bearer eyJ..."}
)

async with Client(transport) as client:
    result = await client.call_tool("search_deals", {"query": "solar"})
```

Client also supports `auth="oauth"` for interactive OAuth flows and custom `httpx.Auth` objects.

## Ezra Platform: Transport Selection

The `ezra-mcp` runner handles transport selection via `MCPSettings`:

```python
from ezra_mcp import MCPSettings, run_mcp_server
from ezra_api.mcp.server import mcp

settings = MCPSettings()  # reads MCP_TRANSPORT env var
run_mcp_server(mcp, settings)
```

| `MCP_TRANSPORT` | Behavior |
|---|---|
| `stdio` (default) | `mcp.run(transport="stdio")` — for Claude Desktop local, Claude Code |
| `http` | `mcp.run(transport="streamable-http", host=..., port=...)` — for Docker, remote |

## Deployment Patterns

### Local development (Claude Desktop + STDIO)

No Docker needed. Claude Desktop spawns the server as a subprocess.

```
Claude Desktop → (stdio) → uv run python -m ezra_api.mcp
```

### Docker development (HTTP)

```
Claude Desktop/Code → (HTTP :8001) → api-mcp-dev container
```

```bash
docker compose --profile dev up api-mcp-dev
```

### Production (HTTP behind reverse proxy)

```
Client → (HTTPS) → nginx/ALB → (HTTP :8001) → api-mcp container
```

The MCP server itself doesn't handle TLS — terminate SSL at the reverse proxy.

---

> Documentation Index: https://gofastmcp.com/llms.txt
