# Error Handling

## Error Boundary Files

### `error.tsx`

Catches errors in a route segment and its children. Must be a Client Component.

```tsx
// app/dashboard/error.tsx
'use client'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={reset}>Try again</button>
    </div>
  )
}
```

### `global-error.tsx`

Handles errors in the root layout. Must include `<html>` and `<body>` tags.

```tsx
// app/global-error.tsx
'use client'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html>
      <body>
        <h2>Something went wrong!</h2>
        <button onClick={reset}>Try again</button>
      </body>
    </html>
  )
}
```

## Navigation Functions — Critical Gotcha

**Never wrap `redirect()`, `notFound()`, `forbidden()`, or `unauthorized()` in try-catch blocks.** These functions throw special errors used internally for control flow. If caught, navigation breaks.

```tsx
// Bad: redirect() throw will be caught and swallowed
async function action() {
  try {
    await doSomething()
    redirect('/success')  // Throws internally!
  } catch (e) {
    // This catches the redirect error — navigation breaks
    console.error(e)
  }
}

// Good: redirect() outside try-catch
async function action() {
  try {
    await doSomething()
  } catch (e) {
    console.error(e)
    throw e
  }
  redirect('/success')  // Safe here
}

// Good: Use unstable_rethrow inside catch
import { unstable_rethrow } from 'next/navigation'

async function action() {
  try {
    await doSomething()
    redirect('/success')
  } catch (e) {
    unstable_rethrow(e)  // Re-throws Next.js navigation errors
    console.error(e)     // Only runs for real errors
  }
}
```

## Custom Error Pages

```
app/
├── not-found.tsx      # 404 - call notFound()
├── unauthorized.tsx   # 401 - call unauthorized()
├── forbidden.tsx      # 403 - call forbidden()
└── global-error.tsx   # Root layout errors
```

## Error Hierarchy

Errors bubble to the nearest `error.tsx`. If none matches, they reach `global-error.tsx`.
