---
name: fastmcp-server
description: Complete guide for building MCP servers with FastMCP 3.0 and scaffolding MCP servers in this project. Use when creating Python MCP servers, adding MCP tools, or scaffolding MCP for a backend app. Triggers on "add MCP server to", "scaffold MCP for", "create MCP tools for", "new MCP server", "FastMCP".
version: 1.0.0
author: FastMCP Community
license: MIT
tags: [FastMCP, MCP, Python, AI, Tools, Server, Authentication, Providers]
dependencies: []
---

# FastMCP 3.0 Server Development

Complete reference for building production-ready MCP (Model Context Protocol) servers with FastMCP 3.0 - the fast, Pythonic framework for connecting LLMs to tools and data.

## When to use this skill

**Use FastMCP Server when:**
- Creating a new MCP server in Python
- Adding tools, resources, or prompts to an MCP server
- Scaffolding an MCP server for a new or existing backend app
- Adding MCP capabilities to a FastAPI service in this project
- Implementing authentication (OAuth, OIDC, token verification)
- Setting up middleware for logging, rate limiting, or authorization
- Configuring providers (local, filesystem, skills, custom)
- Building production MCP servers with telemetry and storage
- Upgrading from FastMCP 2.x to 3.0

**Key areas covered:**
- **Tools, Resources & Prompts** (CORE): Decorators, validation, return types, templates, message helpers
- **Context & DI** (CORE): MCP context, dependency injection, background tasks
- **Authentication** (SECURITY): OAuth, OIDC, token verification, proxy patterns
- **Authorization** (SECURITY): Scope-based access control, multi-tenant tool scoping
- **Testing** (QUALITY): Unit tests, integration tests with Client, auth testing
- **Integration** (DEPLOYMENT): Claude Desktop, Claude Code, GoClaw, custom clients
- **Middleware** (ADVANCED): Request/response pipeline, built-in middleware
- **Providers** (ADVANCED): Local, filesystem, skills, and custom providers
- **Features** (ADVANCED): Pagination, sampling, storage, OpenTelemetry, versioning

## Quick reference

### Core patterns

**Create a server with tools:**
```python
from fastmcp import FastMCP

mcp = FastMCP("MyServer")

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b
```

**Create a resource:**
```python
@mcp.resource("data://config")
def get_config() -> dict:
    """Return server configuration"""
    return {"version": "1.0", "debug": False}
```

**Create a resource template:**
```python
@mcp.resource("users://{user_id}/profile")
def get_user_profile(user_id: str) -> dict:
    """Get a user's profile by ID"""
    return fetch_user(user_id)
```

**Create a prompt:**
```python
@mcp.prompt
def review_code(code: str, language: str = "python") -> str:
    """Review code for best practices"""
    return f"Review this {language} code:\n\n{code}"
```

**Run the server:**
```python
if __name__ == "__main__":
    mcp.run()

# Or with transport options:
# mcp.run(transport="sse", host="0.0.0.0", port=8000)
```

### Using context in tools

```python
from fastmcp import FastMCP, Context

mcp = FastMCP("MyServer")

@mcp.tool
def process_data(uri: str, ctx: Context) -> str:
    """Process data with logging and progress"""
    ctx.info(f"Processing {uri}")
    ctx.report_progress(0, 100)
    data = ctx.read_resource(uri)
    ctx.report_progress(100, 100)
    return f"Processed: {data}"
```

### Authentication setup

```python
from fastmcp import FastMCP
from fastmcp.server.auth import BearerAuthProvider

auth = BearerAuthProvider(
    jwks_uri="https://your-provider/.well-known/jwks.json",
    audience="your-api",
    issuer="https://your-provider/"
)

mcp = FastMCP("SecureServer", auth=auth)
```

## Key concepts

### Tools
Functions exposed as executable capabilities for LLMs. Decorated with `@mcp.tool`. Support Pydantic validation, async, custom return types, and annotations (readOnlyHint, destructiveHint).

### Resources & Templates
Static or dynamic data sources identified by URIs. Resources use fixed URIs (`data://config`), templates use parameterized URIs (`users://{id}/profile`). Support MIME types, annotations, and wildcard parameters.

