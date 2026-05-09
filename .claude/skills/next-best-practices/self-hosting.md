# Self-Hosting

## Standalone Output for Docker

Use `output: 'standalone'` to create a minimal production build:

```js
// next.config.js
module.exports = {
  output: 'standalone',
}
```

This creates a `standalone` folder with only production dependencies — no need for `node_modules` in the container.

## Docker Example

```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM node:20-alpine AS runner
WORKDIR /app

# Run as non-root
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy standalone build
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER nextjs
EXPOSE 3000
ENV PORT=3000

CMD ["node", "server.js"]
```

## PM2 for Traditional Servers

```js
// ecosystem.config.js
module.exports = {
  apps: [{
    name: 'next-app',
    script: 'node_modules/.bin/next',
    args: 'start',
    instances: 'max',
    exec_mode: 'cluster',
    env: { NODE_ENV: 'production' },
  }],
}
```

## Multi-Instance ISR Cache

**ISR uses filesystem caching by default. This breaks with multiple instances** — each server has separate local storage.

### Redis Cache Handler

```ts
// cache-handler.ts
import { CacheHandler } from 'next/dist/server/lib/incremental-cache'
import Redis from 'ioredis'

const redis = new Redis(process.env.REDIS_URL!)

export default class RedisCache implements CacheHandler {
  async get(key: string) {
    const data = await redis.get(key)
    return data ? JSON.parse(data) : null
  }

  async set(key: string, data: any, ctx: { revalidate?: number }) {
    const ttl = ctx.revalidate ?? 3600
    await redis.setex(key, ttl, JSON.stringify(data))
  }

  async revalidateTag(tag: string) {
    // Implement tag invalidation
  }
}
```

```js
// next.config.js
module.exports = {
  cacheHandler: require.resolve('./cache-handler'),
  cacheMaxMemorySize: 0, // Disable in-memory cache
}
```

## Environment Variables

- **Build-time**: Use `NEXT_PUBLIC_` prefix for client-side variables, baked in at build
- **Runtime**: Read from `process.env` in Server Components/Route Handlers — no prefix needed

## Health Check Endpoint

```ts
// app/api/health/route.ts
export async function GET() {
  return Response.json({ status: 'ok', timestamp: new Date().toISOString() })
}
```

## What Works vs Needs Extra Setup

| Feature | Works Out of Box | Needs Config |
|---------|-----------------|--------------|
| Static assets | Yes | — |
| Server rendering | Yes | — |
| Image optimization | Yes | External: needs loader |
| ISR (single instance) | Yes | — |
| ISR (multi-instance) | No | Custom cache handler |
| Streaming | Yes | — |
