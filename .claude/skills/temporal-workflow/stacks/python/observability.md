# Observability — Python Implementation

For concepts, patterns, and design decisions, see `references/observability.md`.

This file contains the complete Python implementation: `configure_tracing()` function,
`TracingInterceptor` setup on both `Client.connect()` and `Worker()`, custom business spans
with `tracer.start_as_current_span()`, correlation ID pattern with `activity.info()`, and the
heartbeat pattern with `activity.heartbeat()` and `CancelledError` re-raise.

---

## Section 1: TracingInterceptor Setup

`TracingInterceptor` instruments all Temporal operations automatically — workflow execution,
activity scheduling, and signal handling each produce spans with trace context propagated through
the event history.

**Critical ordering requirement:** The OTel provider MUST be configured BEFORE `Client.connect()`.
`TracingInterceptor()` calls `opentelemetry.trace.get_tracer()` at construction time. If the
provider is registered after the interceptor is constructed, the interceptor captures the no-op
tracer and produces no spans.

```python
# Source: python.temporal.io/temporalio.contrib.opentelemetry.TracingInterceptor.html
from temporalio.contrib.opentelemetry import TracingInterceptor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter


def configure_tracing(exporter=None) -> TracingInterceptor:
    """Configure OTel provider and return TracingInterceptor.

    Call BEFORE Client.connect() -- TracingInterceptor captures the tracer at construction.

    Args:
        exporter: Any OTel-compatible SpanExporter. Defaults to ConsoleSpanExporter for
            development. Swap for production:
            - OTLP: OTLPSpanExporter(endpoint="http://collector:4317")
            - Jaeger, Zipkin, Datadog, or any OTel-compatible backend exporter
    """
    provider = TracerProvider()
    # Swap exporter for production: OTLPSpanExporter(endpoint="...") or any OTel-compatible exporter
    provider.add_span_processor(SimpleSpanProcessor(exporter or ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    return TracingInterceptor()
```

Pass the returned interceptor to **both** `Client.connect()` and `Worker()`. Omitting either
side produces an incomplete trace:

```python
# workflows/adapters/temporal_adapter.py — updated create_worker (extends adapter.md Section 5)
tracing = configure_tracing()  # MUST come before Client.connect()

client = await Client.connect(
    f"{host}:{port}", namespace=namespace,
    interceptors=[tracing],  # Client-side trace context propagation
)

worker = Worker(
    client, task_queue=task_queue,
    workflows=[DSLWorkflow], activities=[...],
    interceptors=[tracing],  # Worker-side span propagation
    workflow_runner=SandboxedWorkflowRunner(
        restrictions=SandboxRestrictions.default.with_passthrough_modules("pydantic")
    ),
)
```

`TracingInterceptor` implements both `temporalio.client.Interceptor` and
`temporalio.worker.Interceptor` — a single instance handles both sides. Create it once and
share the reference.

---

## Section 2: Custom Business Spans

`TracingInterceptor` instruments Temporal operations automatically. For step-level business
logic — payment status, order validation result, domain-specific attributes — add custom spans
inside activity functions using the standard OTel tracer API.

Retrieve the module-level tracer once at import time:

```python
# Source: opentelemetry-python SDK patterns
from opentelemetry import trace
from temporalio import activity

tracer = trace.get_tracer(__name__)


@activity.defn(name="process_payment")
async def process_payment_activity(state: dict) -> dict:
    info = activity.info()
    with tracer.start_as_current_span("process_payment.domain") as span:
        span.set_attribute("order_id", state.get("order_id", "unknown"))
        span.set_attribute("workflow.step", "process-payment")
        span.set_attribute("correlation_id", f"{info.workflow_id}/{info.run_id}")
        fn = registry.get("process_payment")
        result = await fn(state)
        span.set_attribute("payment.status", result.get("paid", False))
        return result
```

**Correlation ID pattern:** `activity.info()` exposes `workflow_id` and `run_id` — the two
fields that identify a specific execution in Temporal. Combine them as
`f"{info.workflow_id}/{info.run_id}"` to correlate business spans with Temporal execution
records in the same trace.

**Span naming convention:** Use `"{activity_name}.domain"` for business spans that run inside
a Temporal activity. This distinguishes custom spans from the auto-instrumented Temporal spans
(`StartActivity`, `RunActivity`, etc.) in the same trace.

**Attribute guidelines:**
- Include the domain entity ID (e.g., `order_id`) on every step span for cross-span correlation
- Include `workflow.step` matching the `StepDefinition.id` for traceability back to the DSL
- Add result-status attributes after the domain call completes, not before

---

## Section 3: Activity Heartbeats

Long-running activities must heartbeat periodically so Temporal can detect worker failures.
If a worker crashes without a heartbeat, Temporal waits for `heartbeat_timeout` before
rescheduling the activity on another worker.

```python
# Source: docs.temporal.io/develop/python/cancellation
import asyncio
from temporalio import activity


@activity.defn(name="fulfill_order")
async def fulfill_order_activity(state: dict) -> dict:
    try:
        activity.heartbeat("starting fulfillment")
        result = await do_step_one(state)
        activity.heartbeat("step 1 complete")
        result = await do_step_two(result)
        return result
    except asyncio.CancelledError:
        raise  # Must re-raise -- Temporal uses this for cancellation
```

