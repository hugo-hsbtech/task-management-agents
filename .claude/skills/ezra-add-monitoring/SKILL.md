---
name: ezra-add-monitoring
description: Add error tracking to Ezra backend code via the ezra_observability port. Use when adding a new FastAPI route, a new Temporal activity, a new background task, a new external API integration, or any code path that needs error capture, user context, or breadcrumbs. Triggers on "add monitoring", "add sentry", "capture this error", "track this", "instrument this endpoint", "report this exception", "add error tracking". Do NOT use for tracing/profiling work (errors-only scope today) or for Sentry adapter internals — see error-tracking-fastapi-sentry for adapter author work.
origin: Ezra
author: Carlos Melgoza
---

# Add Monitoring (Ezra Backend)

Adds error tracking to backend code through the `ezra_observability` port. **App code never imports `sentry_sdk` directly** — that's an architectural rule, not a stylistic preference. The port lets us swap Sentry for Logfire, SigNoz, or OTel later without touching feature code.

This skill is the canonical guide for **app developers**. If you're modifying the Sentry adapter itself, see `error-tracking-fastapi-sentry` for Sentry-specific internals.

## When to Activate

- Adding a new FastAPI route, especially one with external API calls or non-trivial business logic
- Adding a new Temporal workflow or activity
- Adding a new background task (asyncio task, polling loop)
- Adding a new external integration (HubSpot, Slack, OpenAI, Hunter, Stripe, etc.) with new failure modes
- Auditing an existing module that has bare `try/except: pass` or `try/except: logger.error(...)` blocks
- A user-reported bug needs more diagnostic context

**Do not activate** for: tracing/profiling/spans (out of scope today — `traces_sample_rate=0.0`), structured logging migrations, or Sentry SDK configuration changes.

## The one rule

```python
# ✅ Always
from ezra_observability import get_observability

obs = get_observability()
obs.capture_exception(exc, tags={"deal_id": deal.id})

# ❌ Never in app code
import sentry_sdk
sentry_sdk.capture_exception(exc)
```

CI lints for `import sentry_sdk` outside `ezra_observability.adapters.*` and will fail the build.

## What gets captured automatically

You don't need to write capture code for these — `FastApiIntegration` + `StarletteIntegration` handle them:

- Unhandled exceptions in route handlers and middleware
- Unhandled exceptions in dependencies
- HTTP request method, URL, route name. **Bodies are off** (`max_request_body_size="never"` in adapter init). Headers are filtered by the adapter's `EventScrubber`.

**There is no global `@app.exception_handler(Exception)` in `ezra-api`.** Adding one that calls `capture_exception` and re-raises would produce duplicate events because the ASGI integration already captures the same exception. If you find yourself reaching for one, you almost certainly want one of the explicit-capture patterns below instead.

You **do** need to write capture code for:

- Exceptions you handle and don't re-raise (the integration sees them as resolved)
- Exceptions in `BackgroundTasks`, `asyncio.create_task`, or polling loops
- Exceptions in Temporal activities (a separate interceptor in `ezra_workflows` handles workflow-level capture, but business-logic failures inside activities still need explicit capture if you swallow them)
- Anything that's "not an exception but is wrong" — silent fallbacks, missing data, contract violations from a third party

## Capturing exceptions

### Bubble-up path (most common)

If you don't catch it, the FastAPI integration captures it. Just let it propagate.

```python
@router.post("/deals/{deal_id}/triage")
async def trigger_triage(
    deal_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(enrich_observability_scope),  # sets user context for this request
):
    deal = await deals_repo.get(session, deal_id)  # may raise NotFound — fine, captured
    workflow = await temporal_client.start_workflow(...)  # may raise — fine, captured
    return {"workflow_id": workflow.id}
```

### Catch-and-capture (when you need to enrich and re-raise)

When the failure has context the integration can't see:

