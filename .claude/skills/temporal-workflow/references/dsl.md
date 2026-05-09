# DSL Layer Reference

The DSL layer defines the workflow graph using plain data models. No Temporal imports.
No infrastructure dependencies. The models are the source of truth for what the workflow
does — the adapter layer (Phase 2) translates them into Temporal execution.

All code in this layer is infrastructure-free. Import only from the standard library and
a validation/schema library appropriate to the stack. Run it, test it, and validate it
before any Temporal server is involved.

See stacks/{stack}/ for the concrete model implementation in your language.

---

## Section 1: Core Models (DSL-01)

Define four core model types. The schema below describes each model as an abstract field table.

### RetryPolicy

Controls retry behavior for a workflow step.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `max_attempts` | integer | 1–100 | Total execution attempts including the first |
| `initial_interval_seconds` | integer | 1–3600 | Delay before the first retry |
| `backoff_coefficient` | float | 1.0–10.0 | Multiplier applied to each subsequent interval |
| `max_interval_seconds` | integer or null | >= initial_interval_seconds | Upper bound on the computed interval |

Cross-field constraint: when `max_interval_seconds` is set, it must be greater than or equal to `initial_interval_seconds`.

### StepDefinition

A single node in the workflow graph.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | string | 1–100 chars, unique within workflow | Identifier for this step |
| `type` | enum | `"task"`, `"decision"`, `"parallel"`, `"event"` | Execution category |
| `action` | string or null | Required for task; forbidden for decision/parallel | Name of the callable registered in the action registry |
| `timeout_seconds` | integer | 1–86400, default 30 | Maximum wall-clock time for this step |
| `retry_policy` | RetryPolicy or null | — | Optional retry configuration |

Cross-field constraints:
- `type="task"` requires `action` to be set.
- `type="decision"` and `type="parallel"` must not define `action`.

### Transition

A directed edge in the workflow graph.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `from_step` | string | Must reference a valid step id | Source step |
| `to_step` | string | Must reference a valid step id | Target step |
| `condition` | string or null | — | Expression evaluated at runtime; transition fires only when true |

### WorkflowDefinition

Complete workflow graph definition.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | string | 1–100 chars | Unique workflow identifier |
| `version` | string | — | Semantic version; increment when graph shape changes |
| `steps` | list of StepDefinition | Step ids must be unique | All nodes in the graph |
| `transitions` | list of Transition | — | All directed edges in the graph |

Customize field names to match the target domain. The schema above uses canonical names — rename `action` to match the project's naming convention if needed.

See stacks/{stack}/ for the concrete model definition with validation.

---

## Section 2: Graph Validation (DSL-02)

Graph validation enforces four structural constraints that prevent runtime failures. Call
`validate_graph` after constructing a `WorkflowDefinition` and before executing it.

### The 4 Constraints

**Constraint 1 — Single entry point.**
Exactly one step must have no incoming transitions. Steps with incoming transitions are identified from the `transitions` list. The set of all step IDs minus the set of steps appearing as `to_step` gives the entry candidates. That set must have exactly one member.

**Constraint 2 — At least one terminal step.**
At least one step must have no outgoing transitions. The set of all step IDs minus the set of steps appearing as `from_step` gives the terminal steps. That set must be non-empty.

**Constraint 3 — No orphan steps.**
All steps must be reachable from the entry point. Run a BFS traversal starting from the entry step, following transitions. The set of reachable steps must equal the full set of step IDs.

BFS algorithm:
1. Build an adjacency map: `from_step -> [to_step, ...]` from the transitions list.
2. Initialize a visited set and a queue containing only the entry step ID.
3. While the queue is non-empty: dequeue a node, add to visited, enqueue each unvisited neighbor.
4. After BFS completes, compute `all_step_ids - visited`. Any remaining IDs are orphans.

**Constraint 4 — No infinite loops without an event break.**
Cycles are allowed only when at least one step in the cycle has `type="event"`. This ensures every loop has a point where the workflow suspends waiting for an external signal, preventing infinite spin.

Detection algorithm (DFS with three-color marking):
- WHITE (0): not yet visited
- GRAY (1): currently on the DFS stack
- BLACK (2): fully explored