### Context
The `Context` object provides access to MCP features within tools/resources: logging, progress reporting, resource access, LLM sampling, user elicitation, and session state.

### Dependency Injection
Inject values into tool/resource functions using `Depends()`. Supports HTTP requests, access tokens, custom dependencies, and generator-based cleanup patterns.

### Providers
Control where components come from. `LocalProvider` (default, decorator-based), `FileSystemProvider` (load from Python files on disk), `SkillsProvider` (packaged bundles), or custom providers.

### Authentication & Authorization
Multiple auth patterns: token verification (JWT, JWKS), OAuth proxy, OIDC proxy, remote OAuth, and full OAuth server. Authorization via scopes on components and middleware.

### Middleware
Intercept and modify requests/responses. Built-in middleware for rate limiting, error handling, logging, and response size limits. Custom middleware via `@mcp.middleware`.

## Using the references

Detailed documentation is organized in the `references/` folder:

### Getting Started
- **getting-started/installation.md** - Install FastMCP, optional dependencies, verify setup
- **getting-started/upgrade-guide.md** - Migrate from FastMCP 2.x to 3.0
- **getting-started/quickstart.md** - First server, tools, resources, prompts, running

### Server
- **server/server-class.md** - FastMCP server configuration, transport options, tag filtering
- **server/tools.md** - Tool decorator, parameters, validation, return types, annotations
- **server/resources-and-templates.md** - Resources, templates, URIs, wildcards, MIME types
- **server/prompts.md** - Prompt decorator, return types, arguments, Message helper, DI, auth

### Context
- **context/mcp-context.md** - Context object, logging, progress, resource access, sampling
- **context/background-tasks.md** - Long-running operations with task support
- **context/dependency-injection.md** - Depends(), custom deps, HTTP request, access tokens
- **context/user-elicitation.md** - Request structured input from users during execution

### Features
- **features/icons.md** - Custom icons for tools, resources, prompts, and servers
- **features/lifespans.md** - Server lifecycle management and startup/shutdown hooks
- **features/client-logging.md** - Send log messages to MCP clients
- **features/middleware.md** - Request/response pipeline, built-in and custom middleware
- **features/pagination.md** - Paginate large component lists
- **features/progress-reporting.md** - Report progress for long-running operations
- **features/sampling.md** - Request LLM completions from the client
- **features/storage-backends.md** - Memory, file, and Redis storage for caching and tokens
- **features/opentelemetry.md** - Distributed tracing and observability
- **features/versioning.md** - Version components and filter by version ranges

### Authentication
- **authentication/token-verification.md** - JWT, JWKS, introspection, static keys, custom
- **authentication/remote-oauth.md** - Delegate auth to upstream OAuth provider
- **authentication/oauth-proxy.md** - Full OAuth proxy with PKCE, client management
- **authentication/oidc-proxy.md** - OpenID Connect proxy with auto-discovery
- **authentication/full-oauth-server.md** - Complete built-in OAuth server

### Authorization
- **authorization.md** - Scope-based access control, middleware authorization, patterns
- **authorization/multi-tenant-scoping.md** - Tenant isolation via token claims, DI, data filtering, middleware

### Testing
- **testing/testing-mcp-tools.md** - Unit tests, integration tests with Client, auth testing, /healthz tests

### Integration
- **integration/llm-runtime-integration.md** - Claude Desktop, Claude Code, GoClaw, custom Python clients, deployment patterns

### Providers
- **providers/local.md** - Default provider, decorator-based component registration
- **providers/filesystem.md** - Load components from Python files on disk
- **providers/skills.md** - Package and distribute component bundles
- **providers/custom.md** - Build custom providers for any component source

## Project Integration

When scaffolding MCP servers in this project, use the `ezra-mcp` shared infrastructure domain.

### Shared Infrastructure (`ezra-mcp` domain at `backend/packages/domains/mcp/`)

```python
from ezra_mcp import MCPSettings, ClerkTokenVerifier, create_mcp_server, run_mcp_server
```

