# Multi-Tenant Tool Scoping

Patterns for isolating MCP tools, resources, and data by tenant — so each tenant sees only their own data and capabilities.

## How Tenancy Works in MCP

FastMCP has no built-in multi-tenancy. Tenant isolation is implemented through three layers:

1. **Token claims** — tenant identity embedded in the JWT
2. **Authorization checks** — tool/resource access gated by tenant
3. **Data filtering** — tools query only the tenant's data

All three layers work together. Missing any one creates a gap.

## Layer 1: Tenant Identity from Token Claims

Store `tenant_id` (or `org_id` for Clerk) in the JWT. The `ClerkTokenVerifier` already puts all claims into `AccessToken.claims`, so tenant info flows through automatically.

```python
from fastmcp.server.dependencies import get_access_token


@mcp.tool
async def list_projects(ctx: Context) -> list[dict]:
    token = get_access_token()
    tenant_id = token.claims.get("org_id") if token else None
    if not tenant_id:
        return []
    return await db.fetch_projects(tenant_id=tenant_id)
```

### Extracting Tenant via Dependency Injection

For cleaner code, create a reusable dependency:

```python
from fastmcp import Depends
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.auth.auth import AccessToken


def get_tenant_id(token: AccessToken = Depends(get_access_token)) -> str:
    """Extract tenant_id from token claims. Raises if missing."""
    tenant_id = token.claims.get("org_id") if token else None
    if not tenant_id:
        raise ValueError("No tenant_id in token claims")
    return tenant_id


@mcp.tool
async def list_projects(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    return await db.fetch_projects(tenant_id=tenant_id)


@mcp.tool
async def get_project(project_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    project = await db.get_project(project_id)
    if project.tenant_id != tenant_id:
        raise PermissionError("Access denied")
    return project
```

The `Depends(get_tenant_id)` pattern keeps tenant extraction consistent across all tools.

## Layer 2: Authorization Checks

Use FastMCP's authorization system to gate access at the component level.

### Scope-Based Tenant Authorization

```python
from fastmcp.server.auth import require_scopes


@mcp.tool(auth=require_scopes("tenant:read"))
async def list_invoices(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    return await db.fetch_invoices(tenant_id=tenant_id)


@mcp.tool(auth=require_scopes("tenant:write"))
async def create_invoice(data: dict, tenant_id: str = Depends(get_tenant_id)) -> dict:
    return await db.create_invoice(tenant_id=tenant_id, **data)
```

### Custom Tenant Authorization

For finer control, write a custom auth check:

```python
def require_tenant_access(required_role: str = "member"):
    """Authorization check that verifies tenant membership and role."""
    async def check(ctx) -> bool:
        token = ctx.token
        if not token:
            return False

        org_id = token.claims.get("org_id")
        org_role = token.claims.get("org_role", "member")

        if not org_id:
            return False

        role_hierarchy = {"admin": 3, "manager": 2, "member": 1, "viewer": 0}
        return role_hierarchy.get(org_role, 0) >= role_hierarchy.get(required_role, 0)

    return check


@mcp.tool(auth=require_tenant_access("admin"))
async def delete_project(project_id: str, tenant_id: str = Depends(get_tenant_id)) -> str:
    await db.delete_project(project_id, tenant_id=tenant_id)
    return f"Deleted project {project_id}"
```

## Layer 3: Data Filtering

Every database query in a multi-tenant tool must include the tenant filter. Never trust the client to send the tenant ID as a parameter — always derive it from the token.

### Pattern: Tenant-Scoped Repository

```python
class TenantRepository:
    """Wraps DB access with automatic tenant filtering."""

    def __init__(self, session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    async def list_deals(self, **filters) -> list[Deal]:
        query = select(Deal).where(Deal.tenant_id == self.tenant_id)
        for key, value in filters.items():
            query = query.where(getattr(Deal, key) == value)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_deal(self, deal_id: str) -> Deal | None:
        result = await self.session.execute(
            select(Deal).where(Deal.id == deal_id, Deal.tenant_id == self.tenant_id)
        )
        return result.scalar_one_or_none()
```

Wire it into tools via the lifespan and context:

```python
@asynccontextmanager
async def lifespan(server: FastMCP):
    async with create_db_session() as session:
        server.state["db_session"] = session
        yield


@mcp.tool
async def list_deals(
    ctx: Context,
    status: str = "active",
    tenant_id: str = Depends(get_tenant_id),
) -> list[dict]:
    session = ctx.state["db_session"]
    repo = TenantRepository(session, tenant_id)
    deals = await repo.list_deals(status=status)
    return [d.to_dict() for d in deals]
```

## Tenant-Aware Middleware

For cross-cutting tenant enforcement, use middleware to extract and validate the tenant before any tool runs:

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext


class TenantMiddleware(Middleware):
    """Extract tenant from token and store in request state."""

    async def on_request(self, context: MiddlewareContext, call_next):
        token = context.fastmcp_context.get_access_token() if context.fastmcp_context else None

        if token:
            tenant_id = token.claims.get("org_id")
            if tenant_id and context.fastmcp_context:
                context.fastmcp_context.set_state("tenant_id", tenant_id)

        return await call_next(context)


mcp = FastMCP("TenantServer", middleware=[TenantMiddleware()])
```

Then tools read from state instead of extracting from token each time:

```python
@mcp.tool
async def list_deals(ctx: Context) -> list[dict]:
    tenant_id = ctx.state.get("tenant_id")
    if not tenant_id:
        raise PermissionError("Tenant context required")
    return await db.fetch_deals(tenant_id=tenant_id)
```

## Important Constraints

**STDIO has no auth.** In STDIO mode, there's no HTTP layer, so `get_access_token()` returns `None` and all auth checks are skipped. Multi-tenant scoping only works with HTTP transports (`streamable-http` or `sse`).

**Tool visibility is not tenant-scoped.** All clients see all registered tools in `list_tools()`. Tenant scoping happens at execution time (data filtering) and authorization time (access checks), not at discovery time. If you need to hide tools from certain tenants, use tag-based filtering with `restrict_tag()`.

**Cross-tenant prevention.** Never accept `tenant_id` as a tool parameter from the client. Always derive it from the authenticated token:

```python
# BAD: client can pass any tenant_id
@mcp.tool
async def list_deals(tenant_id: str) -> list[dict]: ...

# GOOD: tenant_id comes from token
@mcp.tool
async def list_deals(tenant_id: str = Depends(get_tenant_id)) -> list[dict]: ...
```

---

> Documentation Index: https://gofastmcp.com/llms.txt
