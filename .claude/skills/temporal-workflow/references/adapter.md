# Temporal Adapter Layer Reference

The adapter layer is the ONLY layer that imports from the Temporal SDK. It translates DSL
concepts into Temporal execution primitives, implementing the `TemporalAdapter` that satisfies
the `WorkflowEngine` interface and the `DSLWorkflow` class that interprets `WorkflowDefinition`
step-by-step. All other layers — domain, DSL, and port — are adapter-free.

See stacks/{stack}/ for the concrete adapter implementation in your language.

---

## Section 1: DSL-to-Temporal Mapping Table (DSL-05)

Each DSL concept maps to a specific Temporal primitive. The translation is one-directional: DSL
defines what the workflow does, Temporal determines how it executes.

| DSL Concept | DSL Field / Type | Temporal Concept | Temporal API | Notes |
|-------------|-----------------|-----------------|-------------|-------|
| `WorkflowDefinition` | `id`, `version`, `steps`, `transitions` | Workflow class | `DSLWorkflow` interprets the definition at runtime | One generic class handles any `WorkflowDefinition` |
| `StepDefinition` type=`"task"` | `action` (str), `timeout_seconds`, `retry_policy` | Activity | `workflow.execute_activity(step.action, ...)` | Activity is a thin shell delegating to the action registry |
| `StepDefinition` type=`"parallel"` | Successor steps via transitions | Async fan-out | Concurrent activity execution via gather | All successor steps execute simultaneously |
| `StepDefinition` type=`"decision"` | `Transition.condition` strings | Conditional flow | Condition strings evaluated against current state | Pure routing node; no activity called |
| `StepDefinition` type=`"event"` | Implicit signal wait | Signal + wait condition | Signal handler + `wait_condition(lambda)` | Workflow suspends until signal arrives |
| `Transition` | `from_step`, `to_step`, `condition` | Code flow | Graph traversal in the workflow run loop | Decision steps evaluate conditions; others take first |
| `RetryPolicy` | `max_attempts`, `initial_interval_seconds`, `backoff_coefficient`, `max_interval_seconds` | SDK RetryPolicy | Mapped 1:1 in task execution | See field mapping table in Section 7 |
| `StepDefinition` type=`"event"` signal | Implicit signal wait | Signal handler | `receive_signal` decorated handler | Unblocks `wait_condition` |

**Key mapping insight:** A single `WorkflowDefinition` is not converted into a static workflow
class — instead, `DSLWorkflow` is a generic interpreter class. The `WorkflowDefinition` instance
is passed as an argument to `DSLWorkflow.run()` at execution time, and the workflow traverses
the graph dynamically. This preserves DSL portability: the same `DSLWorkflow` class handles any
`WorkflowDefinition` without requiring code changes.

---

## Section 2: DSLWorkflow — Generic Workflow Interpreter (ADPT-02)

`DSLWorkflow` is the workflow-decorated class that Temporal executes. It receives a
`WorkflowDefinition` and an initial state dict, then traverses the step graph. The workflow
never calls domain services directly — it delegates all work to registered activities.

### Run Loop (abstract algorithm)

```
function run(defn: WorkflowDefinition, input: dict) -> dict:
  state = copy of input
  build step_map: step_id -> StepDefinition
  build transition_map: from_step_id -> [Transition, ...]
  find entry_id: the step with no incoming transitions

  current_id = entry_id
  while current_id is not null:
    step = step_map[current_id]
    state = await execute_step(step, state, transition_map)
    update state snapshot (for query handler)
    outgoing = transition_map[current_id] or []
    current_id = select_next(step, state, outgoing)

    if is_continue_as_new_suggested():
      continue_as_new(args=[defn, {**state, "_continued_from": current_run_id}])

  return state
```

### Step Dispatch

| Step Type | Behavior |
|-----------|----------|
| `"task"` | Call `execute_task(step, state)` — runs the named activity |
| `"parallel"` | Call `execute_parallel(step, state, transition_map)` — fan out to successor steps concurrently |
| `"decision"` | Return state unchanged; routing happens in `select_next` via condition evaluation |
| `"event"` | Call `execute_event(step, state)` — suspend until signal arrives |

### Task Execution

```
function execute_task(step, state) -> dict:
  build SDK RetryPolicy from step.retry_policy if present (see Section 7)
  return await workflow.execute_activity(
    step.action,
    state,
    start_to_close_timeout = step.timeout_seconds,
    retry_policy = built retry policy or null,
  )
```

