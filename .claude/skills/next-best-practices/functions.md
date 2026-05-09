# Functions

## Navigation Hooks (Client Components)

| Hook | Purpose |
|------|---------|
| `useRouter` | Programmatic navigation (`push`, `replace`, `back`, `refresh`) |
| `usePathname` | Get current URL path |
| `useSearchParams` | Read URL search params (requires Suspense) |
| `useParams` | Read dynamic route params |
| `useSelectedLayoutSegment` | Read active child segment |
| `useSelectedLayoutSegments` | Read all active segments |
| `Link` | Client-side navigation (use instead of `<a>`) |
| `useFormStatus` | Get form submission status |

```tsx
'use client'
import { useRouter, usePathname, useSearchParams, useParams } from 'next/navigation'

function NavComponent() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const params = useParams()

  return (
    <button onClick={() => router.push('/dashboard')}>
      Go to Dashboard
    </button>
  )
}
```

## Server Functions

| Function | Purpose |
|----------|---------|
| `cookies()` | Read/write cookies (async in v15+) |
| `headers()` | Read request headers (async in v15+) |
| `draftMode()` | Enable/disable draft mode |
| `after()` | Run code after response is sent |
| `redirect()` | Redirect to another URL |
| `notFound()` | Trigger 404 |

```tsx
import { cookies, headers } from 'next/headers'
import { after } from 'next/server'

export default async function Page() {
  const cookieStore = await cookies()
  const headersList = await headers()

  const token = cookieStore.get('token')?.value
  const ua = headersList.get('user-agent')

  after(() => {
    // Runs after response is sent — analytics, logging
    logPageView(token)
  })

  return <div>Hello</div>
}
```

## Generate Functions

| Function | Purpose |
|----------|---------|
| `generateStaticParams` | Pre-render dynamic routes at build time |
| `generateMetadata` | Dynamic page metadata |
| `generateViewport` | Dynamic viewport config |
| `generateImageMetadata` | Multiple OG images |
| `generateSitemaps` | Multiple sitemaps for large sites |

```tsx
// Pre-render /blog/[slug] for all posts
export async function generateStaticParams() {
  const posts = await getPosts()
  return posts.map(post => ({ slug: post.slug }))
}

export default async function BlogPost({ params }) {
  const { slug } = await params
  const post = await getPost(slug)
  return <article>{post.content}</article>
}
```

## Request/Response

| API | Purpose |
|-----|---------|
| `NextRequest` | Extended Request with Next.js helpers |
| `NextResponse` | Extended Response with Next.js helpers |
| `ImageResponse` | Generate OG images (from `next/og`) |

## Active Link Pattern

```tsx
'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

function NavLink({ href, children }) {
  const pathname = usePathname()
  const isActive = pathname === href

  return (
    <Link href={href} className={isActive ? 'font-bold' : ''}>
      {children}
    </Link>
  )
}
```
