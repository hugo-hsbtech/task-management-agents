---
name: next-best-practices
description: Next.js best practices - file conventions, RSC boundaries, data patterns, async APIs, metadata, error handling, route handlers, image/font optimization, bundling
origin: Ezra
author: Carlos Melgoza
---

# Next.js Best Practices

Opinionated patterns for the Next.js App Router. Apply when writing or reviewing Next.js code.

## When to Activate

- Writing or reviewing Next.js App Router code — file conventions, layouts, route segments
- Choosing between Server Components, Server Actions, and Route Handlers
- Setting up error boundaries, metadata, or image and font optimization
- Debugging hydration errors, Suspense issues, or unexpected rendering behavior
- Configuring self-hosted deployment or analyzing bundle size

## RSC Boundaries

The single most common source of bugs in App Router code.

Push `'use client'` to the leaves. Every component is a Server Component by default — keep it that way until you actually need client-side interactivity.

```tsx
// Bad: marking a layout or page as client just to use one hook
'use client'

export default function DashboardPage() {
  const [open, setOpen] = useState(false)
  const data = await db.reports.findMany()  // can't do this in a client component anyway
  return <Dashboard data={data} open={open} />
}
```

```tsx
// Good: Server Component fetches data, client component handles state
export default async function DashboardPage() {
  const data = await db.reports.findMany()
  return <Dashboard data={data} />
}

// dashboard.tsx
'use client'
export function Dashboard({ data }: { data: Report[] }) {
  const [open, setOpen] = useState(false)
  return <>{/* ... */}</>
}
```

Non-serializable values (functions, class instances, Dates) cannot cross the Server→Client boundary as props. See [rsc-boundaries.md](./rsc-boundaries.md) for full detection rules.

## Async APIs

Next.js 15+ made `params`, `searchParams`, `cookies()`, and `headers()` async. Access them with `await`.

```tsx
// Bad: synchronous access (Next.js 14 style — throws in 15+)
export default function Page({ params }: { params: { slug: string } }) {
  return <h1>{params.slug}</h1>
}
```

```tsx
// Good: await params
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  return <h1>{slug}</h1>
}

// Good: await cookies/headers
import { cookies } from 'next/headers'

export default async function Page() {
  const cookieStore = await cookies()
  const token = cookieStore.get('token')
  return <>{/* ... */}</>
}
```

Run the codemod to migrate automatically: `npx @next/codemod@latest next-async-request-api .`

See [async-patterns.md](./async-patterns.md) for the full list of affected APIs.

## Data Patterns

Three ways to load data — choose based on who needs it and when.

| Pattern | Use for |
|---|---|
| Server Component `async/await` | Page-level data, data that never needs client refresh |
| Server Action | Mutations, form submissions, write operations |
| Route Handler | Webhooks, external API callbacks, non-React consumers |

Avoid waterfalls. Fetch independent data in parallel.

```tsx
// Bad: sequential fetches — total time = A + B + C
const user = await getUser(id)
const posts = await getPosts(id)
const followers = await getFollowers(id)
```

```tsx
// Good: parallel — total time = max(A, B, C)
const [user, posts, followers] = await Promise.all([
  getUser(id),
  getPosts(id),
  getFollowers(id),
])
```

For deep component trees where a child needs data the parent already fetched, use the `preload` pattern instead of prop-drilling. See [data-patterns.md](./data-patterns.md).

## Directives

```
'use client'   — React directive. Marks client component boundary. Push to leaves.
'use server'   — React directive. Marks Server Actions. Use inside functions, not files.
'use cache'    — Next.js directive. Caches the component/function result. Requires Next.js 16+.
```

Never put `'use server'` at the file level unless every export in that file is a Server Action. See [directives.md](./directives.md).

## Error Handling

| File | Handles |
|---|---|
| `error.tsx` | Runtime errors in a route segment and its children |
| `global-error.tsx` | Errors in the root layout — replaces the entire page |
| `not-found.tsx` | `notFound()` throws and 404 responses |

`error.tsx` must be a Client Component (`'use client'`). It receives `error` and `reset` props.

