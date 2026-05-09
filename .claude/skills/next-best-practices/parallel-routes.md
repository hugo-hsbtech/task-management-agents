# Parallel & Intercepting Routes

Use parallel routes for rendering multiple pages simultaneously and intercepting routes for modal patterns.

## Modal Pattern

```
app/
├── feed/
│   └── page.tsx
├── @modal/
│   ├── default.tsx          # Required fallback
│   └── (.)photo/[id]/
│       └── page.tsx         # Modal view
├── photo/[id]/
│   └── page.tsx             # Full page view
└── layout.tsx               # Receives { modal } slot
```

### Layout Setup

```tsx
// app/layout.tsx
export default function Layout({
  children,
  modal,
}: {
  children: React.ReactNode
  modal: React.ReactNode
}) {
  return (
    <>
      {children}
      {modal}
    </>
  )
}
```

### Required: `default.tsx`

**Every parallel route slot MUST have a `default.tsx`** to prevent 404s on hard navigation (refresh, direct URL access, sharing).

```tsx
// app/@modal/default.tsx
export default function Default() {
  return null  // Render nothing when no modal is active
}
```

### Modal Closing

**Always use `router.back()` to close modals.** Never use `push` or `Link` — they add a history entry and don't properly clear the intercepted route.

```tsx
// app/@modal/(.)photo/[id]/page.tsx
'use client'
import { useRouter } from 'next/navigation'

export default function PhotoModal({ params }) {
  const router = useRouter()

  return (
    <div className="modal-overlay" onClick={() => router.back()}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <button onClick={() => router.back()}>Close</button>
        {/* modal content */}
      </div>
    </div>
  )
}
```

## Route Matching

The matcher system operates on route **segments**, not filesystem paths:

| Convention | Meaning |
|-----------|---------|
| `(.)` | Same level segment |
| `(..)` | One level up segment |
| `(..)(..)` | Two levels up |
| `(...)` | From root |

Common misconception: `(..)` means "parent folder" — it actually means "parent route segment."

## Navigation Behavior

- **Soft navigation** (in-app link click): intercepting route shows modal
- **Hard navigation** (URL bar, refresh, shared link): full page renders instead of modal

This is the desired behavior — users bookmarking a photo URL see the full photo page, not the feed with a modal.

## TypeScript

In Next.js 15+, params in intercepted routes are async:

```tsx
export default async function PhotoModal({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const photo = await getPhoto(id)
  // ...
}
```
