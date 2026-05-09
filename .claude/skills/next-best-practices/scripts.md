# Scripts

## Always Use next/script

Use `next/script` instead of native `<script>` tags for proper optimization and loading management.

```tsx
// Bad: Native script tag
<script src="https://example.com/script.js" />

// Good: next/script
import Script from 'next/script'

export default function Page() {
  return (
    <Script
      src="https://example.com/script.js"
      strategy="afterInteractive"
    />
  )
}
```

## Inline Scripts Need an `id`

When using `dangerouslySetInnerHTML` or children, the `id` attribute is required for Next.js to track the script lifecycle:

```tsx
// Bad: Missing id
<Script dangerouslySetInnerHTML={{ __html: `console.log('hello')` }} />

// Good: With id
<Script id="my-script" dangerouslySetInnerHTML={{ __html: `console.log('hello')` }} />

// Good: Children syntax also needs id
<Script id="my-script-2">
  {`console.log('hello')`}
</Script>
```

## Loading Strategies

| Strategy | When | Use For |
|----------|------|---------|
| `afterInteractive` (default) | After page interactive | Analytics, chat widgets |
| `lazyOnload` | Browser idle time | Low-priority scripts |
| `beforeInteractive` | Before page interactive | Critical scripts (root layout only) |
| `worker` | Web worker (experimental) | Offload heavy scripts |

```tsx
// Analytics - default strategy
<Script src="https://analytics.com/script.js" strategy="afterInteractive" />

// Non-critical, defer as much as possible
<Script src="https://widget.com/chat.js" strategy="lazyOnload" />

// Critical - must be in root layout
// app/layout.tsx only
<Script src="https://critical.com/polyfill.js" strategy="beforeInteractive" />
```

## Google Analytics with @next/third-parties

Don't implement GA manually — use the optimized component:

```tsx
import { GoogleAnalytics } from '@next/third-parties/google'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>{children}</body>
      <GoogleAnalytics gaId="G-XXXXXXXXXX" />
    </html>
  )
}
```

Also available: `GoogleTagManager`, `YouTubeEmbed`, `GoogleMapsEmbed`.

## Placement

`next/script` goes at the **page level**, not inside `next/head`. It handles its own DOM positioning.

```tsx
// Bad: Inside Head
import Head from 'next/head'
<Head>
  <Script src="..." />  {/* Wrong */}
</Head>

// Good: At page or layout level
export default function Page() {
  return (
    <>
      <main>...</main>
      <Script src="..." strategy="afterInteractive" />
    </>
  )
}
```
