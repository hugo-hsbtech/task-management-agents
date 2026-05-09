---
name: error-tracking-fastapi-sentry
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Sentry SDK internals for the ezra_observability Sentry adapter — sentry_sdk.init configuration, StarletteIntegration/FastApiIntegration/SqlalchemyIntegration setup, EventScrubber denylist, before_send filters, PII rules, and adapter-level tests. ADAPTER AUTHORS ONLY. App code must use `from ezra_observability import get_observability` (see ezra-add-monitoring).
author: Carlos Melgoza
---

# Error Tracking — FastAPI + Sentry (Adapter Reference)

> **Scope:** This skill documents Sentry SDK specifics for whoever maintains the `ezra_observability` Sentry adapter (`backend/packages/domains/observability/src/ezra_observability/adapters/sentry.py`). Application code — routes, services, workers, dependencies — must not import `sentry_sdk` directly. CI lints for it.
>
> **If you're a feature developer adding error tracking to your code, you want `ezra-add-monitoring`, not this file.**
>
> **Why we have an abstraction:** see `docs/proposals/sentry-error-tracking-introduction.md`. Short version: Sentry is the default error tracker today, behind a port (Protocol) so we can swap it for Logfire/SigNoz/OTel later by writing one new adapter. The patterns below are how the Sentry adapter implements that port.

Sentry implementation patterns for FastAPI. Covers SDK initialization, user context injection via dependencies, PII scrubbing, and background task tracing.

## When to Activate

- Modifying the `SentryObservability` adapter implementation
- Updating `sentry_sdk.init` integration list, sampling, or scrubber configuration
- Debugging why an event isn't shipping (or why an unexpected one is)
- Adding a new `before_send` rule to drop a known-noise event class
- Reviewing an adapter PR for PII safety

## SDK Initialization

The adapter calls `sentry_sdk.init` exactly once, from `SentryObservability.__init__` when `settings.is_enabled` (DSN set). The init runs inside the lifespan task at app boot, which is required for `AsyncioIntegration` to wire up against the running event loop.

```python
# adapters/sentry.py (Sentry adapter — only file that imports sentry_sdk)
import logging
import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.scrubber import EventScrubber, DEFAULT_DENYLIST, DEFAULT_PII_DENYLIST

EZRA_PII_DENYLIST = [
    "clerk_session", "clerk_jwt", "clerk_api_key",
    "hubspot_api_key", "hubspot_token",
    "slack_token", "slack_signing_secret",
    "openai_api_key", "anthropic_api_key",
    "exa_api_key", "hunter_api_key",
    "stripe_secret_key", "stripe_webhook_secret",
    "resend_api_key",
]

def _init_sdk(
    service_name: str,
    settings: SentrySettings,
    *,
    transport: sentry_sdk.transport.Transport | None = None,
) -> None:
    # `transport` is a TEST-ONLY hook. Production callers do not pass it (None
    # → SDK installs the real HTTPS transport). Auto-capture integration tests
    # pass a fake transport so events stay in-process. See "Adapter-level
    # testing" below.
    sentry_sdk.init(
        dsn=settings.dsn,
        environment=settings.environment,
        release=settings.release,
        sample_rate=settings.sample_rate,
        traces_sample_rate=settings.traces_sample_rate,           # 0.0 today (errors-only)
        profiles_sample_rate=settings.profiles_sample_rate,       # 0.0 today
        send_default_pii=settings.send_default_pii,               # False
        max_request_body_size="never",                            # do NOT attach request bodies
        debug=settings.debug,
        shutdown_timeout=settings.shutdown_timeout,               # 2.0s default
        transport=transport,                                      # None in prod
        integrations=[
            # failed_request_status_codes=set() means HTTP 5xx responses raised via
            # HTTPException are NOT auto-captured. The Sentry default is 500-599.
            # See "5xx HTTPException policy" below.
            StarletteIntegration(
                transaction_style="endpoint",
                failed_request_status_codes=set(),
            ),
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes=set(),
            ),
            SqlalchemyIntegration(),
            AsyncioIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=None),
        ],
        event_scrubber=EventScrubber(
            denylist=DEFAULT_DENYLIST + EZRA_PII_DENYLIST,
            pii_denylist=DEFAULT_PII_DENYLIST + EZRA_PII_DENYLIST,
            recursive=True,
        ),
        before_send=_before_send,
    )
    sentry_sdk.set_tag("service", service_name)
```

Decisions worth keeping in mind:

