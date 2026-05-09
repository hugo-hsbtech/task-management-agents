# Bundling

## Server-Incompatible Packages

### Problem: Browser APIs in Server Components

Errors like `window is not defined` or `Can't resolve 'fs'` indicate server/browser incompatibility.

### Solution 1: Dynamic Import with `ssr: false`

For client-only libraries (Recharts, React Quill, etc.):

```tsx
import dynamic from 'next/dynamic'

const Chart = dynamic(() => import('./Chart'), { ssr: false })
```

### Solution 2: Externalize Packages

For packages with native bindings (Sharp, Bcrypt) or circular deps:

```js
// next.config.js
module.exports = {
  serverExternalPackages: ['sharp', 'bcrypt'],
}
```

### Solution 3: Client Component Wrapper

Isolate the problematic import in a `'use client'` file.

## CSS Imports

Always import CSS via JS imports, never `<link>` tags in components:

```tsx
// Good
import './styles.css'

// Bad - don't use <link> tags for CSS in Next.js
```

## Polyfills

Next.js includes common polyfills automatically. Don't add `core-js` or polyfill services — they're redundant.

## ESM/CommonJS Issues

If you get ESM/CJS conflicts, use `transpilePackages`:

```js
// next.config.js
module.exports = {
  transpilePackages: ['some-esm-package'],
}
```

## Bundle Analysis

Next.js 16.1+ includes a built-in bundle analyzer:

```bash
ANALYZE=true next build
```

Or install `@next/bundle-analyzer` for older versions.

## Turbopack Migration

Turbopack is the default bundler. Custom webpack configs need migration:

```js
// next.config.js - Turbopack config
module.exports = {
  turbopack: {
    rules: {
      '*.svg': {
        loaders: ['@svgr/webpack'],
        as: '*.js',
      },
    },
  },
}
```
