# Persistence and Versioning — Python Implementation

For concepts, patterns, and design decisions, see `references/persistence.md`.

This file contains the complete Python implementation: `WorkflowInstance` and `StepRecord`
Pydantic v2 models (schema-only, no storage prescribed), `temporal_workflow_id` lifecycle,
`workflow.patched()` three-phase migration code with DSLWorkflow-specific naming,
`workflow.continue_as_new()` with `is_continue_as_new_suggested()` trigger, and the order
processing running example.

---

## Section 1: WorkflowInstance and StepRecord Models

`WorkflowInstance` is a schema-only Pydantic model. It represents the application's own record
of a workflow execution and lives entirely outside Temporal. `temporal_workflow_id` is the
foreign key that links a `WorkflowInstance` record to the Temporal execution history.

No storage implementation is prescribed. Store `WorkflowInstance` in any database, ORM, or
persistence layer appropriate to the project — SQL, document store, key-value store, or
in-memory for testing.

```python
# Source: DRAFT.md persistence model + CONTEXT.md D-13 (schema-only, no storage prescribed)
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
from datetime import datetime


WorkflowStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class StepRecord(BaseModel):
    """Append-only record of a completed step.

    Fields:
        step_id: Matches StepDefinition.id from the WorkflowDefinition.
        step_type: The step type ("task", "decision", "parallel", "event").
        status: Outcome of this step execution.
        state_snapshot: Full accumulated state dict after this step completed.
        timestamp: UTC timestamp when this step completed.
    """
    step_id: str
    step_type: str
    status: Literal["completed", "failed"]
    state_snapshot: dict[str, Any]
    timestamp: datetime


class WorkflowInstance(BaseModel):
    """Domain-side record of a workflow execution.

    Stored outside Temporal in the application's own database.
    temporal_workflow_id is the FK linking this record to the Temporal execution.
    No storage implementation prescribed -- use any database, ORM, or persistence layer.

    Fields:
        id: Application-generated UUID for this instance.
        definition_id: WorkflowDefinition.id this instance runs.
        version: WorkflowDefinition.version at start time. Store at creation —
            the definition may evolve while this instance is running.
        status: Current lifecycle state of this workflow instance.
        state: Current accumulated state dict (mirrors DSLWorkflow._state_snapshot).
        history: Step-level history. Append-only — never mutate or remove records.
        temporal_workflow_id: FK to Temporal workflow execution. Set after
            start_workflow() succeeds. None while status="pending".
        created_at: UTC timestamp when the instance was created.
        updated_at: UTC timestamp of the most recent state update.
    """
    id: str = Field(description="Application-generated UUID for this instance")
    definition_id: str = Field(description="WorkflowDefinition.id this instance runs")
    version: str = Field(description="WorkflowDefinition.version at start time")
    status: WorkflowStatus = Field(default="pending")
    state: dict[str, Any] = Field(default_factory=dict, description="Current accumulated state")
    history: list[StepRecord] = Field(
        default_factory=list,
        description="Step-level history. Append only.",
    )
    temporal_workflow_id: Optional[str] = Field(
        default=None,
        description="FK to Temporal workflow execution. Set after start_workflow() succeeds.",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
```

**`temporal_workflow_id` lifecycle:**
1. Create the `WorkflowInstance` with `status="pending"` and `temporal_workflow_id=None`.
2. Call `TemporalAdapter.start_workflow()`.
3. If it succeeds: set `temporal_workflow_id` to the workflow ID and `status="running"`.
4. If it raises: the instance stays in `"pending"` status with no `temporal_workflow_id`.

**`history` is append-only.** Each `StepRecord` captures the state snapshot after step
completion. Never mutate or remove records — the history log supports audit, debugging, and
replay analysis.

**`definition_id` links to `WorkflowDefinition.id`.** Store both `definition_id` and `version`
at instance creation time, because the definition may evolve while old instances are still
running.

---

## Section 2: Versioning with `workflow.patched()`

