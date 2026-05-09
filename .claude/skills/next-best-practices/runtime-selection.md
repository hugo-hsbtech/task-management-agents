# Runtime Selection

## Default: Node.js Runtime

**Always start with Node.js runtime.** It provides full Node.js API support including file system access, database connections, and the complete npm ecosystem.

```tsx
// Default - no configuration needed
export default async function Page() {
  // Full Node.js available here
}
```

## Edge Runtime

Only use Edge runtime when you have a **concrete latency requirement** for geographic distribution.

```tsx
// Opt into Edge runtime explicitly
export const runtime = 'edge'

export default function Page() {
  // Limited to Web APIs only
}
```

## Decision Checklist

Before using Edge runtime, verify all three:
1. The project already uses Edge runtime elsewhere
2. There is a concrete, measured latency need
3. All dependencies are Edge-compatible (no native modules, no Node.js APIs)

**If unsure, use Node.js runtime.**

## Trade-offs

| | Node.js | Edge |
|-|---------|------|
| Full Node.js API | Yes | No |
| Native npm packages | Yes | Limited |
| Cold start | Slower | Faster |
| Geographic distribution | No | Yes |
| Database connections | Yes | Limited |

## When Edge Is Appropriate

- Middleware/proxy that needs geographic distribution (`proxy.ts` in v16)
- Simple request transformations with no database access
- A/B testing or redirects at the edge
- Auth token verification with JWT (no DB lookup)
