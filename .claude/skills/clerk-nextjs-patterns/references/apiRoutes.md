# API Routes / Route Handlers (HIGH)

Next.js Route Handlers (`app/api/.../route.ts`) run on the server. Use `await auth()` for authentication.

> **Note**: In the Ezra monorepo, most API logic lives in FastAPI backend services. Next.js Route Handlers are used for BFF (backend-for-frontend) patterns, webhooks, or proxying.

## Auth Check Pattern

```typescript
// app/api/deals/route.ts
import { auth } from "@clerk/nextjs/server";

export async function GET() {
  const { isAuthenticated, userId, getToken } = await auth();
  if (!isAuthenticated) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Forward to backend API with Clerk token
  const token = await getToken();
  const res = await fetch(`${process.env.API_URL}/api/v1/deals`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  return Response.json(data);
}
```

> **Core 2**: `isAuthenticated` unavailable. Use `if (!userId)` instead.

## 401 vs 403

- **401 Unauthorized** — not authenticated (no valid session)
- **403 Forbidden** — authenticated but lacks permission

```typescript
export async function DELETE(req: Request) {
  const { isAuthenticated, has } = await auth();
  if (!isAuthenticated) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const isAdmin = await has({ role: "org:admin" });
  if (!isAdmin) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  // proceed
  return Response.json({ success: true });
}
```

## Org Route Protection

```typescript
export async function GET(
  req: Request,
  { params }: { params: Promise<{ orgId: string }> },
) {
  const { userId, orgId } = await auth();
  const { orgId: routeOrgId } = await params;

  if (!userId) return Response.json({ error: "Unauthorized" }, { status: 401 });
  if (orgId !== routeOrgId) return Response.json({ error: "Forbidden" }, { status: 403 });

  // fetch org-scoped data from backend
}
```

## When to Use Route Handlers vs Direct Backend Calls

| Use Case | Approach |
|----------|----------|
| Client needs data from backend API | Use Orval-generated hooks (token injected via `ClerkTokenSync`) |
| Server Component needs data | Use `auth().getToken()` + direct `fetch` to backend |
| Webhook from external service | Route Handler (verify webhook signature, no Clerk auth) |
| BFF aggregation (combine multiple backend calls) | Route Handler with `auth()` |
| Proxy to avoid CORS | Route Handler forwarding to backend |

## Docs

[Clerk auth() reference](https://clerk.com/docs/reference/nextjs/auth)