```tsx
// app/dashboard/error.tsx
'use client'

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div>
      <p>Something went wrong in the dashboard.</p>
      <button onClick={reset}>Try again</button>
    </div>
  )
}
```

Use `unstable_rethrow` inside catch blocks to avoid swallowing Next.js internal errors (`redirect`, `notFound`). See [error-handling.md](./error-handling.md).

## Image Optimization

Never use `<img>`. Always use `next/image`.

```tsx
// Bad
<img src="/hero.jpg" alt="Hero" />

// Good
import Image from 'next/image'
<Image src="/hero.jpg" alt="Hero" width={1200} height={630} priority />
```

Set `priority` on the LCP image. Set `sizes` on any image that changes size across breakpoints. See [image.md](./image.md).

## Font Optimization

Never load fonts with `<link>` tags or `@import`. Use `next/font`.

```tsx
// Bad
// <link rel="preconnect" href="https://fonts.googleapis.com"> in layout

// Good
import { Inter } from 'next/font/google'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.className}>
      <body>{children}</body>
    </html>
  )
}
```

See [font.md](./font.md) for local fonts and Tailwind integration.

## Route Handlers

Route Handlers live in `app/api/**/route.ts`. They do not have access to React DOM.

A `route.ts` file in the same segment as a `page.tsx` conflicts with GET requests — the page wins. Put API routes in a dedicated path.

```
# Bad: conflicts with the page
app/dashboard/route.ts
app/dashboard/page.tsx

# Good: separate path
app/api/dashboard/route.ts
app/dashboard/page.tsx
```

Prefer Server Actions over Route Handlers for mutations triggered by the UI — Server Actions colocate with the component and skip the manual `fetch` call. See [route-handlers.md](./route-handlers.md) for when Route Handlers are the right choice.

## Runtime Selection

Default to the Node.js runtime. Opt into Edge only when you need global low-latency and can accept the constraints.

```ts
// Only add this when you have a specific reason
export const runtime = 'edge'
```

Edge runtime does not support: Node.js built-ins, most npm packages, file system access, or `next/image` optimization. See [runtime-selection.md](./runtime-selection.md).

## Suspense Boundaries

`useSearchParams()` and `usePathname()` cause a CSR bailout for the entire page if not wrapped in `<Suspense>`.

```tsx
// Bad: no Suspense — the whole page falls back to client rendering
export default function Page() {
  return <SearchResults />
}

function SearchResults() {
  const params = useSearchParams()  // CSR bailout here
  return <>{/* ... */}</>
}
```

```tsx
// Good: isolate the client hook behind Suspense
export default function Page() {
  return (
    <Suspense fallback={<ResultsSkeleton />}>
      <SearchResults />
    </Suspense>
  )
}
```

See [suspense-boundaries.md](./suspense-boundaries.md) for the full list of hooks that require Suspense.

## Self-Hosting

```ts
// next.config.ts
const nextConfig: NextConfig = {
  output: 'standalone',  // required for Docker — copies only production files
}
```

Multi-instance deployments need a shared cache handler for ISR to work correctly across pods. See [self-hosting.md](./self-hosting.md).

## Additional Reference

- [file-conventions.md](./file-conventions.md) — project structure, route segments, parallel and intercepting routes
- [functions.md](./functions.md) — navigation hooks, server functions, generate functions
- [metadata.md](./metadata.md) — static metadata, `generateMetadata`, OG images
- [bundling.md](./bundling.md) — server-incompatible packages, ESM/CJS issues, bundle analysis
- [scripts.md](./scripts.md) — `next/script` loading strategies
- [hydration-error.md](./hydration-error.md) — common causes and fixes
- [parallel-routes.md](./parallel-routes.md) — modal patterns with slots and interceptors
- [debug-tricks.md](./debug-tricks.md) — MCP endpoint, `--debug-build-paths`

**Remember**: App Router and Pages Router have different file conventions, data fetching models, and error handling approaches. Always verify which router the project uses before applying these patterns — they are for App Router only.

## See Also

- `next-cache-components` — PPR and `use cache` directive patterns
- `next-upgrade` — upgrading to a new major Next.js version
- `typescript-practices` — TypeScript patterns for Next.js code