- `MCPSettings` — pydantic-settings for MCP config. Env prefix: `MCP_`. Fields: `name`, `transport` (stdio|http), `host`, `port`, `instructions`.
- `ClerkTokenVerifier` — FastMCP `TokenVerifier` wrapping `ClerkClient` for Clerk JWT auth with circuit breaker.
- `create_mcp_server(settings, lifespan=..., auth=...)` — factory that creates FastMCP with `/healthz` endpoint and optional auth.
- `run_mcp_server(mcp, settings)` — transport selection: stdio (default) or streamable-http.

### Scaffolding an MCP Server for an App

When user asks to add MCP to a backend app, follow these steps:

#### Step 1: Derive Names

From app path `packages/apps/{name}`:
- Package: `ezra-{name}`
- Module: `ezra_{name}`
- MCP service: `{name}-mcp`
- Port: next available 8001+ (check `backend/docker-compose.yml`)

#### Step 2: Read Existing Files

Before making changes, read:
- `backend/packages/apps/{name}/pyproject.toml`
- `backend/packages/apps/{name}/src/ezra_{name}/main.py`
- `backend/docker-compose.yml`

#### Step 3: Create `mcp/` Module

Create at `backend/packages/apps/{name}/src/ezra_{name}/mcp/`:

**`mcp/__init__.py`** — empty

**`mcp/server.py`**:
```python
"""FastMCP server for {name}."""

from contextlib import asynccontextmanager

from ezra_mcp import MCPSettings, create_mcp_server
from fastmcp import FastMCP

settings = MCPSettings(
    name="{name}-mcp",
    instructions="{description}.",
)


@asynccontextmanager
async def lifespan(server: FastMCP):
    # Initialize resources here (DB, clients, etc.)
    yield


mcp = create_mcp_server(settings, lifespan=lifespan)

# Import tool modules to register them (must be after mcp is defined)
from ezra_{name}.mcp.tools import example  # noqa: F401, E402
```

**`mcp/tools/__init__.py`** — empty

**`mcp/tools/example.py`**:
```python
"""Example MCP tools -- replace with real tools."""

from ezra_{name}.mcp.server import mcp


@mcp.tool()
async def ping() -> str:
    """Health check tool. Replace with real tools."""
    return "pong"
```

**`mcp/__main__.py`**:
```python
"""Entrypoint for running the MCP server."""

from ezra_mcp import run_mcp_server

from ezra_{name}.mcp.server import mcp, settings

run_mcp_server(mcp, settings)
```

#### Step 4: Add Dependency

Add `"ezra-mcp"` to the app's `pyproject.toml` dependencies if not already present.

#### Step 5: Create Dockerfile

Create `backend/packages/apps/{name}/Dockerfile.mcp`:
```dockerfile
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.10.11 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages packages

RUN uv sync --frozen --no-dev --package ezra-{name}

EXPOSE {port}

ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT={port}
ENV MCP_NAME={name}-mcp

CMD ["uv", "run", "--no-dev", "--package", "ezra-{name}", "python", "-m", "ezra_{name}.mcp"]
```

#### Step 6: Add to docker-compose.yml

Add to `backend/docker-compose.yml`:
```yaml
  {name}-mcp:
    <<: *api-common
    profiles: [prod]
    build:
      context: .
      dockerfile: packages/apps/{name}/Dockerfile.mcp
    ports:
      - "{port}:{port}"
    environment:
      <<: *api-env
      MCP_TRANSPORT: http
      MCP_HOST: "0.0.0.0"
      MCP_PORT: "{port}"
      MCP_NAME: {name}-mcp

  {name}-mcp-dev:
    <<: *api-common
    profiles: [dev]
    image: ghcr.io/astral-sh/uv:python3.12-bookworm-slim
    working_dir: /app
    ports:
      - "{port}:{port}"
    volumes:
      - .:/app
      - {name}_mcp_venv:/app/.venv
    environment:
      <<: *api-env
      MCP_TRANSPORT: http
      MCP_HOST: "0.0.0.0"
      MCP_PORT: "{port}"
      MCP_NAME: {name}-mcp
    command: >
      bash -c "uv sync --frozen --package ezra-{name} &&
      uv run --package ezra-{name} python -m ezra_{name}.mcp"
```

