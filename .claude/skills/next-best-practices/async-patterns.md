# Async Patterns

Next.js 15+ async API changes.

## Key Rules

In Next.js 15+, `params`, `searchParams`, `cookies()`, and `headers()` are asynchronous.

### Pages and Layouts

Always type params as `Promise<...>` and await them:

```tsx
// app/blog/[slug]/page.tsx
type Props = {
  params: Promise<{ slug: string }>
  searchParams: Promise<{ q?: string }>
}

export default async function Page({ params, searchParams }: Props) {
  const { slug } = await params
  const { q } = await searchParams
  return <div>{slug}</div>
}
```

### Route Handlers

```tsx
// app/api/posts/[id]/route.ts
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return Response.json({ id })
}
```

### Non-Async Components

Use React's `use()` hook to unwrap without making component async:

```tsx
'use client'
import { use } from 'react'

export function ClientPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params)
  return <div>{slug}</div>
}
```

### generateMetadata

```tsx
export async function generateMetadata({ params }: Props) {
  const { slug } = await params
  return { title: slug }
}
```

### Cookies and Headers

```tsx
import { cookies, headers } from 'next/headers'

export default async function Page() {
  const cookieStore = await cookies()
  const headersList = await headers()

  const token = cookieStore.get('token')?.value
  const ua = headersList.get('user-agent')
}
```

## Migration

Run the codemod to auto-update your codebase:

```bash
npx @next/codemod@latest next-async-request-api .
```