When a back edge is detected (a neighbor is GRAY), extract the cycle nodes from the current DFS stack path. If none of the cycle nodes have `type="event"`, raise an error.

### Validation Pipeline

Run all four stages before accepting a workflow as production-ready:

1. **Schema validation** — model construction validates field types, constraints, and cross-field rules. A schema error means the input is malformed.
2. **Graph validation** — `validate_graph()` checks structural integrity: entry point, terminal steps, orphan detection, loop detection. An error here means the workflow graph is logically broken.
3. **Execution constraint validation** — checks that runtime values are within safe bounds: timeout totals, retry backoff ceilings, step count limits. An error here means the workflow would be unreliable.
4. **Action contract validation** — verifies every `action` string referenced in steps has a registered handler. This runs at executor-creation time, not at model-construction time.

See stacks/{stack}/ for the concrete validator implementation.

---

## Section 3: In-Memory Executor (DSL-04)

The in-memory executor runs a `WorkflowDefinition` without any Temporal infrastructure. Use it
to validate that the DSL models and graph are correct before connecting to a Temporal server.

### How It Works

1. Register action handlers by name: `executor.register("action_name", callable)`.
2. Call `executor.run(workflow_definition, initial_state_dict)`.
3. The executor validates the graph (Section 2), then traverses from the entry step.
4. For each `task` step, it resolves the registered callable by the step's `action` name, calls it with the current state dict, and receives an updated state dict.
5. After the terminal step completes, returns the final state with `status: "completed"` added.

### Step Type Handling

The Phase 1 in-memory executor handles `task` steps only. When it encounters `decision`, `parallel`, or `event` step types, it raises a "not implemented" error. The Phase 2 Temporal adapter handles all step types.

### State Flow

State is an accumulated dictionary. Each handler receives the full accumulated state and returns an updated version. Keys set by earlier steps remain available to later steps.

See stacks/{stack}/ for the concrete `InMemoryExecutor` implementation.

---

## Section 4: Running Example — Order Processing

This example is used throughout all phases for consistency. Map concepts to the target domain by substituting step IDs, action names, and field values.

### Graph Structure

```
validate-order --> process-payment --> fulfill-order --> send-confirmation
```

- Entry point: `validate-order` (no incoming transitions)
- Terminal step: `send-confirmation` (no outgoing transitions)
- All steps reachable from entry
- No cycles

### WorkflowDefinition (abstract representation)

```
WorkflowDefinition:
  id: "order-processing"
  version: "1.0"
  steps:
    - id: "validate-order",    type: task, action: "validate_order"
    - id: "process-payment",   type: task, action: "process_payment"
    - id: "fulfill-order",     type: task, action: "fulfill_order"
    - id: "send-confirmation", type: task, action: "send_confirmation"
  transitions:
    - from: "validate-order"    to: "process-payment"
    - from: "process-payment"   to: "fulfill-order"
    - from: "fulfill-order"     to: "send-confirmation"
```

### In-Memory Executor Verification

Register stub handlers for each action, run the executor with `{"order_id": "12345"}`, and assert:
- `result["status"] == "completed"`
- `result["validated"] == true`
- `result["paid"] == true`
- `result["fulfilled"] == true`
- `result["confirmed"] == true`

---

## Section 5: Verification Checkpoint

After building the DSL layer, verify it end-to-end before proceeding to Phase 2.

Run the stack's test suite against the DSL checkpoint tests. All tests must pass:

1. **Order processing workflow** — DSL models construct without error, graph validation passes, in-memory executor runs all four steps and returns `status: "completed"`.
2. **Invalid graph — no entry** — a circular graph with all steps having incoming transitions raises a validation error citing "exactly one entry point".
3. **Missing action raises on run** — when a task step's action is not registered, the executor raises an error naming the missing action.
4. **RetryPolicy cross-field constraint** — constructing a `RetryPolicy` with `max_interval_seconds < initial_interval_seconds` raises a validation error.
5. **Task step requires action** — constructing a `StepDefinition` with `type="task"` but no `action` raises a validation error.
6. **Decision step must not have action** — constructing a `StepDefinition` with `type="decision"` and an `action` set raises a validation error.

All six tests must pass before proceeding to Phase 2.

See stacks/{stack}/ for the concrete test file.
