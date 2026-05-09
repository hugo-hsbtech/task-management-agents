---
name: error-tracking-nextjs-sentry
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Sentry SDK internals for the @ezra/observability Next.js Sentry adapter — Sentry.init configuration across client/server/edge runtimes, withSentryConfig, session replay setup, beforeSend filters, and adapter-level tests. ADAPTER AUTHORS ONLY. App code must use `import { getObservability } from '@ezra/observability'` (frontend skill TBD; backend mirror is ezra-add-monitoring).
author: Carlos Melgoza
---

# Error Tracking — Next.js + Sentry (Adapter Reference)

> **Scope:** This skill documents Sentry SDK specifics for whoever maintains the frontend `@ezra/observability` Sentry adapter. Application code — pages, components, Server Actions, Route Handlers — must not import `@sentry/nextjs` directly. The frontend mirror of the backend abstraction (`ezra_observability`) is planned in a follow-up to `docs/proposals/sentry-error-tracking-introduction.md`; the same architectural rule applies.
>
> **If you're a feature developer adding error tracking to a page, component, or Server Action, wait for the frontend mirror skill or use the same patterns as `ezra-add-monitoring` adapted to TypeScript.**
>
> **Why we have an abstraction:** see `docs/proposals/sentry-error-tracking-introduction.md`. Short version: Sentry is the default error tracker today, behind a port so we can swap it later without touching feature code. The patterns below are how the Next.js Sentry adapter implements that port.

Sentry implementation patterns for Next.js App Router. Covers server-side error capture, client-side session replay, and the configuration differences between the Node.js and Edge runtimes.

## When to Activate

- Modifying the frontend `SentryObservability` adapter (when it lands)
- Updating `Sentry.init` integration list, sampling, or replay configuration across `sentry.{client,server,edge}.config.ts`
- Debugging why an event isn't shipping (or why an unexpected one is)
- Adding a new `beforeSend` rule to drop a known-noise event class
- Reviewing an adapter PR for PII safety in session replay

## SDK Files

`@sentry/nextjs` requires three SDK init files — one per runtime:

```
sentry.client.config.ts   — browser (React, session replay)
sentry.server.config.ts   — Node.js server (SSR, Route Handlers)
sentry.edge.config.ts     — Edge runtime (Middleware)
```

Each file is loaded automatically by the Sentry webpack plugin via `next.config.ts`. Do not import them manually.

All three configs ship with **`tracesSampleRate: 0`** at launch (errors-only, mirroring the backend posture in `docs/proposals/sentry-error-tracking-introduction.md`). When/if we adopt tracing, this becomes one env-var flip per runtime, not a code change.

### Client Config

```ts
// sentry.client.config.ts
import * as Sentry from '@sentry/nextjs'

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_ENV,
  release: process.env.NEXT_PUBLIC_RELEASE,

  // Errors-only at launch. See proposal section "Out of scope (explicit non-goals)".
  tracesSampleRate: 0,

  // Session replay still runs — it's a separate sampler, not gated on tracesSampleRate.
  // 10% of sessions, 100% of sessions with errors.
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,

  integrations: [
    Sentry.replayIntegration({
      // Mask all text content and inputs by default
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
})
```

### Server Config

```ts
// sentry.server.config.ts
import * as Sentry from '@sentry/nextjs'

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.ENV,
  release: process.env.RELEASE,
  tracesSampleRate: 0,   // errors-only at launch
})
```

### Edge Config

```ts
// sentry.edge.config.ts
import * as Sentry from '@sentry/nextjs'

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.ENV,
  tracesSampleRate: 0,   // errors-only at launch
  // Note: session replay and most integrations are not available in Edge
})
```

## next.config.ts

Wrap your config with `withSentryConfig` to inject the build-time plugin:

```ts
// next.config.ts
import { withSentryConfig } from '@sentry/nextjs'
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // your config
}

export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,

  // Upload source maps silently — don't print to console
  silent: !process.env.CI,

  // Automatically tree-shake Sentry logger statements in production
  disableLogger: true,
})
```

## What `@sentry/nextjs` captures automatically

These behaviors are inherent to the SDK once `Sentry.init` runs in each runtime config file. They are **not** adapter-side code, and the future `@ezra/observability` adapter relies on them:

- **Server Components**: errors thrown in RSC render are captured by `withSentryConfig`'s instrumentation hook before `error.tsx` renders the fallback. The adapter does not need to wrap RSC render functions.
- **Server Actions**: when wrapped with `Sentry.withServerActionInstrumentation`, uncaught exceptions are captured and the action is wrapped in a transaction. (Today, with `tracesSampleRate: 0`, only the capture path is exercised.) The wrapper is a Sentry SDK API; whether the *port* exposes an equivalent helper is an open API-design question for the frontend mirror — see `docs/proposals/sentry-error-tracking-introduction.md`.
- **Route Handlers**: same instrumentation as Server Actions.
- **Client Components**: unhandled errors and unhandled promise rejections in the browser are captured automatically once `sentry.client.config.ts` runs.

