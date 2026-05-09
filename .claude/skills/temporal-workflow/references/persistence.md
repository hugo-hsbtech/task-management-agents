# Persistence and Versioning Reference

External state management for Temporal workflows. This reference covers the WorkflowInstance
persistence model (domain-side record linking to Temporal execution), safe versioning with
`workflow.patched()`, and the `continue_as_new` pattern for long-running workflows.

No storage implementation is prescribed — `WorkflowInstance` is a schema-only model that any
database, ORM, or persistence layer can store.

See stacks/{stack}/ for the concrete model and migration implementation in your language.

---

## Section 1: WorkflowInstance Model (PROD-04)

`WorkflowInstance` is a schema-only domain record. It represents the application's own record
of a workflow execution and lives entirely outside Temporal. `temporal_workflow_id` is the
foreign key that links a `WorkflowInstance` record to the Temporal execution history.

No storage implementation is prescribed. Store `WorkflowInstance` in any database, ORM, or
persistence layer appropriate to the project — SQL, document store, key-value store, or
in-memory for testing.

### WorkflowInstance Schema

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | — | Application-generated UUID for this instance |
| `definition_id` | string | — | `WorkflowDefinition.id` this instance runs |
| `version` | string | — | `WorkflowDefinition.version` at start time |
| `status` | enum | `"pending"` | One of: `pending`, `running`, `completed`, `failed`, `cancelled` |
| `state` | dict | {} | Current accumulated state |
| `history` | list of StepRecord | [] | Step-level audit history; append-only |
| `temporal_workflow_id` | string or null | null | FK to Temporal execution; set after `start_workflow()` succeeds |
| `created_at` | datetime | now() | Instance creation timestamp |
| `updated_at` | datetime or null | null | Last update timestamp |

### StepRecord Schema

| Field | Type | Description |
|-------|------|-------------|
| `step_id` | string | The `StepDefinition.id` that completed |
| `step_type` | string | The step type (`task`, `event`, etc.) |
| `status` | enum | `"completed"` or `"failed"` |
| `state_snapshot` | dict | Full accumulated state after this step |
| `timestamp` | datetime | When this step record was appended |

### temporal_workflow_id Lifecycle

1. Create the `WorkflowInstance` with `status="pending"` and `temporal_workflow_id=null`.
2. Call `TemporalAdapter.start_workflow()`.
3. If it succeeds: set `temporal_workflow_id` to the workflow ID returned by the Temporal client, set `status="running"`.
4. If it raises: the instance stays in `"pending"` status with no `temporal_workflow_id`.

### history Is Append-Only

Each `StepRecord` captures the state snapshot after step completion. Never mutate or remove
records — the history log supports audit, debugging, and replay analysis.

### definition_id and version

`definition_id` links to `WorkflowDefinition.id`. Store both `definition_id` and `version` at
instance creation time, because the definition may evolve while old instances are still running.
When the `WorkflowDefinition` changes, use `version` to track which schema version ran.

---

## Section 2: Versioning with workflow.patched() (PROD-05)

`workflow.patched()` inserts a marker into the Temporal event history. This allows two versions
of `DSLWorkflow.run()` to coexist during a deployment: new executions take the new code path,
while replaying workflows (re-executing from recorded history) take the old code path.

Deploy versioned code in three phases. All three phases must pass through production before the
patch is fully retired.

### Phase 1 — Deploy Alongside Old Code

Both code paths must be functionally correct. New workflow executions enter the patched branch;
executions replaying history from before the patch enter the unpatched branch.

```
// Inside DSLWorkflow.run:
if workflow.patched("add-validation-step-v2"):
  // New code path — new workflow executions take this branch
  state = await execute_task(validation_step_v2, state)
else:
  // Old code path — replaying history from before the patch takes this branch
  state = await execute_task(validation_step_v1, state)
```

### Phase 2 — Deprecate After All Pre-Patch Workflows Complete

`workflow.deprecate_patch()` logs a warning if any workflow replays with the old history path.
This signals that pre-patch executions are still running and Phase 2 was deployed too early.

```
workflow.deprecate_patch("add-validation-step-v2")
state = await execute_task(validation_step_v2, state)
```

### Phase 3 — Remove Markers After Retention Period

