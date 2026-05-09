---
name: product-analytics-ts-posthog
description: TypeScript product analytics patterns using PostHog JS and Node SDKs — event capture, user identification, super properties, group analytics, Next.js pageview tracking, autocapture configuration, and testing.
origin: Ezra
author: Carlos Melgoza
---

# Product Analytics — TypeScript + PostHog

TypeScript implementation patterns for capturing product analytics with PostHog on the client (`posthog-js`) and server (`posthog-node`).

## When to Activate

- Adding event tracking in TypeScript or React code
- Setting up PostHog SDK in a Next.js or Node.js project
- Implementing user identification at sign-up or sign-in
- Setting up group analytics for B2B organizations
- Writing tests that involve analytics calls

## SDK Selection

| Context | SDK | Install |
|---|---|---|
| Browser / React | `posthog-js` | `npm i posthog-js` |
| Node.js / Next.js server | `posthog-node` | `npm i posthog-node` |
| Next.js full-stack | Both | Install both |

## Typed Event Constants

Define all event names and their property shapes in one place.

```typescript
// lib/analytics/events.ts
export const EVENTS = {
  USER_SIGNED_UP:          'user_signed_up',
  PROJECT_CREATED:         'project_created',
  SUBSCRIPTION_UPGRADED:   'subscription_upgraded',
  PAYMENT_FAILED:          'payment_failed',
  INVITE_SENT:             'invite_sent',
  DASHBOARD_VIEWED:        'dashboard_viewed',
} as const

export type EventName = typeof EVENTS[keyof typeof EVENTS]
```

## Client-Side Setup (posthog-js)

```typescript
// lib/analytics/posthog.ts
import posthog from 'posthog-js'

export function initPostHog() {
  if (typeof window === 'undefined') return

  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST ?? 'https://app.posthog.com',

    // Autocapture is enabled by default.
    // It captures clicks, inputs, and pageviews automatically.
    // Custom events below layer on top of this.
    autocapture: true,
    capture_pageview: true,
    capture_pageleave: true,

    // Disable if you want full manual control:
    // autocapture: false,
    // capture_pageview: false,
  })
}
```

## Server-Side Setup (posthog-node)

```typescript
// lib/analytics/posthog-server.ts
import { PostHog } from 'posthog-node'

let client: PostHog | null = null

export function getAnalyticsClient(): PostHog {
  if (!client) {
    client = new PostHog(process.env.POSTHOG_API_KEY!, {
      host: process.env.POSTHOG_HOST ?? 'https://app.posthog.com',
    })
  }
  return client
}
```

## Super Properties

Set persistent context once at init. These attach to every subsequent event automatically.

```typescript
// lib/analytics/context.ts
import posthog from 'posthog-js'

export function setAnalyticsContext(user: { plan: string }) {
  posthog.register({
    app_version: process.env.NEXT_PUBLIC_APP_VERSION ?? 'unknown',
    environment: process.env.NODE_ENV,
    platform: 'web',
    plan_tier: user.plan,
  })
}
```

Call `setAnalyticsContext()` after the user is identified. Properties registered here fire on every event until `posthog.unregister('key')` or `posthog.reset()` is called.

## User Identification

### Client-side (posthog-js)

```typescript
// lib/analytics/identity.ts
import posthog from 'posthog-js'

export function identifyUser(user: {
  id: string
  email: string
  name: string
  plan: string
  createdAt: string
}) {
  posthog.identify(
    user.id,              // stable DB ID — never email or username
    {
      // $set: mutable properties (updated on every identify)
      email: user.email,
      name: user.name,
      plan_type: user.plan,
    },
    {
      // $set_once: immutable first-touch properties (never overwritten)
      signed_up_at: user.createdAt,
      acquisition_source: document.referrer || 'direct',
    },
  )
}

export function resetAnalytics() {
  // Always call on logout — generates a new anonymous ID
  posthog.reset()
}
```

### Server-side (posthog-node)

```typescript
import { getAnalyticsClient } from './posthog-server'

export async function identifyUserServer(user: {
  id: string
  email: string
  plan: string
}) {
  const client = getAnalyticsClient()

  client.identify({
    distinctId: user.id,
    properties: {
      email: user.email,
      plan_type: user.plan,
    },
  })

  // posthog-node queues events — flush ensures delivery in short-lived functions
  await client.flush()
}
```

## Event Capture

### Client-side

```typescript
import posthog from 'posthog-js'
import { EVENTS } from './events'

// Simple boolean event
posthog.capture(EVENTS.PROJECT_CREATED, {
  project_id: project.id,
  template_used: template?.name ?? null,
})

// Upgrade event with before/after context
posthog.capture(EVENTS.SUBSCRIPTION_UPGRADED, {
  plan_from: currentPlan,
  plan_to: newPlan,
  billing_interval: interval,
  upgrade_source: 'settings_page',
})
```

