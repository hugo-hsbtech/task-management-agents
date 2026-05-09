# Font Optimization

Use `next/font` for automatic font optimization with zero layout shift.

## Google Fonts

```tsx
// app/layout.tsx
import { Inter, Roboto_Mono } from 'next/font/google'

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
})

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={inter.className}>
      <body>{children}</body>
    </html>
  )
}
```

## Multiple Fonts with CSS Variables

```tsx
// app/layout.tsx
import { Inter, Roboto_Mono } from 'next/font/google'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const robotoMono = Roboto_Mono({
  subsets: ['latin'],
  variable: '--font-roboto-mono',
  display: 'swap',
})

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${inter.variable} ${robotoMono.variable}`}>
      <body>{children}</body>
    </html>
  )
}
```

```css
/* globals.css */
body { font-family: var(--font-inter); }
code { font-family: var(--font-roboto-mono); }
```

## Local Fonts

```tsx
import localFont from 'next/font/local'

// Variable font
const myFont = localFont({
  src: './fonts/MyFont-Variable.woff2',
  variable: '--font-my-font',
  display: 'swap',
})

// Multiple weights
const myFont = localFont({
  src: [
    { path: './fonts/MyFont-Regular.woff2', weight: '400' },
    { path: './fonts/MyFont-Bold.woff2', weight: '700' },
  ],
  variable: '--font-my-font',
})
```

## Tailwind CSS Integration

```tsx
// app/layout.tsx
const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export default function RootLayout({ children }) {
  return (
    <html className={inter.variable}>
      <body className="font-sans">{children}</body>
    </html>
  )
}
```

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-inter)'],
      },
    },
  },
}
```

## Best Practices

- **Never use `<link>` tags** for fonts — they block rendering and lack optimization
- **Create font instances once** in layout, not in individual components
- **Specify only needed subsets and weights** to minimize payload
- **Use `'swap'` display** as the default strategy
- **Export from a shared file** for component-specific fonts:

```tsx
// lib/fonts.ts
import { Inter } from 'next/font/google'

export const inter = Inter({ subsets: ['latin'] })
```
