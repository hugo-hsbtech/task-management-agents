---
name: feature-flags-ts-posthog
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] TypeScript feature flag patterns using PostHog JS and Node SDKs — typed constants, React hooks, Next.js SSR bootstrap, local evaluation, and testing. Use with feature-flags for universal patterns.
author: Carlos Melgoza
---

# Feature Flags — TypeScript + PostHog

TypeScript implementation patterns for evaluating PostHog feature flags on the client (posthog-js) and server (posthog-node).

## When to Activate

- Adding feature flag evaluation in TypeScript or React code
- Setting up PostHog SDK in a Next.js, Express, or Node.js project
- Writing tests that involve feature flags
- Bootstrapping flags server-side to prevent client flicker
- Debugging a flag not evaluating as expected

## SDK Selection

| Context | SDK | Install |
|---|---|---|
| Browser / React | `posthog-js` | `npm i posthog-js` |
| Node.js / Next.js server | `posthog-node` | `npm i posthog-node` |
| Next.js full-stack | Both | Install both |

## Typed Flag Constants

Define all flag keys in one place. Never use raw strings at call sites.

```typescript
// lib/flags.ts
export const FLAGS = {
  NEW_CHECKOUT:       'new-checkout-flow',
  BILLING_V2:         'billing-v2-enabled',
  AI_AUTOCOMPLETE:    'ai-autocomplete-beta',
  DARK_MODE:          'dark-mode-rollout',
} as const

export type FlagKey = typeof FLAGS[keyof typeof FLAGS]
```

## Client-Side Setup (posthog-js)

```typescript
// lib/posthog.ts
import posthog from 'posthog-js'

export function initPostHog() {
  if (typeof window === 'undefined') return

  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST ?? 'https://app.posthog.com',
    bootstrap: {
      // Populated server-side to prevent flicker — see SSR Bootstrap section
      featureFlags: {},
    },
    // Disable automatic capture if you only need feature flags
    autocapture: false,
    capture_pageview: false,
  })
}
```

## Server-Side Setup (posthog-node)

```typescript
// lib/posthog-server.ts
import { PostHog } from 'posthog-node'

// Singleton — do not instantiate per-request
let client: PostHog | null = null

export function getPostHogClient(): PostHog {
  if (!client) {
    client = new PostHog(process.env.POSTHOG_API_KEY!, {
      host: process.env.POSTHOG_HOST ?? 'https://app.posthog.com',
      // Enable local evaluation to avoid a network call per flag check
      personalApiKey: process.env.POSTHOG_PERSONAL_API_KEY,
      featureFlagsPollingInterval: 30_000,
    })
  }
  return client
}
```

## Server-Side Flag Evaluation

```typescript
import { getPostHogClient } from '@/lib/posthog-server'
import { FLAGS } from '@/lib/flags'

export async function isFeatureEnabled(
  flagKey: FlagKey,
  distinctId: string,
  userProperties?: Record<string, string | number | boolean>,
): Promise<boolean> {
  const client = getPostHogClient()

  const value = await client.isFeatureEnabled(flagKey, distinctId, {
    personProperties: userProperties,
  })

  // isFeatureEnabled returns boolean | undefined — treat undefined as false
  return value ?? false
}

export async function getFeatureFlagPayload(
  flagKey: FlagKey,
  distinctId: string,
): Promise<unknown> {
  const client = getPostHogClient()
  return client.getFeatureFlagPayload(flagKey, distinctId) ?? null
}
```

## Next.js SSR Bootstrap (Prevent Flicker)

Evaluate flags on the server and pass them to the client so posthog-js doesn't need a round-trip before rendering.

```typescript
// app/layout.tsx (Next.js App Router)
import { getPostHogClient } from '@/lib/posthog-server'
import { PostHogProvider } from '@/components/PostHogProvider'
import { auth } from '@/lib/auth'

export default async function RootLayout({ children }) {
  const session = await auth()
  const flags: Record<string, boolean | string> = {}

  if (session?.user) {
    const client = getPostHogClient()
    const allFlags = await client.getAllFlags(session.user.id, {
      personProperties: {
        email: session.user.email,
        plan: session.user.plan,
      },
    })
    Object.assign(flags, allFlags)
  }

  return (
    <html>
      <body>
        <PostHogProvider bootstrapData={{ featureFlags: flags }}>
          {children}
        </PostHogProvider>
      </body>
    </html>
  )
}
```

```tsx
// components/PostHogProvider.tsx
'use client'

import posthog from 'posthog-js'
import { PostHogProvider as PHProvider } from 'posthog-js/react'
import { useEffect } from 'react'

interface Props {
  children: React.ReactNode
  bootstrapData?: { featureFlags: Record<string, boolean | string> }
}

export function PostHogProvider({ children, bootstrapData }: Props) {
  useEffect(() => {
    posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
      api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
      bootstrap: bootstrapData,
    })
  }, [])

  return <PHProvider client={posthog}>{children}</PHProvider>
}
```

## React Hooks

```tsx
'use client'

import { useFeatureFlagEnabled, useFeatureFlagVariantKey } from 'posthog-js/react'
import { FLAGS } from '@/lib/flags'

// Boolean flag
export function NewCheckoutGate({ children }: { children: React.ReactNode }) {
  const enabled = useFeatureFlagEnabled(FLAGS.NEW_CHECKOUT)

  // undefined means flags not yet loaded — render nothing or a skeleton
  if (enabled === undefined) return null
  if (!enabled) return null

  return <>{children}</>
}

// Multivariate flag
export function CheckoutVariant() {
  const variant = useFeatureFlagVariantKey(FLAGS.CHECKOUT_VARIANT)

  if (variant === 'test') return <NewCheckout />
  return <OriginalCheckout />       // 'control' or undefined (flag off)
}
```