```python
from ezra_observability import get_observability

async def enrich_company(company_id: UUID, session: AsyncSession) -> Company:
    obs = get_observability()
    company = await companies_repo.get(session, company_id)
    try:
        emails = await hunter_client.find_emails(domain=company.domain)
    except HunterAPIError as exc:
        with obs.isolated_scope():
            obs.set_tag("company_id", str(company_id))
            obs.set_tag("hunter.endpoint", "find_emails")
            obs.set_context("company", {"domain": company.domain, "name": company.name})
            obs.capture_exception(exc)
        raise  # re-raise so the caller sees the failure too
    return await companies_repo.update_emails(session, company_id, emails)
```

**Why `isolated_scope()`:** without it, your tags leak into every subsequent capture in the same request/task. With it, they apply only to the captures inside the `with` block. Always use it for catch-and-capture.

### Capture-and-recover (when failure is acceptable)

When you genuinely want to swallow the error but still know it happened:

```python
async def warm_search_cache(query: str) -> None:
    obs = get_observability()
    try:
        await search_service.warm(query)
    except SearchUnavailableError as exc:
        with obs.isolated_scope():
            obs.set_tag("query_hash", hashlib.sha256(query.encode()).hexdigest()[:8])
            obs.capture_exception(exc, level="warning")
        # Cache warming is best-effort; continue
```

Two things to notice:

- `level="warning"` because this isn't a user-visible failure — it's a degraded state.
- We hash the query instead of sending it raw. Queries can contain PII.

## Capturing messages (no exception)

For "this shouldn't happen but isn't an exception":

```python
obs = get_observability()
if response.status_code == 200 and not response.json().get("companies"):
    obs.capture_message(
        "Hunter returned empty companies list with 200 status",
        level="warning",
        tags={"domain": domain},
    )
```

Use sparingly. Bare `obs.capture_message("foo failed")` is rarely useful — you almost always want either an exception (with stack trace) or a breadcrumb (with context for the next exception).

## User context

On authenticated routes, use `enrich_observability_scope` instead of `get_current_user`:

```python
from ezra_api.dependencies.observability import enrich_observability_scope

@router.get("/me/deals")
async def list_my_deals(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(enrich_observability_scope),  # <-- here
):
    return await deals_repo.list_for_user(session, user.id)
```

`enrich_observability_scope` calls `get_current_user` internally, then sets the user_id and clerk_id on the request scope. Switching is free — both return `User`.

For unauthenticated endpoints (webhooks, public deal-share pages), don't set user context. Tag with whatever identifies the caller instead (`webhook_provider`, `share_token_hash`, etc.).

## Tags vs. context vs. extras

- **Tags** are searchable, indexed, and have a length limit (~200 chars). Use for things you want to filter by in Sentry: `deal_id`, `workflow_id`, `company_id`, `hubspot_object_id`. Always strings (or things that string-format cleanly).
- **Context** is structured grouped data, displayed in a section on the event detail page. Use for "everything about this object": `obs.set_context("deal", {"id": ..., "stage": ..., "amount": ...})`.
- **Extras** are unstructured key/value bags on a single capture. Use for one-off diagnostic data attached to a specific exception: `obs.capture_exception(exc, extras={"retry_count": 3, "last_status": 502})`.

Rule of thumb: **tag what you'd filter by, context what you'd read.**

## Breadcrumbs

Breadcrumbs are the trail of events leading up to an error. The Sentry adapter already converts `logger.info(...)` calls (level INFO+) to breadcrumbs automatically — so most of the time you don't need to add them manually.

Add a manual breadcrumb when:

- A meaningful state transition happens that isn't logged (auth flow step, workflow phase change)
- You make an external call whose response code matters for debugging future errors

```python
obs.add_breadcrumb(
    category="hubspot",
    message="upserted contact",
    data={
        "hubspot_id": result.id,
        "operation": "upsert",
        "ezra_contact_id": str(contact.id),
    },
)
```

