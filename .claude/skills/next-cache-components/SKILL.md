---
name: next-cache-components
description: Next.js 16 Cache Components - PPR, use cache directive, cacheLife, cacheTag, updateTag
origin: Ezra
author: Carlos Melgoza
---

# Cache Components (Next.js 16+)

Cache Components enable Partial Prerendering (PPR) - mix static, cached, and dynamic content in a single route.

## When to Activate

- Adding `use cache` to components, functions, or pages in a Next.js 16+ project
- Setting up Partial Prerendering to mix static, cached, and dynamic content in a single route
- Migrating from `unstable_cache`, page-level `revalidate` exports, or `dynamic` config constants
- Tagging cached content for on-demand invalidation with `cacheTag` and `updateTag`
- Debugging stale data or unexpected cache behavior after a mutation

## Enable Cache Components

```ts
// next.config.ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  cacheComponents: true,
}

export default nextConfig
```

This replaces the old `experimental.ppr` flag.

## Three Content Types

With Cache Components enabled, content falls into three categories:

### Static (Auto-Prerendered)

Synchronous code, imports, pure computations - prerendered at build time:

```tsx
export default function Page() {
  return (
    <header>
      <h1>Our Blog</h1>  {/* Static - instant */}
      <nav>...</nav>
    </header>
  )
}
```

### Cached (`use cache`)

Async data that doesn't need fresh fetches every request:

```tsx
async function BlogPosts() {
  'use cache'
  cacheLife('hours')

  const posts = await db.posts.findMany()
  return <PostList posts={posts} />
}
```

### Dynamic (Suspense)

Runtime data that must be fresh - wrap in Suspense:

```tsx
import { Suspense } from 'react'

export default function Page() {
  return (
    <>
      <BlogPosts />  {/* Cached */}

      <Suspense fallback={<p>Loading...</p>}>
        <UserPreferences />  {/* Dynamic - streams in */}
      </Suspense>
    </>
  )
}

async function UserPreferences() {
  const theme = (await cookies()).get('theme')?.value
  return <p>Theme: {theme}</p>
}
```

## `use cache` Directive

### File Level

```tsx
'use cache'

export default async function Page() {
  // Entire page is cached
  const data = await fetchData()
  return <div>{data}</div>
}
```

### Component Level

```tsx
export async function CachedComponent() {
  'use cache'
  const data = await fetchData()
  return <div>{data}</div>
}
```

### Function Level

```tsx
export async function getData() {
  'use cache'
  return db.query('SELECT * FROM posts')
}
```

## Cache Profiles

### Built-in Profiles

```tsx
'use cache'                    // Default: 5m stale, 15m revalidate
```

```tsx
'use cache: remote'           // Platform-provided cache (Redis, KV)
```

```tsx
'use cache: private'          // For compliance, allows runtime APIs
```

### `cacheLife()` - Custom Lifetime

```tsx
import { cacheLife } from 'next/cache'

async function getData() {
  'use cache'
  cacheLife('hours')  // Built-in profile
  return fetch('/api/data')
}
```

Built-in profiles: `'default'`, `'minutes'`, `'hours'`, `'days'`, `'weeks'`, `'max'`

### Inline Configuration

```tsx
async function getData() {
  'use cache'
  cacheLife({
    stale: 3600,      // 1 hour - serve stale while revalidating
    revalidate: 7200, // 2 hours - background revalidation interval
    expire: 86400,    // 1 day - hard expiration
  })
  return fetch('/api/data')
}
```

## Cache Invalidation

### `cacheTag()` - Tag Cached Content

```tsx
import { cacheTag } from 'next/cache'

async function getProducts() {
  'use cache'
  cacheTag('products')
  return db.products.findMany()
}

async function getProduct(id: string) {
  'use cache'
  cacheTag('products', `product-${id}`)
  return db.products.findUnique({ where: { id } })
}
```

### `updateTag()` - Immediate Invalidation

Use when you need the cache refreshed within the same request:

```tsx
'use server'

import { updateTag } from 'next/cache'

export async function updateProduct(id: string, data: FormData) {
  await db.products.update({ where: { id }, data })
  updateTag(`product-${id}`)  // Immediate - same request sees fresh data
}
```

### `revalidateTag()` - Background Revalidation

Use for stale-while-revalidate behavior:

