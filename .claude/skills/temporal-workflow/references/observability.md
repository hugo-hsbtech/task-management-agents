# Observability Reference

OpenTelemetry tracing for Temporal workflows. This reference covers TracingInterceptor setup,
custom business spans in activities, correlation IDs, and activity heartbeats. The observability
layer is backend-agnostic — configure any OTel-compatible exporter (OTLP, Console, etc.)
without changing the instrumentation code.

See stacks/{stack}/ for the concrete tracing setup implementation in your language.

---

## Section 1: TracingInterceptor Setup (PROD-03)

`TracingInterceptor` instruments all Temporal operations automatically — workflow execution,
activity scheduling, and signal handling each produce spans with trace context propagated
through the event history. Configure the OTel provider once, then pass the same
`TracingInterceptor` instance to both the Temporal client and the Temporal worker.

### Critical Ordering Requirement

The OTel provider MUST be configured BEFORE the Temporal client connects. `TracingInterceptor`
captures the tracer at construction time. If the provider is registered after the interceptor
is constructed, the interceptor holds a no-op tracer and produces no spans.

### Setup Algorithm

```
function configure_tracing(exporter=null) -> TracingInterceptor:
  provider = TracerProvider()
  processor = SimpleSpanProcessor(exporter or ConsoleSpanExporter())
  provider.add_span_processor(processor)
  set_global_tracer_provider(provider)
  return TracingInterceptor()
```

For production: pass an `OTLPSpanExporter` pointing at your OTel collector endpoint.
For development: use `ConsoleSpanExporter` (the default) which prints spans to stdout.
Accept the exporter as a parameter — never hardcode a backend-specific exporter.

### Wiring to Client and Worker

Pass the returned interceptor to BOTH the Temporal client and the Temporal worker:

```
tracing = configure_tracing()   // MUST come before client.connect

client = await Client.connect(
  host,
  namespace=namespace,
  interceptors=[tracing],       // client-side trace context propagation
)

worker = Worker(
  client,
  task_queue=task_queue,
  workflows=[DSLWorkflow],
  activities=[...],
  interceptors=[tracing],       // worker-side span propagation
  ...
)
```

`TracingInterceptor` implements both the client interceptor interface and the worker interceptor
interface — a single instance handles both sides. Create it once and share the reference.

Omitting either side produces an incomplete trace: client-side spans appear but activity spans
are missing, or vice versa.

---

## Section 2: Custom Business Spans (PROD-03)

`TracingInterceptor` instruments Temporal operations automatically. For step-level business
logic — payment status, order validation result, domain-specific attributes — add custom spans
inside activity functions using the standard OTel tracer API.

### Pattern (conceptual)

```
// In an activity function:
tracer = get_tracer(module_name)   // retrieve once at module level

activity "process_payment"(state: dict) -> dict:
  info = activity.info()           // workflow_id, run_id from the Temporal runtime
  with tracer.start_span("process_payment.domain") as span:
    span.set_attribute("order_id", state.order_id)
    span.set_attribute("workflow.step", "process-payment")
    span.set_attribute("correlation_id", "{info.workflow_id}/{info.run_id}")
    result = await registry.get("process_payment")(state)
    span.set_attribute("payment.status", result.paid)
    return result
```

### Correlation ID Pattern

`activity.info()` exposes `workflow_id` and `run_id` — the two fields that identify a specific
execution in Temporal. Combine them as `"{workflow_id}/{run_id}"` to correlate business spans
with Temporal execution records in the same trace.

### Span Naming Convention

Use `"{activity_name}.domain"` for business spans that run inside a Temporal activity. This
distinguishes custom spans from the auto-instrumented Temporal spans (`StartActivity`,
`RunActivity`, etc.) in the same trace.

### Attribute Guidelines

- Include the domain entity ID (e.g., `order_id`) on every step span for cross-span correlation.
- Include `workflow.step` matching the `StepDefinition.id` for traceability back to the DSL.
- Add result-status attributes after the domain call completes, not before.

---

## Section 3: Activity Heartbeats (PROD-03)

Long-running activities must heartbeat periodically so Temporal can detect worker failures. If
a worker crashes without a heartbeat, Temporal waits for `heartbeat_timeout` before
rescheduling the activity on another worker.

### Heartbeat Pattern

```
activity "fulfill_order"(state: dict) -> dict:
  try:
    heartbeat("starting fulfillment")
    result = await do_step_one(state)
    heartbeat("step 1 complete")
    result = await do_step_two(result)
    return result
  on CancelledError:
    raise   // MUST re-raise — Temporal uses this for cancellation
```

### Heartbeat Timeout Configuration

Set `heartbeat_timeout` in the activity execution call alongside `start_to_close_timeout`.
The timeout must be longer than the heartbeat interval — if the activity does not heartbeat
within `heartbeat_timeout`, Temporal marks the activity as failed and reschedules it.

**Guideline:** Set `heartbeat_timeout` to 2–3x the expected time between heartbeat calls. For
an activity that heartbeats every 10 seconds, set `heartbeat_timeout` to 30 seconds.

```
workflow.execute_activity(
  step.action,
  state,
  start_to_close_timeout = step.timeout_seconds,
  heartbeat_timeout = 30 seconds,
  retry_policy = retry_policy,
)
```

### CancelledError Must Be Re-Raised

Temporal signals activity cancellation by raising `CancelledError` inside the activity
coroutine. Swallowing it prevents Temporal from marking the activity as cancelled and breaks
the cancellation flow. Always re-raise `CancelledError` in heartbeating activities.

---

## Section 4: Anti-Patterns

**TracingInterceptor on client only — no worker spans.**
Passing `TracingInterceptor` to the client but not to the worker produces client-side spans
(workflow start, signal send) but no activity spans. The trace shows the workflow start span
with no children. Always pass the same instance to both sides.

**OTel provider configured after client connect — no-op tracer.**
`TracingInterceptor` captures the tracer at construction time. If `set_tracer_provider(provider)`
is called after the client connects, the interceptor holds the default no-op tracer. Call
`configure_tracing()` before any Temporal client code.

**Hardcoding an exporter backend — breaks backend-agnostic principle.**
Hardcoding a specific backend exporter endpoint inside `configure_tracing` couples the
instrumentation code to a specific observability backend. Accept the exporter as a parameter
so the caller can inject `ConsoleSpanExporter` in development and `OTLPSpanExporter` in
production without modifying instrumentation code.

**Missing CancelledError re-raise in heartbeating activities.**
Catching `CancelledError` without re-raising prevents Temporal from detecting activity
cancellation. The activity appears to complete successfully even when it was cancelled. Always
re-raise `CancelledError` in heartbeating activities.