### Server-side

```typescript
import { getAnalyticsClient } from './posthog-server'
import { EVENTS } from './events'

export async function trackPaymentFailed(userId: string, details: {
  plan: string
  error_code: string
  amount: number
}) {
  const client = getAnalyticsClient()

  client.capture({
    distinctId: userId,
    event: EVENTS.PAYMENT_FAILED,
    properties: {
      plan_type: details.plan,
      error_code: details.error_code,
      amount_cents: details.amount,
    },
  })

  await client.flush()
}
```

### High-volume server events (skip person profile)

For server-side events that don't need a person record (webhooks, background jobs), set `$process_person_profile: false` to reduce PostHog costs.

```typescript
client.capture({
  distinctId: organizationId,
  event: 'api_request_completed',
  properties: {
    endpoint: '/api/export',
    duration_ms: 342,
    $process_person_profile: false,
  },
})
```

## Group Analytics (B2B)

```typescript
import posthog from 'posthog-js'

export function setOrganizationContext(org: {
  id: string
  name: string
  plan: string
  memberCount: number
}) {
  posthog.group('organization', org.id, {
    name: org.name,
    plan: org.plan,
    member_count: org.memberCount,
  })
}
```

Call `setOrganizationContext()` after `identifyUser()`. Events captured after this are attributed to both the user and the organization.

## React Context Provider

Wrap the app once so PostHog is accessible throughout.

```tsx
// components/AnalyticsProvider.tsx
'use client'

import posthog from 'posthog-js'
import { PostHogProvider } from 'posthog-js/react'
import { useEffect } from 'react'

export function AnalyticsProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
      api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
      autocapture: true,
      capture_pageview: true,
    })
  }, [])

  return <PostHogProvider client={posthog}>{children}</PostHogProvider>
}
```

## Next.js Pageview Tracking

Autocapture handles pageviews for standard navigations. For Next.js App Router soft navigations, add explicit tracking:

```typescript
// app/layout.tsx
'use client'

import { usePathname, useSearchParams } from 'next/navigation'
import { usePostHog } from 'posthog-js/react'
import { useEffect } from 'react'

export function PageviewTracker() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const posthog = usePostHog()

  useEffect(() => {
    if (pathname && posthog) {
      posthog.capture('$pageview', {
        $current_url: window.location.href,
      })
    }
  }, [pathname, searchParams, posthog])

  return null
}
```

## Graceful SDK Shutdown

```typescript
process.on('SIGTERM', async () => {
  await getAnalyticsClient().shutdown()
  process.exit(0)
})
```

## Testing

### Mock posthog-js in React tests

```typescript
// __mocks__/posthog-js.ts
const posthog = {
  init: jest.fn(),
  capture: jest.fn(),
  identify: jest.fn(),
  register: jest.fn(),
  group: jest.fn(),
  reset: jest.fn(),
}

export default posthog
```

```typescript
// checkout.test.ts
import posthog from 'posthog-js'

const mockCapture = posthog.capture as jest.Mock

beforeEach(() => jest.clearAllMocks())

it('tracks subscription_upgraded on plan change', async () => {
  await upgradePlan({ from: 'free', to: 'pro' })

  expect(mockCapture).toHaveBeenCalledWith('subscription_upgraded', {
    plan_from: 'free',
    plan_to: 'pro',
    billing_interval: expect.any(String),
    upgrade_source: expect.any(String),
  })
})

it('does not track when upgrade fails', async () => {
  mockUpgrade.mockRejectedValueOnce(new Error('Payment failed'))
  await expect(upgradePlan({ from: 'free', to: 'pro' })).rejects.toThrow()
  expect(mockCapture).not.toHaveBeenCalledWith('subscription_upgraded', expect.anything())
})
```

### Mock posthog-node in server tests

```typescript
jest.mock('posthog-node', () => ({
  PostHog: jest.fn().mockImplementation(() => ({
    capture: jest.fn(),
    identify: jest.fn(),
    flush: jest.fn().mockResolvedValue(undefined),
    shutdown: jest.fn(),
  })),
}))
```

## Environment Variables

```bash
# Client-side (Next.js — safe to expose)
NEXT_PUBLIC_POSTHOG_KEY=phc_...
NEXT_PUBLIC_POSTHOG_HOST=https://app.posthog.com
NEXT_PUBLIC_APP_VERSION=2.4.1

# Server-side only
POSTHOG_API_KEY=phc_...
POSTHOG_HOST=https://app.posthog.com
```

**Remember**: `posthog.capture()` is PostHog's method name — not `track()`. If you are migrating from Mixpanel or Amplitude, update all call sites. Autocapture gives you baseline data immediately; layer custom events on top for the metrics that drive decisions.

## See Also

- `product-analytics` — universal patterns: naming, identity lifecycle, governance rules
- `product-analytics-fastapi-posthog` — FastAPI + PostHog SDK implementation