Configure `heartbeat_timeout` in the `execute_activity` call. The timeout must be longer than
the heartbeat interval — if the activity does not heartbeat within `heartbeat_timeout`, Temporal
marks the activity as failed and reschedules it:

```python
# In _execute_task, add heartbeat_timeout alongside start_to_close_timeout:
await workflow.execute_activity(
    step.action, state,
    start_to_close_timeout=timedelta(seconds=step.timeout_seconds),
    heartbeat_timeout=timedelta(seconds=30),  # Worker must heartbeat every 30s or less
    retry_policy=retry_policy,
)
```

**Heartbeat interval guideline:** Set `heartbeat_timeout` to 2–3x the expected time between
`activity.heartbeat()` calls. For a step that heartbeats every 10 seconds, set
`heartbeat_timeout=timedelta(seconds=30)`.

**`asyncio.CancelledError` must be re-raised.** Temporal signals activity cancellation by
raising `CancelledError` inside the activity coroutine. Swallowing it prevents Temporal from
marking the activity as cancelled and breaks the cancellation flow.

---

## Section 4: Anti-Patterns

**TracingInterceptor on Client only — no worker spans.**
Passing `TracingInterceptor` to `Client.connect()` but not to `Worker()` produces client-side
spans (workflow start, signal send) but no activity spans. The trace shows the workflow start
span with no children. Always pass the same instance to both sides.

**OTel provider configured after `Client.connect()` — no-op tracer.**
`TracingInterceptor()` captures `opentelemetry.trace.get_tracer()` at construction time. If
`trace.set_tracer_provider(provider)` is called after `Client.connect()`, the interceptor
holds the default no-op tracer and produces no spans. Call `configure_tracing()` before any
Temporal client code.

**Hardcoding an exporter backend — breaks backend-agnostic principle.**
Hardcoding `OTLPSpanExporter(endpoint="http://datadog-agent:4317")` inside `configure_tracing`
couples the instrumentation code to a specific backend. Accept the exporter as a parameter
(as shown in Section 1) so the caller can inject `ConsoleSpanExporter` in development and
`OTLPSpanExporter` in production without modifying instrumentation code.

**Missing `asyncio.CancelledError` re-raise in heartbeating activities.**
Catching `CancelledError` without re-raising prevents Temporal from detecting activity
cancellation. The activity appears to complete successfully even when it was cancelled. Always
re-raise `CancelledError` in heartbeating activities.

---

## Order Processing Example with Observability

Full activity with custom span, correlation ID, and heartbeat:

```python
from opentelemetry import trace
from temporalio import activity
from workflows.registry.actions import registry
import asyncio
from datetime import timedelta

tracer = trace.get_tracer(__name__)


@activity.defn(name="fulfill_order")
async def fulfill_order_activity(state: dict) -> dict:
    """Fulfill order with heartbeat for long-running operations."""
    info = activity.info()
    try:
        with tracer.start_as_current_span("fulfill_order.domain") as span:
            span.set_attribute("order_id", state.get("order_id", "unknown"))
            span.set_attribute("workflow.step", "fulfill-order")
            span.set_attribute("correlation_id", f"{info.workflow_id}/{info.run_id}")

            activity.heartbeat("starting fulfillment")
            fn = registry.get("fulfill_order")
            result = await fn(state)
            activity.heartbeat("fulfillment complete")

            span.set_attribute("fulfillment.status", result.get("fulfilled", False))
            return result
    except asyncio.CancelledError:
        raise  # Must re-raise — Temporal uses this for cancellation
```

Worker setup with tracing (all configuration as parameters, no `os.environ`):

```python
from workflows.adapters.temporal_adapter import DSLWorkflow
from workflows.adapters.activities import (
    validate_order_activity,
    process_payment_activity,
    fulfill_order_activity,
    send_confirmation_activity,
)
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions


async def create_worker_with_tracing(
    host: str,
    port: int,
    namespace: str,
    task_queue: str,
    exporter=None,
) -> Worker:
    """Create worker with OTel tracing enabled.

    Args:
        host: Temporal server hostname.
        port: Temporal server port.
        namespace: Temporal namespace.
        task_queue: Task queue name.
        exporter: OTel SpanExporter. Defaults to ConsoleSpanExporter.
    """
    # configure_tracing MUST come before Client.connect()
    tracing = configure_tracing(exporter)

    client = await Client.connect(
        f"{host}:{port}",
        namespace=namespace,
        interceptors=[tracing],
    )

    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[DSLWorkflow],
        activities=[
            validate_order_activity,
            process_payment_activity,
            fulfill_order_activity,
            send_confirmation_activity,
        ],
        interceptors=[tracing],
        workflow_runner=SandboxedWorkflowRunner(
            restrictions=SandboxRestrictions.default.with_passthrough_modules("pydantic")
        ),
    )
    return worker
```
