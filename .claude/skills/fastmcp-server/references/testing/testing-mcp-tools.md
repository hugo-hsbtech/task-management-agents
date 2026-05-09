# Testing MCP Tools

How to write tests for MCP tools, resources, and prompts — from fast unit tests to full integration tests with transport.

## Unit Testing Tools Directly

The simplest approach: call tool functions directly, bypassing the MCP protocol layer. Good for testing business logic in isolation.

```python
import pytest
from ezra_api.mcp.server import mcp
from ezra_api.mcp.tools.deals import search_deals


async def test_search_deals_returns_results():
    result = await search_deals(query="solar", limit=5)
    assert len(result) <= 5
    assert all("solar" in d["name"].lower() for d in result)


async def test_search_deals_empty_query_returns_all():
    result = await search_deals(query="", limit=10)
    assert len(result) > 0
```

For tools that use `Context`, mock it:

```python
from unittest.mock import AsyncMock, MagicMock
from fastmcp import Context


def _make_context(**overrides) -> Context:
    ctx = MagicMock(spec=Context)
    ctx.read_resource = AsyncMock(return_value="resource data")
    ctx.report_progress = MagicMock()
    ctx.info = MagicMock()
    for k, v in overrides.items():
        setattr(ctx, k, v)
    return ctx


async def test_process_with_context():
    ctx = _make_context()
    result = await process_data("data://config", ctx=ctx)
    ctx.info.assert_called_once()
    assert "Processed" in result
```

## Integration Testing with FastMCP Client

FastMCP provides `run_server_async()` for in-process integration tests that exercise the full MCP protocol stack without subprocess overhead.

```python
import pytest
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.utilities.tests import run_server_async

from ezra_api.mcp.server import mcp


@pytest.fixture
async def mcp_client():
    async with run_server_async(mcp, transport="streamable-http") as url:
        async with Client(StreamableHttpTransport(url)) as client:
            yield client


async def test_ping_tool(mcp_client):
    result = await mcp_client.call_tool("ping", {})
    assert result[0].text == "pong"


async def test_list_tools(mcp_client):
    tools = await mcp_client.list_tools()
    tool_names = [t.name for t in tools]
    assert "ping" in tool_names


async def test_tool_not_found(mcp_client):
    with pytest.raises(Exception, match="not found"):
        await mcp_client.call_tool("nonexistent", {})
```

### Transport Options for `run_server_async()`

| Parameter | Default | Description |
|---|---|---|
| `transport` | `"streamable-http"` | Transport type: `"streamable-http"`, `"sse"`, or `"http"` |
| `host` | `"127.0.0.1"` | Host to bind |
| `port` | auto | Auto-finds available port if not specified |
| `path` | `"/"` | URL path prefix |

## Testing Authentication

For servers with `ClerkTokenVerifier`, test both authenticated and unauthenticated paths.

### Unit Testing the Verifier

```python
from unittest.mock import AsyncMock, MagicMock

from ezra_authentication.exceptions import InvalidTokenError
from ezra_authentication.schemas import ClerkTokenPayload
from ezra_mcp import ClerkTokenVerifier


VALID_PAYLOAD = ClerkTokenPayload(
    sub="user_123",
    iss="https://clerk.example.dev",
    exp=9999999999,
    iat=1700000000,
    nbf=1700000000,
    azp=None,
)


async def test_valid_token_returns_access_token():
    mock_client = MagicMock()
    mock_client.verify_token = AsyncMock(return_value=VALID_PAYLOAD)
    verifier = ClerkTokenVerifier(mock_client)

    result = await verifier.verify_token("valid-jwt")
    assert result is not None
    assert result.client_id == "user_123"
    assert result.expires_at == 9999999999


async def test_invalid_token_returns_none():
    mock_client = MagicMock()
    mock_client.verify_token = AsyncMock(side_effect=InvalidTokenError("expired"))
    verifier = ClerkTokenVerifier(mock_client)

    result = await verifier.verify_token("bad-jwt")
    assert result is None


async def test_empty_token_skips_verification():
    mock_client = MagicMock()
    mock_client.verify_token = AsyncMock()
    verifier = ClerkTokenVerifier(mock_client)

    result = await verifier.verify_token("")
    assert result is None
    mock_client.verify_token.assert_not_awaited()
```

### Integration Testing Authenticated Endpoints

```python
from starlette.testclient import TestClient


def test_healthz_does_not_require_auth():
    """The /healthz endpoint should be accessible without auth."""
    mcp = create_mcp_server(MCPSettings(name="test"), auth=mock_verifier)
    client = TestClient(mcp.http_app())
    response = client.get("/healthz")
    assert response.status_code == 200
```

## Testing the /healthz Endpoint

Every MCP server created with `create_mcp_server()` gets a `/healthz` route. Test it via `TestClient`:

```python
from starlette.testclient import TestClient
from ezra_mcp import MCPSettings, create_mcp_server


def test_healthz_returns_service_name():
    settings = MCPSettings(name="billing-mcp")
    mcp = create_mcp_server(settings)
    client = TestClient(mcp.http_app())

    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "billing-mcp"}
```

## Testing Settings

Test that `MCPSettings` correctly reads environment variables:

```python
from ezra_mcp import MCPSettings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("MCP_NAME", "custom-mcp")
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_PORT", "9000")
    settings = MCPSettings()
    assert settings.name == "custom-mcp"
    assert settings.transport == "http"
    assert settings.port == 9000


def test_settings_defaults():
    settings = MCPSettings()
    assert settings.name == "ezra-mcp"
    assert settings.transport == "stdio"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8001
```

## Test File Organization

Follow the Ezra testing standards (`docs/development-guides/testing-standards.md`):

```
packages/apps/{name}/
  src/ezra_{name}/mcp/
    server.py
    tools/
      deals.py
  tests/
    test_mcp/
      test_tools_deals.py      # Unit tests for deal tools
      test_server.py            # Integration tests with Client
      test_healthz.py           # /healthz endpoint test
```

Pattern: `test_<function>_<condition>_<expected_result>`

```python
def test_search_deals_empty_query_returns_all(): ...
def test_search_deals_negative_limit_raises_validation_error(): ...
async def test_ping_tool_returns_pong(): ...
```

## HeadlessOAuth for OAuth Testing

FastMCP provides `HeadlessOAuth` for testing OAuth flows without a browser:

```python
from fastmcp.utilities.tests import HeadlessOAuth

oauth = HeadlessOAuth()
# Programmatically simulates the OAuth authorization flow
# Stores HTTP responses and parses authorization codes
```

This is useful when testing servers that use the full OAuth server pattern rather than token verification.

---

> Documentation Index: https://gofastmcp.com/llms.txt