What is **not** captured automatically (and so the port must expose a path for it):

- Errors caught and not re-thrown (the SDK sees them as resolved)
- Errors in `setTimeout` / `setInterval` callbacks not surfaced through the React tree
- Errors in workers (`Worker`, `SharedWorker`) — separate `Sentry.init` required if needed

The frontend `@ezra/observability` adapter wraps these capture surfaces under a port (`captureException`, `captureMessage`, `setUser`, `setTag`, `setContext`, `addBreadcrumb`, `isolatedScope`, `flush`) so app code never imports `@sentry/nextjs` directly. The TypeScript signatures mirror the Python port.

## User Context

The adapter is the *only* place that calls `Sentry.setUser`. App code calls `getObservability().setUser(userId)`. The adapter implementation looks like:

```ts
// adapters/sentry.ts (frontend Sentry adapter — only file that imports @sentry/nextjs)
import * as Sentry from '@sentry/nextjs'

setUser(userId: string | null, opts?: { username?: string; extras?: Record<string, unknown> }) {
  // Note: port does NOT accept email — see ezra-add-monitoring (or its frontend mirror) for PII rules.
  if (userId === null) {
    Sentry.setUser(null)
    return
  }
  Sentry.setUser({ id: userId, username: opts?.username, ...(opts?.extras ?? {}) })
}
```

Same rule as backend: the port deliberately does not accept `email`. App code that wants to identify a user passes `userId` only.

## Before-Send Filtering

```ts
// sentry.client.config.ts
Sentry.init({
  // ...
  beforeSend(event, hint) {
    const error = hint.originalException

    // Drop browser extension noise
    if (
      event.exception?.values?.[0]?.stacktrace?.frames?.some(
        f => f.filename?.includes('chrome-extension')
      )
    ) {
      return null
    }

    // Drop canceled network requests
    if (error instanceof DOMException && error.name === 'AbortError') {
      return null
    }

    // Scrub sensitive fields from request data
    if (event.request?.data) {
      const data = event.request.data as Record<string, unknown>
      for (const key of ['password', 'token', 'authorization', 'card_number']) {
        if (key in data) data[key] = '[Filtered]'
      }
    }

    return event
  },
})
```

## Session Replay

Session replay records user interactions so you can reproduce bugs exactly as the user experienced them.

Configuration is in `sentry.client.config.ts` (see above). The default `maskAllText: true` + `blockAllMedia: true` gives safe defaults — user inputs and media are masked before any data leaves the browser.

Selective unmasking for non-sensitive areas:

```html
<!-- Unmask specific elements that are safe to record -->
<div data-sentry-unmask>Dashboard title</div>

<!-- Block specific elements from appearing in replay -->
<div data-sentry-block>Billing summary</div>
```

Session replay is not available in the Edge runtime.

## Performance Tracing — out of scope today

Sentry SDK exposes `Sentry.startSpan` and friends, but the launch scope is **errors only** (`tracesSampleRate: 0`). The frontend port does not expose `span()` / `transaction()` until tracing is added in a follow-up. If a future debug session needs a one-off span, an adapter author may extend the port — but adding `Sentry.startSpan` calls in app code is forbidden by the same rule that forbids `import * as Sentry from '@sentry/nextjs'` in features.

## Environment Variables

```bash
# Public (browser)
NEXT_PUBLIC_SENTRY_DSN=https://...@sentry.io/...
NEXT_PUBLIC_ENV=production
NEXT_PUBLIC_RELEASE=git-sha-or-semver

# Server only
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ORG=your-org-slug
SENTRY_PROJECT=your-project-slug
SENTRY_AUTH_TOKEN=sntrys_...    # for source map uploads in CI

ENV=production
RELEASE=git-sha-or-semver
```

**Acceptance gate before turning Sentry on in production:** trigger a deliberate error in staging across each runtime (RSC, Server Action, Route Handler, Client Component) and visually confirm the resulting events contain zero of: raw email, JWT, bearer token, API key, request body, free-text user content. Session replay's `maskAllText: true` + `blockAllMedia: true` is the second line of defense, but it is not infallible against custom DOM. Session replay runs only in the browser; Edge runtime supports error capture only.

## See Also

- `error-tracking` — tool-agnostic principles: boundaries, severity, alerting hygiene.
- `error-tracking-fastapi-sentry` — adapter-internals reference for the backend Sentry adapter.
- `docs/proposals/sentry-error-tracking-introduction.md` — backend rationale; frontend mirror to follow.
- `next-best-practices` — App Router patterns including `error.tsx` and `global-error.tsx` (where the integration's auto-capture hooks).