- **`max_request_body_size="never"`.** sentry-sdk's default is `"medium"`, which means the Starlette extractor *will* attach JSON/form bodies to events. Bodies stay off, period. If a future debug requires body-side context, add the specific safe field to the explicit capture site as `extras` from app code — not by raising this setting.
- **5xx HTTPException policy: not captured at launch** (`failed_request_status_codes=set()` on both Starlette and FastAPI integrations). The Sentry default is to capture **any** HTTP 500–599 response as a "failed request" — including responses produced by deliberate `raise HTTPException(503, ...)` calls. The codebase has at least three of these by design (`JWKSUnavailableError → 503` and `ClerkAPIUnavailableError → 503` in `auth.py:142–163`, plus the existing `clerk_api_unavailable_handler`). They are graceful-degradation responses, not bugs. Capturing them on day one would drown the signal we want — true unhandled exceptions, which the integration captures *separately* via the ASGI middleware regardless of `failed_request_status_codes`. If a route wants Sentry to see a 5xx case, it calls `obs.capture_exception(exc)` explicitly before raising. Post-launch we may re-enable a narrow set (`{500, 502, 504}`) once we've watched real volume.
- **`AsyncioIntegration` is not auto-enabled.** Listing it explicitly is what makes async-task instrumentation correct. SDK init must run inside an async context (i.e., the lifespan task), which it does — `configure_observability` is called from `lifespan`, and from `async def main()` in workers.
- **`SqlalchemyIntegration` is in the list but inert today.** `traces_sample_rate=0.0` means it adds error breadcrumbs only; no spans ship. Keeping it in means turning tracing on later is a config flip.
- **`LoggingIntegration(level=logging.INFO, event_level=None)`.** `logger.info(...)` becomes a breadcrumb; `logger.error(...)` does **not** auto-create a Sentry event. Apps capture explicitly via the port. This is the lever that keeps Sentry signal/noise under our control.
- **`event_scrubber=EventScrubber(...)` with extended denylists.** The scrubber redacts known-key tokens recursively. It does *not* redact free-text strings or unfamiliar keys, which is why the port doesn't accept email and the app-developer skill enforces "no PII in tag/breadcrumb values."
- **`sentry_sdk.set_tag("service", service_name)`.** Every event from this process is tagged with which app produced it. Sentry projects are per-app, but the tag survives if we ever multiplex.

## Settings

The adapter reads `SentrySettings(BaseSettings)` from `ezra_observability.settings`. The DSN-empty-means-disabled rule lives in the factory: when DSN is empty the factory returns `NullObservability` and `sentry_sdk.init` is never called.

```python
# settings.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class SentrySettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    dsn: str = Field(default="", validation_alias="SENTRY_DSN")
    environment: str = Field(default="Local", validation_alias="SENTRY_ENVIRONMENT")
    release: str | None = Field(default=None, validation_alias="SENTRY_RELEASE")

    sample_rate: float = Field(default=1.0, validation_alias="SENTRY_SAMPLE_RATE")
    traces_sample_rate: float = Field(default=0.0, validation_alias="SENTRY_TRACES_SAMPLE_RATE")
    profiles_sample_rate: float = Field(default=0.0, validation_alias="SENTRY_PROFILES_SAMPLE_RATE")

    send_default_pii: bool = Field(default=False, validation_alias="SENTRY_SEND_DEFAULT_PII")
    debug: bool = Field(default=False, validation_alias="SENTRY_DEBUG")
    shutdown_timeout: float = Field(default=2.0, validation_alias="SENTRY_SHUTDOWN_TIMEOUT")

    @property
    def is_enabled(self) -> bool:
        return bool(self.dsn)
```

## What the integrations capture

These behaviors are inherent to `StarletteIntegration` + `FastApiIntegration` + `SqlalchemyIntegration` + `AsyncioIntegration` + `LoggingIntegration`. They are not adapter-side code.

**Captured automatically:**

- Unhandled exceptions in route handlers, dependencies, and middleware (regardless of `failed_request_status_codes` — these go through the ASGI middleware, a different path)
- HTTP method, URL, route name (path parameters preserved with the route template, not values)
- Headers — filtered by `EventScrubber`, but **review what reaches the event in staging** before turning Sentry on in production
- DB error context from SQLAlchemy

**Not captured at launch:**