`workflow.patched()` inserts a marker into the Temporal event history. This allows two versions
of `DSLWorkflow.run()` to coexist during a deployment: new executions take the new code path,
while replaying workflows (re-executing from recorded history) take the old code path.

Deploy versioned code in three phases. All three phases must pass through production before the
patch is fully retired.

**Phase 1 — Deploy alongside old code.** Both code paths must be functionally correct:

```python
# workflows/adapters/temporal_adapter.py — inside DSLWorkflow.run
# Source: docs.temporal.io/develop/python/versioning
if workflow.patched("add-validation-step-v2"):
    # New code path -- new workflow executions take this branch
    state = await self._execute_task(validation_step_v2, state)
else:
    # Old code path -- replaying history from before the patch takes this branch
    state = await self._execute_task(validation_step_v1, state)
```

**Phase 2 — Deprecate after all pre-patch workflows complete.** `workflow.deprecate_patch()`
logs a warning if any workflow replays with the old history path. This signals that pre-patch
executions are still running and Phase 2 was deployed too early:

```python
workflow.deprecate_patch("add-validation-step-v2")
state = await self._execute_task(validation_step_v2, state)
```

**Phase 3 — Remove markers after retention period.** Once no workflow history references the
patch marker, remove all `workflow.patched()` and `workflow.deprecate_patch()` calls entirely:

```python
state = await self._execute_task(validation_step_v2, state)
```

### DSLWorkflow-Specific patch_id Naming

`DSLWorkflow` is a generic interpreter — patch IDs apply to the interpreter logic, not to the
DSL definition being interpreted. Encode the specific interpreter change in the patch ID.

**Good patch ID names:**
- `"dsl-interpreter-v2-parallel-merge"` — describes the specific interpreter change
- `"order-processing-v2-validation"` — scoped to the workflow and change type

**Bad patch ID names:**
- `"v2"` — ambiguous, will collide with future changes
- `"fix"` — not unique, causes silent incorrect replay if reused

`WorkflowDefinition.version` handles DSL-level versioning separately — bump it when the
workflow graph shape changes. `workflow.patched()` handles interpreter-level versioning.

**Anti-pattern — reusing patch IDs.** Each patch ID is a stable marker. Reusing `"my-fix"` for
a second unrelated change causes old and new workflows to interpret the marker differently,
producing incorrect replay results. Patch IDs must be globally unique and descriptive.

---

## Section 3: `continue_as_new`

Temporal workflows accumulate event history with every activity execution, signal, and state
transition. Event history approaching ~10,000 events causes performance degradation. Use
`continue_as_new` to reset the history while preserving workflow identity — the same
`workflow_id`, a new `run_id`, and a fresh event history.

```python
# Source: docs.temporal.io/develop/python/continue-as-new
# Inside DSLWorkflow.run -- check after each step completes:
if workflow.info().is_continue_as_new_suggested():
    workflow.continue_as_new(
        args=[defn, {**state, "_continued_from": workflow.info().run_id}]
    )
```

`workflow.info().is_continue_as_new_suggested()` returns `True` when the event history
approaches the SDK's internal performance threshold. The exact threshold is managed by the SDK —
do not hardcode an event count. Check the suggestion after every step.

**`_continued_from` audit key:** The `_continued_from` key records which `run_id` this execution
continues from. This provides an audit trail when the `WorkflowInstance` history log is reviewed.
The new execution gets a fresh event history in Temporal, but the domain-side `WorkflowInstance`
record can accumulate records across continuations via `temporal_workflow_id` (the `workflow_id`
remains the same across `continue_as_new` calls).

The `continue_as_new` check integrates directly into `DSLWorkflow.run()` (see
`stacks/python/adapter.md` Section 2 for the full loop):

