---
name: error-tracking
description: Universal error tracking patterns — error capture, context enrichment, breadcrumbs, PII scrubbing, before-send filtering, performance tracing, and alerting hygiene
author: Carlos Melgoza
---

# Error Tracking

Patterns for instrumenting applications with error tracking. Tool-agnostic — applies to Sentry, Datadog, New Relic, Honeybadger, and similar platforms.

## When to Activate

- Adding error tracking instrumentation to a new service or feature
- Enriching error reports with user context, request metadata, or custom tags
- Writing `before-send` filters to scrub PII or reduce noise
- Setting up performance tracing for slow operations
- Reviewing alert fatigue caused by noisy or unactionable errors

## Capture Errors at Boundaries

Error tracking works best when you capture at clear, consistent boundaries — not scattered across business logic.

The natural capture points are:

| Boundary | What to capture |
|----------|----------------|
| Global uncaught exception handler | All unhandled errors |
| HTTP request handler | Request-scoped context (user, route, method) |
| Background job / queue worker | Job ID, queue name, payload summary |
| External API call | Status code, latency, endpoint |
| Critical business operations | Operation name, input summary, outcome |

Avoid catching-and-reporting inside utility functions or deep in the call stack — you lose the original context and flood the tracker with duplicates.

## Enrich Every Error with Context

Bare stack traces answer "what crashed" but not "who was affected" or "what were they doing." Attach context at the request boundary so it's available on every error within that request.

```
user.id        — stable identifier, never email or name
user.role      — helps distinguish admin vs. end-user errors
request.id     — correlate with server logs
feature_flag   — which flags were active at the time
tenant.id      — for multi-tenant apps
environment    — production / staging / preview
release        — git SHA or semver tag
```

Set user context once per session or request, not on every capture call.

## Breadcrumbs

Breadcrumbs are the trail of events before an error. They answer "what did the user do right before this crash."

Good breadcrumbs:
- Navigation events (route changes, page loads)
- User interactions that trigger state changes (form submit, button click)
- Key state transitions (auth flow steps, checkout steps)
- Outbound HTTP calls with status codes

Bad breadcrumbs (too noisy, remove or throttle):
- Every render cycle
- Polling requests
- Internal log messages that aren't meaningful out of context

Keep breadcrumb payloads small — scrub any values that could contain PII before they're recorded.

## Before-Send Filtering

Use `before-send` hooks to control what reaches your tracker. Three main use cases:

**Drop noise** — errors that are expected and unactionable:

```
- ResizeObserver loop limit exceeded
- Script error (cross-origin, no stack)
- Network errors from browser extensions
- Canceled fetch requests (user navigated away)
- 404s on known missing assets
```

**Scrub PII** — strip sensitive data before it leaves the browser or server:

Fields to always scrub: `password`, `token`, `secret`, `authorization`, `cookie`, `card_number`, `ssn`, `dob`

Replace the value rather than removing the key entirely — keeping the key shows that the field existed, which can be useful for debugging.

**Normalize duplicates** — aggregate errors that are the same underlying issue:

Give errors explicit fingerprints when the default grouping produces too many separate issues for what is clearly one root cause.

```
// Example: all database connection errors grouped together
fingerprint: ['database-connection', error.code]
```

## Severity Levels

Use severity consistently so alerts fire on the right things:

| Level | When to use |
|-------|-------------|
| `fatal` | App cannot continue — process restart required |
| `error` | User-visible failure, operation aborted |
| `warning` | Degraded state, fallback used, operation succeeded with caveats |
| `info` | Significant business event (not an error) |
| `debug` | Development only — remove before production |

Never capture expected control flow (`404`, `401`, form validation errors) as `error` or `fatal`.

## Performance Tracing

Most error tracking platforms also capture traces for slow operations. The pattern is the same across tools:

- Start a transaction at the outermost boundary (HTTP request, job start)
- Add child spans for meaningful sub-operations (DB query, external API, cache lookup)
- Finish the transaction on completion

Trace every operation that has a user-visible latency impact. Skip internal utility calls that are too granular to be useful in a trace.

Set a sample rate lower than 1.0 in production — 0.1 (10%) is a reasonable starting point for high-traffic endpoints. Increase dynamically for errors or slow transactions.

## Alerting Hygiene

The goal of alerting is actionable signal. Common failure modes:

**Too many alerts** — engineers stop reading them. Causes: alerting on `warning`, alerting on known-flaky errors, no deduplication window.

**Too few alerts** — production breaks silently. Causes: overly aggressive `before-send` filters, wrong environment sampling.

Good defaults:
- Alert on new error types in the last 24 hours
- Alert on error rate spike (% increase, not absolute count)
- Alert on `fatal` and `error`, not `warning`
- Silence errors you've acknowledged and are tracking in your issue tracker

**Remember**: Error tracking is only useful if the errors it captures are actionable. A clean tracker with 50 meaningful errors per day is more valuable than a noisy one with 50,000 where real issues hide in the noise. Invest in `before-send` filters early.

## See Also

- `error-tracking-nextjs-sentry` — Sentry implementation for Next.js App Router with session replay
- `error-tracking-fastapi-sentry` — Sentry implementation for FastAPI with StarletteIntegration
