# Engine Port Layer Reference

The port layer defines the abstraction boundary between domain code and any workflow engine
implementation. This layer is Temporal-free — import only from the standard library and the
DSL layer. The adapter layer (Phase 2) satisfies the interface without the domain layer ever
depending on the Temporal SDK.

See stacks/{stack}/ for the concrete port implementation in your language.

---

## Section 1: WorkflowEngine Interface (PORT-01, PORT-02)

Define `WorkflowEngine` as a structural interface / protocol. Structural subtyping means
`TemporalAdapter` satisfies the interface without inheriting from it or importing from this
file. Domain code depends on this interface — never on the concrete adapter.

Three async methods form the complete engine interface (per D-01). Every adapter — Temporal,
local, test double — must implement all three.

### Method Signatures

**`start_workflow(workflow, input, workflow_id=None) -> WorkflowHandle`**

Start a workflow from a DSL definition.

| Parameter | Type | Description |
|-----------|------|-------------|
| `workflow` | WorkflowDefinition | The graph to execute |
| `input` | dict | Initial state dictionary passed to the first step |
| `workflow_id` | string or null | Optional stable identifier; adapter generates one when null |

Returns: `WorkflowHandle` typed to the workflow result type.

**`signal(workflow_id, signal_name, payload) -> void`**

Send a named signal to a running workflow.

| Parameter | Type | Description |
|-----------|------|-------------|
| `workflow_id` | string | Identifier of the target workflow instance |
| `signal_name` | string | Name of the signal as registered in the workflow |
| `payload` | dict | Signal data; must be JSON-serializable |

**`query(workflow_id, query_name) -> any`**

Query the current state of a running workflow.

| Parameter | Type | Description |
|-----------|------|-------------|
| `workflow_id` | string | Identifier of the target workflow instance |
| `query_name` | string | Name of the query handler registered in the workflow |

Returns: The query result; type depends on the query handler.

### Import Boundary

This file contains zero engine-SDK imports. Any class that implements all three async methods
satisfies the interface through structural subtyping — no inheritance from the interface is
required. Domain code verifies conformance at runtime using the runtime-checkable protocol
mechanism provided by the stack's type system.

---

## Section 2: WorkflowHandle Interface (per D-03)

`WorkflowHandle[T]` is returned by `start_workflow`. Callers interact with a running workflow
instance through the handle — send signals, issue queries, and await the final result.

Generic over T — the result type of the workflow. Use `WorkflowHandle[dict]` when the result
type is the accumulated state dictionary (the common case for DSL-driven workflows).

### Method Signatures

**`signal(signal_name, payload) -> void`**

Send a named signal to this workflow instance. Same semantics as `WorkflowEngine.signal` but
scoped to the handle's workflow instance.

**`query(query_name) -> any`**

Query the current state of this workflow instance.

**`result() -> T`**

Await the final result of this workflow instance. Blocks until the workflow reaches a terminal
state. Raises domain exceptions (see Section 3) on failure.

---

## Section 3: Domain Exception Hierarchy (per D-02)

Define all workflow exceptions in the port layer. The adapter catches engine-SDK exceptions
and translates them into domain exceptions before re-raising. Domain code catches only these
exceptions — never SDK exception types.

### Exception Hierarchy

```
WorkflowError (base)
  |-- ActivityError
  |-- WorkflowTimeoutError
```

**`WorkflowError`** — base class for all workflow engine errors.

| Attribute | Type | Description |
|-----------|------|-------------|
| `message` | string | Human-readable description of the failure |
| `workflow_id` | string or null | Identifier of the workflow instance that failed |

**`ActivityError`** — raised when an activity fails after all retries.

| Attribute | Type | Description |
|-----------|------|-------------|
| `activity_name` | string | Name of the activity that failed |
| `workflow_id` | string or null | Identifier of the enclosing workflow instance |

**`WorkflowTimeoutError`** — raised when a workflow exceeds its execution timeout.

Inherits `message` and `workflow_id` from `WorkflowError`.

Domain code catches `WorkflowError` to handle any engine failure. Catch `ActivityError`
specifically to distinguish activity failures. Catch `WorkflowTimeoutError` to implement
timeout-specific recovery.

---

## Section 4: Optional Extension Interfaces (per D-01)

These interfaces extend the core `WorkflowEngine` interface with advanced lifecycle operations.
Wire them in Phase 3 when production hardening requires them.

**`WorkflowManagement`** — lifecycle control for running workflow instances.

| Method | Parameters | Description |
|--------|-----------|-------------|
| `cancel(workflow_id)` | string | Request cooperative cancellation; workflow can perform cleanup |
| `terminate(workflow_id, reason)` | string, string | Forcibly terminate immediately; no cleanup |

**`WorkflowObservation`** — introspection into running workflow instances.

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `describe(workflow_id)` | string | dict | Snapshot of current state including status, times, metadata |

---

## Section 5: Running Example — Order Processing

Domain code calls through `WorkflowEngine` without knowing whether the engine is
`TemporalAdapter`, an in-memory stub, or a test double.

### Submitting an Order (conceptual)

```
async submit_order(engine: WorkflowEngine, order_id: string) -> dict:
  define order_workflow (validate -> charge -> fulfill -> notify)

  try:
    handle = await engine.start_workflow(
      order_workflow,
      input: {"order_id": order_id},
      workflow_id: "order-{order_id}",
    )
    return await handle.result()

  on ActivityError as e:
    raise domain error: "activity '{e.activity_name}' failed"

  on WorkflowTimeoutError as e:
    raise domain error: "workflow timed out"
```

### Signaling a Running Workflow

```
await engine.signal(
  workflow_id: "order-12345",
  signal_name: "payment_approved",
  payload: {"approved_by": "payment-gateway", "transaction_id": "txn-789"},
)
```

### Querying Workflow State

```
status = await engine.query(
  workflow_id: "order-12345",
  query_name: "order_status",
)
```

### Using a Typed Handle

```
handle: WorkflowHandle[dict] = await engine.start_workflow(order_workflow, {"order_id": "12345"})
await handle.signal("payment_approved", {"transaction_id": "txn-789"})
result: dict = await handle.result()
assert result["status"] == "completed"
```

---

## Section 6: Verification Checkpoint

After building the port layer, verify it before proceeding to the adapter. Run the port
checkpoint tests. All tests must pass and the import boundary test must confirm the port file
is engine-SDK-free.

### Required Tests

1. **Protocol conformance** — a class implementing all three async methods satisfies `WorkflowEngine`; verify with the runtime-checkable protocol check.
2. **Incomplete class does not satisfy** — a class missing `signal` and `query` does not satisfy `WorkflowEngine`.
3. **Domain exceptions instantiate and catch** — all three exception types construct correctly and can be caught as `WorkflowError`.
4. **Port layer import boundary** — parse the port file's AST and confirm no engine-SDK package names appear in any import statement.

See stacks/{stack}/ for the concrete test file.
