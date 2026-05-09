---
name: next-upgrade
description: Upgrade Next.js to the latest version following official migration guides and codemods
origin: Ezra
author: Carlos Melgoza
---

# Upgrade Next.js

Patterns for upgrading Next.js across major versions — codemods, dependency updates, and the breaking changes most likely to bite you.

## When to Activate

- Upgrading Next.js to a new major version (14 → 15 → 16)
- Resolving build errors caused by deprecated Next.js APIs after a version bump
- Running codemods to automate breaking change migrations

## Upgrade Path

Always upgrade one major version at a time. Verify the build passes between each step.

```
13 → 14 → 15 → 16
```

Skipping versions means encountering compounded breaking changes with no clear signal of what caused each error.

## Run Codemods First

Codemods automate the mechanical parts of each migration. Run them before touching code manually — applying them after manual edits causes conflicts.

```bash
# Run all codemods for the target version
npx @next/codemod@latest upgrade

# Or run a specific transform
npx @next/codemod@latest <transform> .
```

Common transforms by version:

| Version | Transform | What It Does |
|---------|-----------|--------------|
| v15 | `next-async-request-api` | Adds `await` to `params`, `searchParams`, `cookies()`, `headers()` |
| v15 | `next-request-geo-ip` | Migrates `geo`/`ip` from `NextRequest` to `@vercel/functions` |
| v15 | `next-dynamic-access-named-export` | Transforms `next/dynamic` named export access |

## Update Dependencies

After codemods, update Next.js and React together — they must stay in sync.

```bash
npm install next@latest react@latest react-dom@latest
```

For TypeScript projects:

```bash
npm install @types/react@latest @types/react-dom@latest
```

## Breaking Changes by Version

### Next.js 15

**Async Request APIs** — `params`, `searchParams`, `cookies()`, and `headers()` are now async. The `next-async-request-api` codemod handles most of these, but review any file it couldn't patch automatically.

```tsx
// Before (v14)
export default function Page({ params }: { params: { slug: string } }) {
  return <h1>{params.slug}</h1>
}

// After (v15)
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  return <h1>{slug}</h1>
}
```

**React 19** — Next.js 15 ships with React 19 by default. Check for removed lifecycle methods (`componentWillMount`, etc.) and deprecated APIs in your dependencies.

**Caching defaults** — `fetch` requests are no longer cached by default. Explicit `cache: 'force-cache'` is needed for caching behavior that was automatic in v14.

```tsx
// v14: cached by default
fetch('/api/data')

// v15: opt in explicitly
fetch('/api/data', { cache: 'force-cache' })
// or use revalidate
fetch('/api/data', { next: { revalidate: 3600 } })
```

### Next.js 16

**`use cache` directive** — `experimental.ppr` is replaced by `cacheComponents: true`. Migrate `unstable_cache` to the `use cache` directive.

```ts
// next.config.ts — v16
const nextConfig: NextConfig = {
  cacheComponents: true,  // replaces experimental.ppr
}
```

See `next-cache-components` for full migration patterns from `unstable_cache` and `dynamic` exports.

## Verify the Upgrade

```bash
# Check for build errors
npm run build

# Check types
npx tsc --noEmit
```

Run the dev server and exercise the key paths in your app. Pay attention to:
- Pages that use `params` or `searchParams` (v15 async APIs)
- Components that read `cookies()` or `headers()` inside Server Components
- Any `fetch` calls that previously relied on default caching behavior (v15)
- `unstable_cache` usage (v16)

**Remember**: Always run codemods before making manual changes — codemods automate the majority of mechanical breaking changes and applying them after manual edits can cause conflicts. For multi-major-version jumps, go one version at a time and verify the build between each step.

## See Also

- `next-best-practices` — App Router patterns for the upgraded version
- `next-cache-components` — `use cache` directive patterns introduced in Next.js 16
