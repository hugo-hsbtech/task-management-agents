# Middleware Strategies (HIGH)

> **Filename**: `middleware.ts` in `src/`. Next.js 16+ also supports `proxy.ts` — the code is identical, only the filename changes.

Each Ezra frontend app has its own middleware file. Choose the strategy that matches the app's auth model.

## Protected-First (deal-triage, internal tools)

Block everything except explicitly public routes. Use for apps where most pages require auth.

```typescript
// apps/<app>/src/middleware.ts
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/login(.*)",
  "/healthz",
]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublicRoute(req)) await auth.protect();
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
```

**Reference implementation**: `frontend/apps/deal-triage/src/middleware.ts`

## Public-First (marketing sites, landing pages)

Allow everything except explicitly protected routes. Use for apps where most pages are public.

```typescript
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isProtectedRoute = createRouteMatcher([
  "/dashboard(.*)",
  "/settings(.*)",
  "/api/private(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) await auth.protect();
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
```

## No Auth (public app)

Apps without Clerk don't need middleware. The `@ezra/app` main app currently has no auth.

## Session Tasks (Forced Actions)

When session tasks are enabled (forced password reset, MFA setup), users may have a `pending` session status:

```typescript
import { NextResponse } from "next/server";

export default clerkMiddleware(async (auth, req) => {
  const { sessionStatus } = await auth();

  if (sessionStatus === "pending") {
    return NextResponse.redirect(new URL("/sign-in/tasks", req.url));
  }

  if (!isPublicRoute(req)) await auth.protect();
});
```

> **Core 2**: `sessionStatus` unavailable. Session tasks do not exist in Core 2.

## Matcher Explanation

The default matcher excludes static files (images, fonts, etc.) but includes all page routes and API routes. The `/(api|trpc)(.*)` pattern ensures API Route Handlers are also processed by Clerk middleware.

If auth fails on API routes, check that `/(api|trpc)(.*)` is in the matcher.

## Docs

[Clerk Middleware](https://clerk.com/docs/reference/nextjs/clerk-middleware)