**Never put email, name, phone, or any other PII into the message or data fields.** Use the internal id (`contact.id`) and let the on-call engineer join back to the user via the DB. The `EventScrubber` catches known-key tokens, but it does not redact free-text strings or values under unfamiliar keys — anything you put here ships as-is.

Skip breadcrumbs for: per-row DB queries (too noisy), every render, polling tick events.

## Workers and background tasks

Workers don't have a request scope. Wrap each unit of work in `isolated_scope()` so tags don't leak across iterations:

```python
async def crm_sync_worker_loop(service: CRMSyncService) -> None:
    obs = get_observability()
    while True:
        async with session_factory() as session:
            with obs.isolated_scope():
                obs.set_tag("worker", "crm_sync")
                try:
                    job = await service.claim_next(session)
                    if job is None:
                        await asyncio.sleep(5)
                        continue
                    obs.set_tag("crm_sync.job_id", str(job.id))
                    await service.process(session, job)
                except asyncio.CancelledError:
                    raise  # let cancellation propagate; not a Sentry event
                except Exception as exc:
                    obs.capture_exception(exc)
                    # don't re-raise — keep the loop alive
```

For Temporal activities, the adapter's interceptor handles isolation and capture automatically. You only need to call `obs.capture_exception` inside an activity if you're handling and **not** re-raising — same rule as everywhere else.

## Flushing on shutdown

If your service has a clean shutdown path (signal handlers, lifespan teardown), call `flush()` before disposing resources:

```python
async with worker:
    await shutdown_event.wait()

get_observability().flush(timeout=2.0)
await engine.dispose()
```

After the Sentry rollout, `ezra-api` lifespan teardown and worker shutdown blocks should already do this. Add the same flush-before-dispose pattern when you write a new long-running service.

## PII rules

| Don't send | Instead |
| ---------- | ------- |
| Email addresses | User ID; or hash if you absolutely need a fingerprint |
| JWTs, bearer tokens, API keys | Drop entirely. Adapter scrubs known keys, but don't rely on it. |
| Raw request bodies in `extras` | Pick the specific fields that matter; redact or hash anything sensitive |
| Free-text user content (deal descriptions, search queries, message bodies) | Hash if you need correlation; otherwise omit |
| Phone numbers, addresses, dates of birth | Omit, always |

The port deliberately doesn't accept email on `set_user`. If you find yourself wanting to send email, you almost certainly want user_id instead.

When in doubt: trigger the error path in a staging environment, look at the resulting Sentry event, and confirm zero PII before merging.

## Testing

Tests run with `SENTRY_DSN=""`, which makes the factory return `NullObservability` — every method is a no-op. You don't have to mock anything.

There are **two distinct test shapes**, and using the wrong one is the most common mistake. The deciding question is: **does your code call `obs.capture_*` explicitly, or does it let the exception bubble?**

### A. Code that calls `obs.capture_*` explicitly → use the spy

This is the catch-and-capture and capture-and-recover patterns earlier in this skill. Test the **service or function directly**, not through HTTP. The `observability_spy` fixture replaces the singleton with a recording adapter:

```python
async def test_hunter_failure_is_captured(observability_spy, session):
    with mock.patch("hunter_client.find_emails", side_effect=HunterAPIError("503")):
        with pytest.raises(HunterAPIError):
            await enrich_company(company_id=UUID("..."), session=session)

    assert observability_spy.exceptions_captured[0].tags["company_id"]
```

`observability_spy` is provided by `ezra-test-utils`. It calls `install_observability_for_testing(spy)` in setup and `reset_observability_for_testing()` in teardown so the singleton doesn't leak.

### B. Code that lets the exception bubble out of a route → spy will not see it

If your route doesn't catch the exception, **the spy will be empty** even though Sentry will capture the error in production. `FastApiIntegration` + `StarletteIntegration` capture bubbled exceptions through Sentry's ASGI middleware path — that path goes straight to the SDK's transport, never through the port. Asserting `observability_spy.exceptions_captured == [...]` for a bubble path will either fail today or pass for the wrong reason after someone "fixes" it by adding a redundant explicit capture.