- Handled-and-not-re-raised exceptions
- `HTTPException` (4xx) — Sentry treats these as expected client errors and skips them by default
- `HTTPException` (5xx) — at launch, suppressed by `failed_request_status_codes=set()` on both integrations. **By Sentry's default (500–599), 5xx HTTPException responses *would* be captured.** We deliberately turn that off because the codebase deliberately raises `HTTPException(503)` for graceful Clerk degradation. If a route wants a 5xx tracked anyway, it calls `obs.capture_exception(exc)` explicitly before raising.
- Errors in `BackgroundTasks`, `asyncio.create_task`, polling loops, or Temporal activities — those need explicit capture from app code via the port

## Implementing the port

The adapter's job is to translate port methods into `sentry_sdk` calls. Keep this layer thin — every additional transformation is a place where bugs hide.

```python
from sentry_sdk import Client

class SentryObservability:
    __slots__ = ("_service_name", "_settings", "_client")

    def __init__(
        self,
        *,
        service_name: str,
        settings: SentrySettings,
        transport: sentry_sdk.transport.Transport | None = None,
    ) -> None:
        # `transport` is the test-only hook documented in `_init_sdk`. The factory
        # and `configure_observability()` do not forward it; tests instantiate the
        # adapter directly and then `install_observability_for_testing(adapter)`.
        self._service_name = service_name
        self._settings = settings
        self._client: Client | None = None
        if settings.is_enabled:
            _init_sdk(service_name, settings, transport=transport)
            # Retain THIS adapter's client. sentry_sdk.init() mutates a global; if
            # configure_observability() is later called with new settings, the global
            # is replaced. Without this reference, flush()/close() would target the
            # NEW client and silently lose the old one's in-flight events.
            self._client = sentry_sdk.get_client()

    def capture_exception(self, exc, *, level="error", tags=None, extras=None):
        with sentry_sdk.new_scope() as scope:
            if tags:
                for k, v in tags.items():
                    scope.set_tag(k, v)
            if extras:
                for k, v in extras.items():
                    scope.set_extra(k, v)
            scope.set_level(level)
            event_id = sentry_sdk.capture_exception(exc)
        return CapturedEventId(event_id) if event_id else None

    def set_user(self, user_id, *, username=None, extras=None):
        # Note: port does NOT accept email — see `ezra-add-monitoring` PII rules.
        sentry_sdk.set_user(
            {"id": user_id, "username": username, **(extras or {})}
            if user_id is not None else None
        )

    def set_tag(self, key, value):
        sentry_sdk.set_tag(key, value)

    def add_breadcrumb(self, category, message, *, level="info", data=None):
        sentry_sdk.add_breadcrumb(
            category=category, message=message, level=level, data=dict(data or {})
        )

    @contextmanager
    def isolated_scope(self):
        with sentry_sdk.new_scope():
            yield

    def flush(self, timeout: float = 2.0) -> None:
        if self._client is not None:
            self._client.flush(timeout=timeout)

    def close(self, timeout: float = 2.0) -> None:
        # Called by the singleton when this adapter is being replaced (production
        # reconfigure, install_observability_for_testing, reset_observability_for_testing).
        # Flush + close THIS adapter's client specifically. Idempotent.
        #
        # IMPORTANT: Client.close() shuts down the transport but does NOT detach
        # the client from Sentry's global scope. Without detaching, subsequent
        # capture_* calls in the same process either silently no-op against a
        # closed client or — after a singleton swap — accidentally use ours when
        # they should be using the new adapter's. Detach only when the global is
        # still pointing at OUR client; if a newer adapter has already taken
        # over, leave it alone.
        client = self._client
        if client is None:
            return
        if sentry_sdk.get_client() is client:
            sentry_sdk.get_global_scope().set_client(None)
        client.close(timeout=timeout)
        self._client = None

    # ... capture_message, set_context wrap their sentry_sdk equivalents the same way ...
```

Three patterns to keep:

- **`with sentry_sdk.new_scope()` around every capture_exception path** — port-level isolation. Tags from this capture do not leak to the next one. Mirrors the `isolated_scope()` contract of the port.
- **No `email` parameter on `set_user`.** This is enforced at the port-type level so app code can't pass one even if it tries. If a debug session genuinely needs email, an adapter author adds it to `extras` under code review with a written reason.
- **Retain `self._client` at init time and use it in `flush`/`close`.** Do not call `sentry_sdk.get_client()` inside flush — that returns the *current* global, which after a reconfigure is no longer this adapter's client. This was a real bug in an earlier draft.

## before_send filtering

The launch ruleset is intentionally minimal. Adding more rules is a real risk because expected exceptions are converted to `HTTPException` upstream, so filtering by exception class often filters nothing.