Add volume `{name}_mcp_venv:` to the volumes section.

#### Step 7: Verify

```bash
cd backend && uv run ruff check packages/apps/{name}/src/ezra_{name}/mcp/
cd backend && uv run python -c "from ezra_{name}.mcp.server import mcp; print(mcp.name)"
MCP_TRANSPORT=http MCP_HOST=0.0.0.0 MCP_PORT={port} uv run --package ezra-{name} python -m ezra_{name}.mcp
```

### Examples

**Add MCP server to the API app:**
```
User: add MCP server to packages/apps/api
Result: mcp/ module in ezra_api, Dockerfile.mcp, compose service on port 8001
```

**Add MCP server with description:**
```
User: scaffold MCP for packages/apps/billing "Invoice and payment management"
Result: Same structure, instructions set to "Invoice and payment management"
```

### Troubleshooting

**`ModuleNotFoundError: ezra_mcp`:**
Run `cd backend && uv sync` and check `ezra-mcp` is in the app's pyproject.toml.

**Circular import in tool modules:**
Tools import `mcp` from `server.py`; `server.py` imports tool modules at bottom after `mcp` is defined.

**Port conflict:**
Check `backend/docker-compose.yml`. FastAPI apps use 8000+, MCP servers use 8001+.

**`ValidationError` on startup:**
`MCP_TRANSPORT` only accepts `stdio` or `http`. `MCP_PORT` must be 1-65535. Check env vars for typos.

### Adding Clerk Authentication

Auth is optional — omit `auth=` for unauthenticated MCP servers. To add Clerk JWT auth:

1. Add `"ezra-authentication"` to the app's `pyproject.toml` (if not already there)
2. Create `ClerkClient` in the lifespan and pass `ClerkTokenVerifier` to `create_mcp_server`:

```python
from contextlib import asynccontextmanager

from ezra_authentication.infrastructure import ClerkClient
from ezra_authentication.settings import ClerkSettings
from ezra_mcp import MCPSettings, ClerkTokenVerifier, create_mcp_server
from fastmcp import FastMCP

settings = MCPSettings(name="{name}-mcp", instructions="...")
clerk_client = ClerkClient(ClerkSettings())
auth = ClerkTokenVerifier(clerk_client)


@asynccontextmanager
async def lifespan(server: FastMCP):
    yield


mcp = create_mcp_server(settings, lifespan=lifespan, auth=auth)
```

**Required env vars**: same `CLERK_SECRET_KEY`, `CLERK_WEBHOOK_SIGNING_SECRET`, `CLERK_PUBLISHABLE_KEY` as the FastAPI app. No new config needed.

**How it works**: `ClerkTokenVerifier` wraps `ClerkClient.verify_token()` — reuses the existing circuit breaker, JWKS caching, and Clerk SDK. Returns `AccessToken(client_id=clerk_user_id, claims={sub, iss, exp, ...})` on success, `None` on failure.

### What This Skill Does NOT Do

- Does not create the app itself (use standard app scaffolding)
- Does not write real tool implementations (creates example tool only)
- Does not configure auth/OAuth for the MCP server
- Does not set up CI workflows for MCP servers

## Version history

**v1.0.0** (February 2026)
- Initial release covering FastMCP 3.0 (release candidate)
- 30 reference files across 7 categories
- Complete coverage of tools, resources, context, auth, providers, and features

**v1.1.0** (March 2026)
- Added Ezra Platform Integration section
- Scaffolding steps for adding MCP servers to backend apps
- Templates for server.py, tools, __main__.py, Dockerfile.mcp, docker-compose

**v1.2.0** (March 2026)
- Added testing reference: unit tests, integration tests with Client, auth testing patterns
- Added LLM runtime integration reference: Claude Desktop, Claude Code, GoClaw, custom clients
- Added multi-tenant tool scoping reference: tenant isolation via token claims, DI, data filtering
