# Route Handlers

## Basics

Create `route.ts` files to define API endpoints. Supports GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS.

```tsx
// app/api/posts/route.ts
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const posts = await db.post.findMany()
  return NextResponse.json(posts)
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const post = await db.post.create({ data: body })
  return NextResponse.json(post, { status: 201 })
}
```

## Dynamic Routes

```tsx
// app/api/posts/[id]/route.ts
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const post = await db.post.findUnique({ where: { id } })
  if (!post) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  return NextResponse.json(post)
}
```

## GET Handler Conflict

**A `route.ts` and `page.tsx` cannot coexist in the same folder.** Put API routes in a subdirectory:

```
app/
├── posts/
│   ├── page.tsx          # /posts UI
│   └── api/
│       └── route.ts      # /posts/api endpoint
```

Or use the conventional `/api` prefix:

```
app/
├── posts/
│   └── page.tsx          # /posts UI
└── api/
    └── posts/
        └── route.ts      # /api/posts endpoint
```

## Environment Behavior

Route Handlers run on the server like Server Components. They can:
- Access databases directly
- Read environment variables
- Use Node.js APIs

They **cannot** use:
- React hooks
- React DOM APIs
- `useState`, `useEffect`, etc.

## Reading Request Data

```tsx
export async function GET(request: NextRequest) {
  // URL search params
  const searchParams = request.nextUrl.searchParams
  const query = searchParams.get('q')

  // Headers
  const authHeader = request.headers.get('authorization')

  // Cookies
  const cookieStore = await cookies()
  const token = cookieStore.get('token')?.value

  return NextResponse.json({ query, token })
}
```

## When to Use Route Handlers vs Server Actions

| Scenario | Use |
|----------|-----|
| External API (mobile, third parties) | Route Handler |
| Webhooks from external services | Route Handler |
| GET endpoints with HTTP caching | Route Handler |
| Form submissions from your UI | Server Action |
| Mutations triggered by buttons | Server Action |
| Internal data fetching in pages | Server Component (no API) |