```python
def _before_send(event, hint):
    # Drop health-check noise.
    request = event.get("request", {}) or {}
    url = request.get("url", "") or ""
    if url.endswith("/healthz") or url.endswith("/health"):
        return None
    return event
```

**A previous draft of the proposal proposed filtering `JWKSUnavailableError` here. That rule would have been a no-op:** `ezra_api/dependencies/auth.py:142–147` catches `JWKSUnavailableError` and re-raises as `HTTPException(status_code=503)`. By the time `before_send` runs, the original exception class is gone. If 503 auth/Clerk-cache outages turn out to be noisy in production, filter by URL path + response status (`event["contexts"]["response"]["status_code"]`) — or set `failed_request_status_codes` on the FastAPI integration — deliberately, after watching real volume. Don't add rules whose conditions never match.

## Adapter-level testing

Tests for the adapter use a fake `Transport` so events are captured locally instead of leaving the process. Mocking `sentry_sdk.capture_exception` is wrong for adapter tests — it doesn't exercise the scrubber, `before_send`, or the integration pipeline.

The `before_send` filter reads **`event["request"]["url"]`** (the request interface), not `event["contexts"]["request"]`. These are different fields populated by different sources: `request` is filled by the integration's HTTP extractor when a real ASGI request goes through, `contexts` is filled by `set_context`. A test that uses `set_context("request", {...})` will not exercise the filter — the filter will read `event.get("request", {})`, get nothing, and pass the event through.

There are two correct ways to test the filter, both shown below.

**Option A — direct `capture_event` with the right shape (fast, unit-level):**

```python
# tests/test_sentry_adapter.py
import sentry_sdk
from sentry_sdk.transport import Transport
from ezra_observability.adapters.sentry import _before_send

class _CapturingTransport(Transport):
    def __init__(self):
        super().__init__()
        self.envelopes = []
    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)

def test_health_check_is_dropped():
    transport = _CapturingTransport()
    sentry_sdk.init(
        dsn="https://x@example.com/1",
        transport=transport,
        before_send=_before_send,
        max_request_body_size="never",
    )
    # capture_event lets us hand-build the event dict with the same shape the
    # FastAPI integration would produce. The `request` interface is what
    # _before_send reads.
    sentry_sdk.capture_event({
        "message": "synthetic",
        "request": {"url": "https://api.example.com/healthz", "method": "GET"},
    })
    sentry_sdk.flush(timeout=1.0)

    assert transport.envelopes == []  # before_send returned None
```

**Option B — drive a real request through the integration (heavier, integration-level):**

Use `httpx.AsyncClient` against a `FastAPI` app with a `/healthz` route that raises a deliberate `RuntimeError`. The `StarletteIntegration` extractor populates `event.request.url` from the live request, exercising the actual code path. This is the test shape we use in the per-app **auto-capture integration tests** (see the testing-strategy section of `docs/proposals/sentry-error-tracking-introduction.md`).

`ezra_observability` ships Option-A unit tests for `_before_send`, `EventScrubber`, and the `flush`/`close` lifecycle. Each app under `backend/packages/apps/*` ships at least one Option-B test. App-side feature tests use `install_observability_for_testing(spy)` and never touch `sentry_sdk` directly — see `ezra-add-monitoring` for the spy fixture.

## Environment Variables

```bash
SENTRY_DSN=https://...@sentry.io/...    # Empty = NullObservability, no SDK init
SENTRY_ENVIRONMENT=Local
SENTRY_RELEASE=git-sha-or-semver        # Set in CI: $(git rev-parse --short HEAD)

# Optional, defaults are correct for errors-only operation
SENTRY_SAMPLE_RATE=1.0
SENTRY_TRACES_SAMPLE_RATE=0.0
SENTRY_PROFILES_SAMPLE_RATE=0.0
SENTRY_SEND_DEFAULT_PII=false
SENTRY_SHUTDOWN_TIMEOUT=2.0
```

**Acceptance gate before turning Sentry on in production for the first time:** trigger a deliberate error in staging and visually confirm the resulting event contains zero of: raw email, JWT, bearer token, API key, request body, free-text user content. The scrubber catches a lot but it is not infallible against unfamiliar keys.

## See Also

- `ezra-add-monitoring` — the canonical app-developer skill. Anyone who is not modifying this adapter wants that skill instead.
- `error-tracking` — tool-agnostic principles: boundaries, severity, alerting hygiene.
- `error-tracking-nextjs-sentry` — adapter-internals reference for the future frontend Sentry adapter.
- `docs/proposals/sentry-error-tracking-introduction.md` — architecture and rationale.