### Parallel Execution

```
function execute_parallel(step, state, transition_map) -> dict:
  outgoing = transition_map[step.id] or []
  branch_ids = [t.to_step for t in outgoing]
  tasks = [execute_activity(branch_id, state, timeout) for branch_id in branch_ids]
  results = await gather(*tasks)
  merged = copy of state
  for result in results:
    merged.update(result)   // last-write-wins per key
  return merged
```

Parallel branches are discovered from the transition map, not from a separate field on
`StepDefinition`. The DSL model has no `parallel_actions` field.

### Event Execution

```
function execute_event(step, state) -> dict:
  reset _signal_received = false
  await wait_condition(lambda: _signal_received, timeout=timedelta(hours=72))
  reset _signal_received = false
  return merge(state, _signal_payload)
```

The 72-hour timeout causes the workflow to fail fast if no signal arrives within the SLA window,
rather than waiting indefinitely.

### Signal Handler

```
signal handler receive_signal(payload: dict) -> void:
  _signal_received = true
  _signal_payload = copy of payload
```

### Query Handler

```
query handler get_state() -> dict:
  return copy of _state_snapshot
```

---

## Section 3: TemporalAdapter — WorkflowEngine Satisfaction (ADPT-01)

`TemporalAdapter` satisfies the `WorkflowEngine` interface through structural subtyping —
no inheritance from the interface is required. It wraps the Temporal client and translates
domain calls into Temporal client API calls.

### Method Behaviors

**`start_workflow(workflow, input, workflow_id=None) -> WorkflowHandle`**

Start a `DSLWorkflow` execution via the Temporal client. Pass the `WorkflowDefinition` and
initial state as arguments. Catch engine-level exceptions and re-raise as domain exceptions
(`WorkflowError`, `ActivityError`, `WorkflowTimeoutError`) before returning.

When `workflow_id` is null, generate a stable identifier using the workflow definition ID and
a unique suffix (e.g., UUID or timestamp).

**`signal(workflow_id, signal_name, payload) -> void`**

Obtain a workflow handle from the Temporal client by `workflow_id`, then send the signal.

**`query(workflow_id, query_name) -> any`**

Obtain a workflow handle from the Temporal client by `workflow_id`, then issue the query.

---

## Section 4: ActionRegistry — Dual Registration (AREG-03)

The ActionRegistry is a domain-layer concern. Worker activity registration is a Temporal-layer
concern. A function in the ActionRegistry is NOT automatically registered with the Worker — both
registrations are required.

```
ActionRegistry.register(name, fn)   <- Domain layer: resolve name -> callable
Worker(activities=[fn, ...])        <- Temporal layer: register activity with the engine
```

The thin-shell activity is the bridge between the two registrations:

```
Activity shell for "validate_order":
  resolve fn = registry.get("validate_order")
  return await fn(state)
```

- The Temporal activity name must match the `@registry.action` name exactly.
- The activity resolves from the registry at invocation time; registration happens at import time.
- The thin-shell activity lives in the adapter layer — it is the ONLY place that combines a
  Temporal activity decorator with registry resolution.

**Anti-pattern — business logic inside the activity:**

```
// WRONG: branching and multiple service calls inside the activity
activity "process_payment"(state):
  order = OrderService.get(state.order_id)
  if order.total > 1000:
    result = PaymentService.charge_high_value(order)
  else:
    result = PaymentService.charge_standard(order)
  NotificationService.notify(order.id, result)
  return {**state, payment_id: result.id}
```

```
// CORRECT: one call to the registered action
activity "process_payment"(state):
  fn = registry.get("process_payment")
  return await fn(state)
```

The business logic belongs in the action function registered in the ActionRegistry, not in the activity shell.

---

## Section 5: Worker Setup

Worker assembly happens in the **worker app** (the deployable service), not in the workflows
domain. Each domain exports an `ACTIVITIES` list from its `activities.py`. The worker app
imports these lists and creates one `Worker` per task queue.

### Worker Assembly (in the app layer)