## Server Component Evaluation (App Router)

```tsx
// app/checkout/page.tsx
import { isFeatureEnabled } from '@/lib/flags-server'
import { auth } from '@/lib/auth'

export default async function CheckoutPage() {
  const session = await auth()
  const showNewCheckout = session
    ? await isFeatureEnabled(FLAGS.NEW_CHECKOUT, session.user.id, {
        email: session.user.email,
        plan: session.user.plan,
      })
    : false

  return showNewCheckout ? <NewCheckout /> : <OldCheckout />
}
```

## Express / Node.js Middleware

```typescript
// middleware/featureFlags.ts
import { Request, Response, NextFunction } from 'express'
import { getPostHogClient } from '../lib/posthog-server'
import { FLAGS, FlagKey } from '../lib/flags'

declare global {
  namespace Express {
    interface Request {
      flags: Record<FlagKey, boolean>
    }
  }
}

const FLAG_KEYS = Object.values(FLAGS) as FlagKey[]

export async function featureFlagsMiddleware(
  req: Request,
  _res: Response,
  next: NextFunction,
) {
  const userId = req.user?.id ?? req.sessionID
  const client = getPostHogClient()

  try {
    const allFlags = await client.getAllFlags(userId, {
      personProperties: {
        email: req.user?.email,
        plan: req.user?.plan,
      },
    })

    req.flags = {} as Record<FlagKey, boolean>
    for (const key of FLAG_KEYS) {
      req.flags[key] = Boolean(allFlags[key] ?? false)
    }
  } catch {
    // Fail safe — all flags off if PostHog unreachable
    req.flags = Object.fromEntries(FLAG_KEYS.map(k => [k, false])) as Record<FlagKey, boolean>
  }

  next()
}
```

## Local Evaluation

Local evaluation avoids a network call per flag check. Requires a Personal API Key.

```typescript
const client = new PostHog(process.env.POSTHOG_API_KEY!, {
  personalApiKey: process.env.POSTHOG_PERSONAL_API_KEY!,
  featureFlagsPollingInterval: 30_000, // poll every 30s
})

// With local evaluation enabled, isFeatureEnabled() does not make a network request
const enabled = await client.isFeatureEnabled(FLAGS.NEW_CHECKOUT, userId)
```

**Use local evaluation in all server-side contexts** where flag evaluation happens per-request.

## Graceful SDK Shutdown

```typescript
// In your process shutdown handler
process.on('SIGTERM', async () => {
  await getPostHogClient().shutdown()
  process.exit(0)
})
```

## Testing

### Unit Tests

```typescript
// __mocks__/posthog-node.ts
export const mockIsFeatureEnabled = jest.fn().mockResolvedValue(false)
export const mockGetAllFlags = jest.fn().mockResolvedValue({})

jest.mock('posthog-node', () => ({
  PostHog: jest.fn().mockImplementation(() => ({
    isFeatureEnabled: mockIsFeatureEnabled,
    getAllFlags: mockGetAllFlags,
    shutdown: jest.fn(),
  })),
}))
```

```typescript
// checkout.test.ts
import { mockIsFeatureEnabled } from '../__mocks__/posthog-node'

describe('CheckoutPage', () => {
  it('renders new checkout when flag is on', async () => {
    mockIsFeatureEnabled.mockResolvedValueOnce(true)
    // ...test
  })

  it('renders old checkout when flag is off', async () => {
    mockIsFeatureEnabled.mockResolvedValueOnce(false)
    // ...test
  })

  it('renders old checkout when PostHog is unreachable', async () => {
    mockIsFeatureEnabled.mockRejectedValueOnce(new Error('Network error'))
    // ...test — must render safely
  })
})
```

### React Component Tests

```typescript
import { useFeatureFlagEnabled } from 'posthog-js/react'

jest.mock('posthog-js/react', () => ({
  useFeatureFlagEnabled: jest.fn(),
  useFeatureFlagVariantKey: jest.fn(),
}))

const mockFlag = useFeatureFlagEnabled as jest.Mock

it('shows new UI when flag is enabled', () => {
  mockFlag.mockReturnValue(true)
  render(<MyComponent />)
  expect(screen.getByTestId('new-ui')).toBeInTheDocument()
})
```

## Environment Variables

```bash
# Client-side (Next.js — safe to expose)
NEXT_PUBLIC_POSTHOG_KEY=phc_...
NEXT_PUBLIC_POSTHOG_HOST=https://app.posthog.com

# Server-side only
POSTHOG_API_KEY=phc_...                    # Project API key
POSTHOG_PERSONAL_API_KEY=phx_...           # For local evaluation
POSTHOG_HOST=https://app.posthog.com
```

**Remember**: Enable local evaluation in all server-side contexts. Without `personalApiKey` set, every `isFeatureEnabled()` call makes a synchronous network request — this will hurt response times under load.

## See Also

- `feature-flags` — universal patterns: naming, types, lifecycle, hygiene rules
- `feature-flags-posthog` — PostHog API: create, target, discover, archive flags