Once no workflow history references the patch marker, remove all `patched()` and
`deprecate_patch()` calls entirely.

```
state = await execute_task(validation_step_v2, state)
```

### DSLWorkflow-Specific Challenge

`DSLWorkflow` is a generic interpreter, not a static per-domain workflow class. Patch IDs apply
to the interpreter logic, not to the DSL definition being interpreted. Encode the specific
interpreter change in the patch ID: `"dsl-interpreter-v2-parallel-merge"` not `"v2"`.
`WorkflowDefinition.version` handles DSL-level versioning separately — bump it when the
workflow graph shape changes.

### Anti-Pattern — Reusing Patch IDs

Each patch ID is a stable marker. Reusing `"my-fix"` for a second unrelated change causes old
and new workflows to interpret the marker differently, producing incorrect replay results. Patch
IDs must be globally unique and descriptive: `"order-processing-v2-validation"`, never `"fix"`
or `"v2"`.

---

## Section 3: continue_as_new (PROD-06)

Temporal workflows accumulate event history with every activity execution, signal, and state
transition. Event history approaching the SDK's internal performance threshold (approximately
10,000 events) causes performance degradation. Use `continue_as_new` to reset the history while
preserving workflow identity — the same `workflow_id`, a new `run_id`, and a fresh event history.

### Trigger Pattern

Check after each step completes inside the `DSLWorkflow.run` loop:

```
// Inside the step execution loop in DSLWorkflow.run:
while current_id is not null:
  step = step_map[current_id]
  state = await execute_step(step, state, transition_map)
  update state snapshot

  if workflow.info().is_continue_as_new_suggested():
    workflow.continue_as_new(
      args=[defn, {**state, "_continued_from": workflow.info().run_id}]
    )

  outgoing = transition_map[current_id] or []
  current_id = select_next(step, state, outgoing)
```

`is_continue_as_new_suggested()` returns true when the event history approaches the SDK's
internal performance threshold. The exact threshold is managed by the SDK — do not hardcode an
event count. Check after every step so the workflow never blocks on completing the current step
after the threshold is crossed.

### _continued_from Key

`_continued_from` in the state dict records which `run_id` this execution continues from. This
provides an audit trail when the `WorkflowInstance` history log is reviewed. The new execution
gets a fresh event history in Temporal, but the domain-side `WorkflowInstance` record
accumulates records across continuations via `temporal_workflow_id` (which remains the same
`workflow_id` across `continue_as_new` calls).

### Anti-Pattern — Calling continue_as_new Inside a Signal Handler

Signal handlers may have queued signals still awaiting processing when `continue_as_new`
terminates the current execution. Those queued signals are dropped. Only call `continue_as_new`
from the main `@workflow.run` coroutine after step execution completes and pending signals
are drained.

---

## Section 4: Running Example — Order Processing

The order processing workflow illustrates how `WorkflowInstance` links domain state to Temporal
execution.

### Instance Lifecycle (conceptual)

```
// 1. Create domain record before starting the Temporal execution
instance = WorkflowInstance(
  id: generate_uuid(),
  definition_id: "order-processing",   // matches WorkflowDefinition.id
  version: "1.0",                      // matches WorkflowDefinition.version
  status: "pending",
  state: {"order_id": "12345"},
  temporal_workflow_id: null,           // not yet started
  created_at: now(),
)
persist(instance)

// 2. Start the Temporal execution via TemporalAdapter
temporal_id = await adapter.start_workflow(
  order_workflow_def,
  input: {"order_id": "12345"},
)

// 3. Link domain record to Temporal execution
instance.temporal_workflow_id = temporal_id
instance.status = "running"
instance.updated_at = now()
persist(instance)

// 4. After payment step completes, append to history (append-only)
instance.history.append(StepRecord(
  step_id: "process-payment",
  step_type: "task",
  status: "completed",
  state_snapshot: {"order_id": "12345", "paid": true},
  timestamp: now(),
))
instance.state = {"order_id": "12345", "paid": true}
instance.updated_at = now()
persist(instance)
```

`temporal_workflow_id` serves as the join key between the application's own `WorkflowInstance`
table and Temporal's execution records. Use it to correlate workflow status queries
(`adapter.query(temporal_workflow_id, "get_state")`) with the application-side instance.