```tsx
'use server'

import { revalidateTag } from 'next/cache'

export async function createPost(data: FormData) {
  await db.posts.create({ data })
  revalidateTag('posts')  // Background - next request sees fresh data
}
```

## Runtime Data Constraint

**Cannot** access `cookies()`, `headers()`, or `searchParams` inside `use cache`.

Pass runtime data as arguments instead — they automatically become part of the cache key:

```tsx
// Bad: runtime API inside use cache
async function CachedProfile() {
  'use cache'
  const session = (await cookies()).get('session')?.value  // Error!
  return <div>{session}</div>
}

// Good: extract outside, pass as argument
async function ProfilePage() {
  const session = (await cookies()).get('session')?.value
  return <CachedProfile sessionId={session} />
}

async function CachedProfile({ sessionId }: { sessionId: string }) {
  'use cache'
  // sessionId becomes part of cache key automatically
  const data = await fetchUserData(sessionId)
  return <div>{data.name}</div>
}
```

Exception: `'use cache: private'` allows runtime APIs for compliance requirements when you can't refactor.

## Cache Key Generation

Cache keys are automatic based on:
- **Build ID** - invalidates all caches on deploy
- **Function ID** - hash of function location
- **Serializable arguments** - props become part of key
- **Closure variables** - outer scope values included

## Complete Example

```tsx
import { Suspense } from 'react'
import { cookies } from 'next/headers'
import { cacheLife, cacheTag } from 'next/cache'

export default function DashboardPage() {
  return (
    <>
      {/* Static shell - instant from CDN */}
      <header><h1>Dashboard</h1></header>
      <nav>...</nav>

      {/* Cached - fast, revalidates hourly */}
      <Stats />

      {/* Dynamic - streams in with fresh data */}
      <Suspense fallback={<NotificationsSkeleton />}>
        <Notifications />
      </Suspense>
    </>
  )
}

async function Stats() {
  'use cache'
  cacheLife('hours')
  cacheTag('dashboard-stats')

  const stats = await db.stats.aggregate()
  return <StatsDisplay stats={stats} />
}

async function Notifications() {
  const userId = (await cookies()).get('userId')?.value
  const notifications = await db.notifications.findMany({
    where: { userId, read: false }
  })
  return <NotificationList items={notifications} />
}
```

## Migration from Previous Versions

| Old Config | Replacement |
|-----------|-------------|
| `experimental.ppr` | `cacheComponents: true` |
| `dynamic = 'force-dynamic'` | Remove (default behavior) |
| `dynamic = 'force-static'` | `'use cache'` + `cacheLife('max')` |
| `revalidate = N` | `cacheLife({ revalidate: N })` |
| `unstable_cache()` | `'use cache'` directive |

### Migrating `unstable_cache` to `use cache`

**Before (`unstable_cache`):**

```tsx
import { unstable_cache } from 'next/cache'

const getCachedUser = unstable_cache(
  async (id) => getUser(id),
  ['my-app-user'],
  {
    tags: ['users'],
    revalidate: 60,
  }
)
```

**After (`use cache`):**

```tsx
import { cacheLife, cacheTag } from 'next/cache'

async function getCachedUser(id: string) {
  'use cache'
  cacheTag('users')
  cacheLife({ revalidate: 60 })
  return getUser(id)
}
```

Key differences:
- **No manual cache keys** - generated automatically from function arguments and closures
- **Tags** - replace `options.tags` with `cacheTag()` calls inside the function
- **Revalidation** - replace `options.revalidate` with `cacheLife({ revalidate: N })`

## Limitations

- **Edge runtime not supported** - requires Node.js
- **Static export not supported** - needs server
- **Non-deterministic values** (`Math.random()`, `Date.now()`) execute once at build time inside `use cache`

For request-time randomness outside cache:

```tsx
import { connection } from 'next/server'

async function DynamicContent() {
  await connection()  // Defer to request time
  const id = crypto.randomUUID()  // Different per request
  return <div>{id}</div>
}
```

**Remember**: `use cache` requires `cacheComponents: true` in `next.config.ts` and the Node.js runtime — it is not compatible with the Edge runtime or static export mode. Always pass runtime data (`cookies`, `headers`, `searchParams`) as arguments to cached functions rather than reading them inside `use cache`.

## See Also

- `next-best-practices` — general Next.js App Router patterns