For these cases, **don't write a port-spy test.** The auto-capture behavior is verified once per app by the `test_unhandled_route_error_is_captured` integration test that ships with `ezra_observability` and uses the real `SentryObservability` + a fake transport. Your feature test only needs to assert the HTTP contract (status code, response body shape):

```python
async def test_failing_route_returns_500(client):
    with mock.patch("some_dep.do_thing", side_effect=RuntimeError("boom")):
        response = await client.post("/v1/things")
    assert response.status_code == 500  # Sentry capture is verified by the auto-capture integration test, not here
```

Quick decision table:

| Pattern in your code | Test shape |
| -------------------- | ---------- |
| `try: ... except: obs.capture_exception(e); raise` | Spy fixture — test the service function directly |
| `try: ... except: obs.capture_exception(e, level="warning")` (recover, no re-raise) | Spy fixture — test the service function directly |
| Background task / `asyncio.create_task` body that calls `obs.capture_exception` | Spy fixture — call the task function directly |
| Route handler that doesn't catch → exception bubbles out | Don't assert on the spy. Test the HTTP contract; auto-capture is covered by the per-app integration test. |
| `obs.set_user`, `obs.set_tag`, `obs.add_breadcrumb` | Spy fixture — record assertions on `spy.tags`, `spy.user`, `spy.breadcrumbs` |

## Common mistakes

- **Importing `sentry_sdk` in app code.** Use `from ezra_observability import get_observability`. CI will reject the import.
- **Forgetting `isolated_scope()` on catch-and-capture.** Tags will leak into other captures in the same request. Always wrap.
- **Capturing then swallowing without `level="warning"`.** If you're not re-raising and the user isn't affected, it's a warning, not an error. Save `error` for things that broke.
- **Logging an exception with `logger.error(exc)` and expecting it in Sentry.** The logging integration only sends breadcrumbs, not events (`event_level=None`). Use `obs.capture_exception(exc)` for that.
- **Setting user context on an unauthenticated endpoint.** Tag the caller (webhook provider, share token hash) instead.
- **Sending raw search queries, deal descriptions, or email bodies as tags or extras.** Hash or redact. Sentry's scrubber catches known-key fields but not free text.
- **Calling `obs.flush()` per request.** It's a shutdown primitive, not a per-request flush. The SDK batches and ships in the background.
- **Adding `traces_sample_rate=1.0` "for one route" via env override.** We're errors-only by design today. If you genuinely need a span for performance investigation, escalate — there's a follow-up proposal coming.

## Quick reference

```python
from ezra_observability import get_observability

obs = get_observability()

# Capture
obs.capture_exception(exc, tags={"deal_id": deal.id}, extras={"retry": 3})
obs.capture_message("unexpected empty response", level="warning", tags={"domain": d})

# Enrich (use inside isolated_scope when not in a request)
obs.set_user(user_id=str(user.id))
obs.set_tag("workflow_id", workflow_id)
obs.set_context("deal", {"id": deal.id, "stage": deal.stage})
obs.add_breadcrumb(category="hubspot", message="upserted contact")

# Isolation
with obs.isolated_scope():
    obs.set_tag("scoped", "yes")
    obs.capture_exception(exc)

# Shutdown
obs.flush(timeout=2.0)
```

## See Also

- `error-tracking` — tool-agnostic principles (boundaries, severity, alerting hygiene). Read first if you're new to error tracking.
- `error-tracking-fastapi-sentry` — Sentry adapter internals (StarletteIntegration, EventScrubber, before_send). For adapter authors only; app code does not use this.
- `docs/proposals/sentry-error-tracking-introduction.md` — architecture and rationale.
- `fastapi-patterns` — request-scoped dependency patterns the user-context dependency is built on.