```
// Worker app: imports activity lists from each domain
import TRIAGE_ACTIVITIES from deals/triage/activities
import KNOWLEDGE_ACTIVITIES from knowledge_base/activities
import SALES_ACTIVITIES from sales_interactions/activities

function main():
  configure_tracing()             // must come before client.connect (see observability.md)
  client = await Client.connect(host, port, namespace, interceptors=[tracing])

  workers = [
    Worker(client, task_queue="deal-triage", workflows=[DSLWorkflow],
           activities=TRIAGE_ACTIVITIES, interceptors=[tracing], sandbox=...),
    Worker(client, task_queue="knowledge-ingestion", workflows=[DSLWorkflow],
           activities=KNOWLEDGE_ACTIVITIES, interceptors=[tracing], sandbox=...),
    Worker(client, task_queue="sales-interaction", workflows=[DSLWorkflow],
           activities=SALES_ACTIVITIES, interceptors=[tracing], sandbox=...),
  ]
```

The sandbox passthrough for the model validation library is required because
the `WorkflowDefinition` is deserialized inside the workflow sandbox during replay. Without the
passthrough, sandbox restrictions prevent the model library from initializing.

In the Ezra monorepo, a single worker process runs all task queues to minimize costs. To
split a high-demand workflow into its own worker later, create a new worker app that imports
only that domain's `ACTIVITIES`. See [ezra-conventions.md](ezra-conventions.md) for the full
worker startup sequence.

---

## Section 6: Import Boundary Enforcement

Enforce at the repository level that the Temporal SDK is never imported outside the adapter
layer. Create a CI test that:

1. Scans all source files outside `workflows/adapters/` and `workers/`.
2. Parses the AST of each file.
3. Fails if any import statement references the Temporal SDK package.

This catches violations at code review time rather than at runtime.

See stacks/{stack}/ for the concrete import boundary test implementation.

**Verification:**

Run the import boundary test immediately after creating the adapter:

```
run test suite: tests/test_import_boundary
```

---

## Section 7: RetryPolicy Field Mapping (Phase 3)

Map DSL `RetryPolicy` fields to the Temporal SDK `RetryPolicy` type 1:1.

| DSL Field | Temporal Field | Notes |
|-----------|---------------|-------|
| `max_attempts` | `maximum_attempts` | Direct mapping |
| `initial_interval_seconds` | `initial_interval` | Convert seconds to duration type |
| `backoff_coefficient` | `backoff_coefficient` | Direct mapping |
| `max_interval_seconds` | `maximum_interval` | Convert to duration type; null when not set |
| `non_retryable_error_types` | `non_retryable_error_types` | List of exception class name strings |

The `non_retryable_error_types` field is added in Phase 3 as a fifth field on the DSL
`RetryPolicy` model. It lists exception class names as strings — not class references — that
Temporal will not retry after activity failure.

Extract the retry policy mapping into a standalone helper function (`_build_retry_policy`) in
the adapter. The helper is the single source of retry translation logic.

---

## Section 8: Typed Signal Payloads (Phase 3)

Define signal payload models in the DSL layer, not in the adapter. Keeping the model in the
DSL layer means the adapter imports from DSL — never the reverse.

### ApprovalPayload Schema

| Field | Type | Description |
|-------|------|-------------|
| `approved` | boolean | Whether the step was approved |
| `approver` | string | Identity of the approver |

Upgrade the signal handler in `DSLWorkflow` from `payload: dict` to `payload: ApprovalPayload`
(or the equivalent typed model). The typed parameter allows the SDK to deserialize and validate
the signal payload before the handler runs.

### Signal with Start

When a workflow may not yet be running when a signal is sent, use signal-with-start: the client
starts the workflow if it is not running, then immediately delivers the signal. This prevents
the race condition where the signal arrives before the workflow is scheduled.

See stacks/{stack}/ for the concrete signal-with-start implementation.

---

## Section 9: Integration Checkpoint

Start a local Temporal server and run the order processing workflow through the full stack.

```
temporal server start-dev
```

Run the order processing workflow end-to-end:

```
DSL definition -> TemporalAdapter.start_workflow
  -> DSLWorkflow interpreter
    -> activity execution (validate -> charge -> fulfill -> notify)
      -> accumulated result
```

Confirm all Phase 1 DSL checkpoint tests still pass after wiring the adapter. The DSL layer
must not change to accommodate the adapter.

See stacks/{stack}/ for the full integration example.

---

## Section 10: Verification Checkpoint

After completing the adapter layer, verify the full stack:

1. The adapter class implements all three interface methods (`start_workflow`, `signal`, `query`).
2. The import boundary test passes — no SDK imports outside adapter/worker directories.
3. The worker module imports without error.
4. A workflow runs end-to-end through the adapter with the order processing example.
5. All Phase 1 DSL checkpoint tests still pass (the DSL layer did not change).

See stacks/{stack}/ for the concrete test suite.
