---
name: feature-flags
description: Universal feature flag patterns — flag types, naming conventions, lifecycle management, fail-safe defaults, and cleanup checklists. Provider-agnostic. Use with feature-flags-posthog, feature-flags-ts-posthog, or feature-flags-fastapi-posthog for implementation.
author: Carlos Melgoza
---

# Feature Flags — Universal Patterns

Provider-agnostic patterns for designing, implementing, and retiring feature flags. Use alongside a provider skill for SDK-specific implementation.

## When to Activate

- Designing a new feature flag
- Evaluating a flag in code
- Auditing existing flags for staleness
- Planning flag removal
- Reviewing flag naming or structure

## Flag Types

| Type | Returns | Use When |
|---|---|---|
| **Boolean** | `true` / `false` | Feature on/off, kill switches, gradual rollouts |
| **String (multivariate)** | `"control"` / `"test"` / `"variant-a"` | A/B tests, UI experiments, copy variants |
| **Number** | `42` / `0.5` | Thresholds, limits, rate values |
| **JSON / Remote Config** | `{ ... }` | Config objects, feature bundles, multiple values at once |

**Default to boolean.** Use multivariate only when the feature genuinely has more than two states.

## Flag Lifecycle

```
new → active → launched → inactive → archived → deleted
```

| State | Meaning | Action |
|---|---|---|
| **new** | Created, not yet evaluated | Add code, keep default off |
| **active** | Receiving evaluations, mixed variation | Monitor, iterate |
| **launched** | Fully rolled out (100% on) | Schedule cleanup |
| **inactive** | No evaluations in 30+ days | Verify, then archive |
| **archived** | Hidden from lists, preserved in history | Safe to delete after 30 days |
| **deleted** | Permanently removed | Irreversible |

## Naming Conventions

Use **kebab-case** everywhere. It is the only format that works natively across all providers and both languages without transformation.

```
new-checkout-flow
billing-v2-enabled
dark-mode-rollout
payment-stripe-express
ai-autocomplete-beta
```

**Namespace by domain when flags exceed ~20:**

```
billing-new-invoice-ui
billing-stripe-express
onboarding-skip-tour
onboarding-video-intro
```

**Never use:**
- `snake_case` (awkward in TS key lookups)
- `camelCase` (breaks in YAML/env configs)
- Vague names like `test-flag` or `flag-2`
- Negations like `disable-old-checkout` (double negatives in code)

## Typed Flag Constants

Never inline flag keys as raw strings. Define constants once and import everywhere.

```ts
// flags.ts
export const FLAGS = {
  NEW_CHECKOUT:       'new-checkout-flow',
  BILLING_V2:         'billing-v2-enabled',
  AI_AUTOCOMPLETE:    'ai-autocomplete-beta',
} as const

export type FlagKey = typeof FLAGS[keyof typeof FLAGS]
```

```python
# flags.py
class Flags:
    NEW_CHECKOUT    = "new-checkout-flow"
    BILLING_V2      = "billing-v2-enabled"
    AI_AUTOCOMPLETE = "ai-autocomplete-beta"
```

This ensures: grep-ability, refactoring safety, and a single source of truth for audits.

## Fail-Safe Defaults

**Rule: the default value must always preserve the current production behavior.**

```ts
// Good: off by default, new feature hidden safely
const enabled = getFlag(FLAGS.NEW_CHECKOUT, false)

// Bad: defaults to on, exposes unfinished feature if SDK unreachable
const enabled = getFlag(FLAGS.NEW_CHECKOUT, true)
```

Exceptions — kill switches invert this:
```ts
// Kill switch: default true = feature ON, flag OFF = feature disabled
const paymentsEnabled = getFlag(FLAGS.PAYMENTS_KILL_SWITCH, true)
```

Always document kill switch defaults explicitly in a comment.

## Temporary vs Permanent Flags

| Type | Examples | Cleanup |
|---|---|---|
| **Temporary** | Feature rollouts, A/B tests, beta access | Remove after launch or experiment ends |
| **Permanent** | Kill switches, ops toggles, entitlements | Keep indefinitely — document why |

Tag or comment permanent flags at creation time. Every untagged flag is assumed temporary.

## Flag Hygiene Rules

1. **One flag, one purpose.** Don't reuse a flag for a second unrelated feature.
2. **Default off.** New flags always start disabled in all environments.
3. **Short-lived by default.** If a flag is older than 90 days and still in code, question it.
4. **No nested flag logic.** Don't evaluate flags inside flag-gated branches.
5. **No flags in migrations.** Database migrations must be unconditional.
6. **Test both paths.** Every flag evaluation must have a test for the true and false branch.

## Evaluation Context

Always pass a consistent evaluation context. Minimum required fields:

```
distinctId   → user.id or session.id (required)
email        → user.email (for targeting rules)
plan         → "free" | "pro" | "enterprise"
environment  → "development" | "staging" | "production"
```

Group context (B2B targeting):
```
groupType    → "organization" | "team"
groupKey     → org.id
groupProps   → { plan, size, createdAt }
```

## Cleanup Checklist

Run this before removing any flag from code and the provider:

- [ ] Flag has been at 100% rollout for at least 7 days
- [ ] No evaluations returning the "off" variation in the last 7 days
- [ ] All environments (dev, staging, prod) serve the same variation
- [ ] No other flag lists this flag as a prerequisite/dependency
- [ ] Grep codebase — zero remaining references to the flag key string
- [ ] Both branches tested — delete the dead branch, keep the live one
- [ ] PR description documents: flag key, forward value, rationale
- [ ] Flag archived in provider (before deletion — gives 30-day safety window)

## Dead Code Removal Pattern

When a boolean flag is being retired at `true`:

```ts
// Before
const enabled = getFlag(FLAGS.NEW_CHECKOUT, false)
if (enabled) {
  return <NewCheckout />
} else {
  return <OldCheckout />
}

// After — remove flag, keep the live branch, delete dead code
return <NewCheckout />
```

When retiring at `false`: delete the entire flag-gated block and clean up imports.

## Anti-Patterns

```ts
// Bad: raw string — ungrepable, easy to typo
if (getFlag('new-checkout-flow')) { ... }

// Good: typed constant, refactoring-safe
if (getFlag(FLAGS.NEW_CHECKOUT)) { ... }
```

```ts
// Bad: flag inside a flag — combinatorial explosion
if (getFlag(FLAGS.FEATURE_A)) {
  if (getFlag(FLAGS.FEATURE_B)) { ... }
}

// Good: each flag guards its own independent feature
if (getFlag(FLAGS.FEATURE_A)) { ... }
```

```ts
// Bad: default to true for a rollout flag — exposes new UI on SDK failure
const show = getFlag(FLAGS.NEW_UI, true)

// Good: default off, existing behavior preserved on failure
const show = getFlag(FLAGS.NEW_UI, false)
```

```ts
// Bad: two booleans for a 3-way test
const variantA = getFlag(FLAGS.TEST_A, false)
const variantB = getFlag(FLAGS.TEST_B, false)

// Good: one multivariate flag
const variant = getFlag(FLAGS.CHECKOUT_VARIANT, 'control') // 'control' | 'test-a' | 'test-b'
```

**Remember**: Feature flags are temporary by default. If a flag has been at 100% rollout for 7+ days with no off-variation traffic, it is already a cleanup candidate — remove the branch and delete the flag.

## See Also

- `feature-flags-posthog` — PostHog API: create, target, discover, clean up flags
- `feature-flags-ts-posthog` — TypeScript + PostHog SDK implementation
- `feature-flags-fastapi-posthog` — FastAPI + PostHog SDK implementation
