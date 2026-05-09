---
name: clerk-nextjs-patterns
description: >-
  Clerk authentication patterns for the Ezra Next.js monorepo — server vs client auth,
  middleware strategies, Server Actions, API route protection, caching with auth,
  and token injection via authTokenProvider for Orval-generated hooks. Use when adding
  Clerk auth to a new app, protecting routes or actions, wiring auth tokens into API calls,
  debugging "unauthorized" or 401/403 errors, asking "how does auth work in this app",
  checking why an API call returns 401, protecting a page or Server Action, or implementing
  role/permission checks. Also use when touching middleware.ts, ClerkProvider, ClerkTokenSync,
  authTokenProvider, or any import from @clerk/nextjs. Do NOT use for Clerk SDK installation
  or initial project setup (see Clerk docs quickstart).
origin: Ezra
---

# Clerk + Next.js Patterns (Ezra Monorepo)

Clerk authentication patterns adapted for the Ezra multi-app, multi-API monorepo. Covers server/client auth APIs, middleware, Server Actions, API route protection, caching, and the token injection bridge that connects Clerk to Orval-generated TanStack Query hooks.

> **SDK version**: Check `package.json` for `@clerk/nextjs` version. This skill targets v7+ (Core 3). Core 2 differences noted inline.

## When to Activate

- Adding Clerk authentication to a new frontend app
- Protecting routes via middleware (public-first vs protected-first)
- Writing Server Actions or Route Handlers that need auth
- Wiring Clerk tokens into Orval-generated API hooks
- Debugging "unauthorized" errors from the backend API
- Implementing user-scoped caching in Server Components
- Adding org/RBAC permission checks to routes or actions

## First Reads

Read these files before changing auth code:

- `frontend/apps/deal-triage/src/middleware.ts` — reference middleware (protected-first)
- `frontend/apps/deal-triage/src/app/layout.tsx` — ClerkProvider + QueryProvider wiring
- `frontend/packages/hooks/src/authTokenProvider.ts` — singleton token bridge
- `frontend/packages/hooks/src/clerkTokenSync.tsx` — Clerk-to-singleton bridge component
- `frontend/packages/api-client/src/mutators/base.ts` — auto-injects Bearer token via authTokenProvider

## Mental Model

**Server vs Client = different auth APIs. Never mix them.**

| Context | Import | API | Async? |
|---------|--------|-----|--------|
| Server Components, Server Actions, Route Handlers | `@clerk/nextjs/server` | `await auth()` | Yes |
| Client Components | `@clerk/nextjs` | `useAuth()`, `useUser()` | No (hook) |

Key properties from `auth()`: `isAuthenticated`, `sessionStatus`, `userId`, `orgId`, `orgSlug`, `has()`, `protect()`

> **Core 2**: `isAuthenticated` and `sessionStatus` unavailable. Use `!!userId` instead.

## Token Flow (Ezra-Specific)

Orval-generated hooks call `baseFetch` which auto-injects Clerk tokens. The bridge:

```
ClerkProvider (layout.tsx)
  -> ClerkTokenSync (renders inside ClerkProvider)
    -> useAuth().getToken (Clerk hook)
    -> setTokenGetter(getToken) (registers in singleton)

Orval hook fires
  -> customFetch (mutator)
    -> baseFetch
      -> getAuthToken() (reads singleton)
      -> Authorization: Bearer <token> header
```

### Correct Layout Wiring

Every Clerk-enabled app MUST render `<ClerkTokenSync />` inside `<ClerkProvider>`:

```tsx
// apps/<app>/src/app/layout.tsx
import { ClerkProvider } from "@clerk/nextjs";
import { QueryProvider } from "@ezra/hooks/queryProvider";
import { ClerkTokenSync } from "@ezra/hooks/clerkTokenSync";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body>
          <ClerkTokenSync />
          <QueryProvider>{children}</QueryProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
```

Once mounted, ALL Orval-generated hooks automatically send authenticated requests. No manual `getToken()` calls needed in components.

### Server-Side Token Access

`ClerkTokenSync` only works client-side. For Server Components, Server Actions, and Route Handlers, use `await auth()` directly:

```tsx
import { auth } from "@clerk/nextjs/server";

// Server Component
export default async function Page() {
  const { userId } = await auth();
  // ...
}

// Server Action — use getToken() for backend API calls
"use server";
export async function createDeal(formData: FormData) {
  const { userId, getToken } = await auth();
  if (!userId) throw new Error("Unauthorized");

  const token = await getToken();
  await fetch(`${process.env.API_URL}/api/v1/deals`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ name: formData.get("name") }),
  });
}
```

## References

| Reference | Impact | Topic |
|-----------|--------|-------|
| `references/serverVsClient.md` | CRITICAL | `await auth()` vs hooks, import rules |
| `references/middlewareStrategies.md` | HIGH | Public-first vs protected-first per app |
| `references/serverActions.md` | HIGH | Protecting mutations, RBAC checks |
| `references/apiRoutes.md` | HIGH | Route Handler auth, 401 vs 403 |
| `references/cachingAuth.md` | MEDIUM | User-scoped caching patterns |

## Adding Clerk to a New App