```python
while current_id is not None:
    step = step_map[current_id]
    state = await self._execute_step(step, state, transition_map)
    self._state_snapshot = state
    outgoing = transition_map.get(current_id, [])
    current_id = self._select_next(step, state, outgoing)

    # Check continue_as_new after each step — never before a step begins
    if workflow.info().is_continue_as_new_suggested():
        workflow.continue_as_new(
            args=[defn, {**state, "_continued_from": workflow.info().run_id}]
        )
```

**Anti-pattern — calling `continue_as_new` inside a signal handler.** Signal handlers may have
queued signals still awaiting processing when `continue_as_new` terminates the current
execution. Those queued signals are dropped. Only call `workflow.continue_as_new()` from the
main `@workflow.run` coroutine after step execution completes and pending signals are drained.

```python
# WRONG — continue_as_new inside signal handler drops queued signals
@workflow.signal
async def receive_signal(self, payload: dict) -> None:
    self._signal_received = True
    self._signal_payload = dict(payload)
    if workflow.info().is_continue_as_new_suggested():
        workflow.continue_as_new(...)  # WRONG: drops queued signals

# CORRECT — continue_as_new only in @workflow.run after step completion
@workflow.run
async def run(self, defn, input):
    ...
    while current_id is not None:
        state = await self._execute_step(step, state, transition_map)
        if workflow.info().is_continue_as_new_suggested():
            workflow.continue_as_new(...)  # Safe: no queued signals dropped here
```

---

## Section 4: Running Example — Order Processing

The order processing workflow illustrates how `WorkflowInstance` links domain state to Temporal
execution.

```python
import uuid
from datetime import datetime, timezone

# 1. Create domain record before starting the Temporal execution
instance = WorkflowInstance(
    id=str(uuid.uuid4()),
    definition_id="order-processing",       # matches WorkflowDefinition.id
    version="1.0",                           # matches WorkflowDefinition.version
    status="pending",
    state={"order_id": "12345"},
    temporal_workflow_id=None,               # not yet started
    created_at=datetime.now(timezone.utc),
)

# 2. Start the Temporal execution via TemporalAdapter
handle = await adapter.start_workflow(
    workflow_def,
    input={"order_id": "12345"},
    workflow_id=f"order-{instance.id}",
)

# 3. Link domain record to Temporal execution
instance.temporal_workflow_id = f"order-{instance.id}"
instance.status = "running"
instance.updated_at = datetime.now(timezone.utc)
# Persist instance to the application database here

# 4. After payment step completes, append to history (append-only)
instance.history.append(StepRecord(
    step_id="process-payment",
    step_type="task",
    status="completed",
    state_snapshot={"order_id": "12345", "paid": True},
    timestamp=datetime.now(timezone.utc),
))
instance.state = {"order_id": "12345", "paid": True}
instance.updated_at = datetime.now(timezone.utc)

# 5. After all steps complete
instance.status = "completed"
instance.state = await handle.result()
instance.updated_at = datetime.now(timezone.utc)
```

`temporal_workflow_id` serves as the join key between the application's own `WorkflowInstance`
table and Temporal's execution records. Use it to correlate workflow status queries
(`adapter.query(temporal_workflow_id, "get_state")`) with the application-side instance.

### Versioning Example — Adding a Validation Step

Adding `validation_step_v2` to the order processing workflow while old instances are still
running:

```python
# Phase 1 — deployed alongside old workers running the v1 path
@workflow.run
async def run(self, defn: WorkflowDefinition, input: dict) -> dict:
    state = dict(input)
    ...
    # Before processing payment, check if v2 validation is enabled for this execution
    if workflow.patched("order-processing-v2-pre-payment-validation"):
        validation_step = StepDefinition(
            id="pre-payment-validation",
            type="task",
            action="validate_payment_method",
        )
        state = await self._execute_task(validation_step, state)
    ...
```

Once all pre-patch workflow instances have completed, move to Phase 2 (`deprecate_patch`),
then Phase 3 (remove markers). Old instances replaying their history will see the same patch
marker decisions recorded in the event history — the code path is determined by the history,
not by the current code.