1. Install `@clerk/nextjs` (pin exact version matching other apps)
2. Add env vars to `.env` and `.env.example`:
   ```
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
   CLERK_SECRET_KEY=
   ```
3. Add `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` to `frontend/turbo.json` `build.env` array
4. Create `src/middleware.ts` (see `references/middlewareStrategies.md`)
5. Wrap layout with `<ClerkProvider>` and mount `<ClerkTokenSync />`
6. Orval hooks now send auth tokens automatically

## Org / RBAC Patterns

Clerk organizations support multi-tenant access control. These patterns apply when org-based features are needed.

### Middleware: Org Route Protection

```typescript
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isOrgRoute = createRouteMatcher(["/org/(.*)"]);

export default clerkMiddleware(async (auth, req) => {
  if (isOrgRoute(req)) {
    const { orgId } = await auth();
    if (!orgId) await auth.protect(); // redirects to sign-in or org selector
  }
});
```

### Permission Check in Components

```tsx
// Server Component
import { auth } from "@clerk/nextjs/server";

export default async function AdminPanel() {
  const { has } = await auth();
  const canManage = await has({ permission: "org:deals:manage" });
  if (!canManage) return <p>Access denied</p>;
  // ...
}
```

```tsx
// Client Component
"use client";
import { useAuth } from "@clerk/nextjs";

export function DeleteButton({ dealId }: { dealId: string }) {
  const { has } = useAuth();
  if (!has?.({ permission: "org:deals:delete" })) return null;
  return <button>Delete</button>;
}
```

### Permission Check in Server Actions

```typescript
"use server";
import { auth } from "@clerk/nextjs/server";

export async function deleteDeal(dealId: string) {
  const { userId, has } = await auth();
  if (!userId) throw new Error("Unauthorized");
  const canDelete = await has({ permission: "org:deals:delete" });
  if (!canDelete) throw new Error("Forbidden");
  // proceed with deletion via backend API
}
```

## Common Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `undefined` userId in Server Component | Missing `await` | `await auth()` not `auth()` |
| Orval hooks send unauthenticated requests | `ClerkTokenSync` not mounted | Add to layout inside `ClerkProvider` |
| Manual `getToken()` in every component | Not using Orval hooks | Mount `ClerkTokenSync`, use generated hooks |
| Auth fails on API routes | Missing matcher in middleware | Add `'/(api\|trpc)(.*)'` to matcher |
| Cache returns wrong user's data | Missing userId in cache key | Include `userId` in `unstable_cache` key |
| Wrong HTTP error code from Route Handler | Confused 401/403 | 401 = not signed in, 403 = no permission |
| `ClerkTokenSync` errors on server | Rendered in Server Component | Must be client-only (has `"use client"`) |

## Anti-Patterns

Do not:

- Call `useAuth().getToken()` manually in components that use Orval hooks — tokens are injected automatically via `ClerkTokenSync` + `baseFetch`
- Import `@clerk/nextjs` (client) in Server Components or `@clerk/nextjs/server` in Client Components
- Put `ClerkProvider` inside `QueryProvider` — Clerk must wrap Query so `ClerkTokenSync` can register before hooks fire
- Use `auth()` without `await` — it's async and returns a promise, not the auth object
- Hardcode API URLs with manual `fetch` + `getToken()` — use Orval-generated hooks instead
- Store Clerk tokens in localStorage or cookies — Clerk manages session tokens internally

## Environment Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `.env`, `turbo.json` | Client-side Clerk initialization |
| `CLERK_SECRET_KEY` | `.env` (server only) | Server-side auth verification |

## See Also

- `next-best-practices` — App Router patterns, RSC boundaries
- `security-review` — auth checklist, JWT handling, RBAC validation
- `fastapi-patterns` — backend `get_current_actor()` dependency for JWT verification
- `error-tracking-nextjs-sentry` — attaching userId to Sentry context

## Troubleshooting

**"Unauthorized" 401 from backend API on client-side requests**
1. Check `<ClerkTokenSync />` is mounted in the app's layout inside `<ClerkProvider>`
2. Verify `@clerk/nextjs` is in the app's `package.json` dependencies
3. Check browser DevTools Network tab — the request should have an `Authorization: Bearer ...` header
4. If header is missing, the `authTokenProvider` singleton wasn't registered — `ClerkTokenSync` may not have rendered yet (race condition on first load)

**`auth()` returns `undefined` userId in Server Component**
- Missing `await` — `auth()` is async. Use `const { userId } = await auth()`

**Orval hooks work but Server Actions get 401**
- Server Actions can't use the client-side token singleton. Use `const { getToken } = await auth()` and pass the token explicitly to `fetch` or the plain client.

**`ClerkTokenSync` throws "useAuth must be used within ClerkProvider"**
- `ClerkTokenSync` is rendered outside `<ClerkProvider>` in the component tree. Move it inside.

**Auth works locally but fails in Docker/CI**
- Check that `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` are set in the container environment. `NEXT_PUBLIC_` vars must be available at build time for client bundles.

## Docs

- [Clerk Next.js SDK Reference](https://clerk.com/docs/reference/nextjs/overview)
- [Clerk Middleware](https://clerk.com/docs/reference/nextjs/clerk-middleware)
- [Clerk Organizations](https://clerk.com/docs/organizations/overview)
