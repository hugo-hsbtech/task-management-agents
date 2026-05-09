# Determinism Rules — Python Implementation

For concepts and background, see `references/determinism.md`.

This file provides the Python-specific sandbox behavior table with all 9 violation categories,
"Use Instead" alternatives using `workflow.*` APIs, and teaching-moment explanations for each.

---

## Why Determinism Matters in Python

Temporal replays workflow code to reconstruct state after a worker restart, upgrade, or failure.
During replay, the workflow function executes again from the beginning, but activity calls and
side effects are replayed from the recorded event history rather than re-executed. Any operation
that produces different output on replay causes workflow divergence and failure.

The Python SDK runs workflow code in a sandbox that intercepts many non-deterministic operations.
However, the sandbox is not exhaustive — some violations cause silent divergence on replay that
is much harder to diagnose than a hard sandbox error.

---

## Sandbox Behavior Table

| Violation | Caught by Sandbox? | Use Instead |
|-----------|--------------------|-------------|
| `random.random()` | YES — raises immediately | `workflow.random().random()` |
| `datetime.datetime.now()` | YES — raises immediately | `workflow.now()` |
| `time.time()` | YES — raises immediately | `workflow.now().timestamp()` |
| `threading.Thread()` | YES — raises immediately | Activity (offload to worker thread) |
| `uuid.uuid4()` | YES — raises immediately | `str(workflow.uuid4())` |
| Iterating `set` or `dict` in branching logic | NO — silent divergence | Convert to `sorted(my_set)` first |
| Global mutable state | NO — silent divergence | Use workflow input/state only |
| `asyncio.sleep()` in workflow | NO — silent divergence | `await workflow.sleep(timedelta(...))` |
| Pydantic validator with I/O | NO — silent divergence | Keep validators pure (no network, no file I/O) |

---

## Teaching-Moment Explanations

### `random.random()`

**What happens:** Produces a different value on each call. On replay, the workflow expects the
exact same random value that was generated during the original execution. A different value causes
the workflow to take a different code path, diverging from the recorded history.

**Why the sandbox catches it:** The Python SDK intercepts `random` module calls at import time
inside the sandbox and raises an error immediately. This gives you a hard failure with a clear
message rather than silent data corruption.

**What to do instead:** Use `workflow.random().random()`. The `workflow.random()` instance is
seeded deterministically from the workflow's event history, producing the same value on every
replay of the same execution point.

```python
# Wrong — different value on every call
import random
value = random.random()  # raises in sandbox

# Correct — same value on replay because history-seeded
value = workflow.random().random()
```

---

### `datetime.datetime.now()`

**What happens:** Returns the current wall-clock time, which differs between the original run
and replay. If workflow branching logic depends on the current time (e.g., "is this a
business-hours request?"), replay may take a different branch than the original execution.

**Why the sandbox catches it:** Wall-clock time is inherently non-deterministic across executions.
The sandbox intercepts `datetime.datetime.now()` and related calls to prevent this class of
divergence.

**What to do instead:** Use `workflow.now()`, which returns the time recorded in the workflow's
event history. On replay, this returns the same recorded time — not the current wall-clock time.

```python
# Wrong — current wall clock time
import datetime
now = datetime.datetime.now()  # raises in sandbox

# Correct — recorded event history time
now = workflow.now()
```

---

### `time.time()`

**What happens:** Same class of violation as `datetime.datetime.now()` — returns the current
epoch timestamp from the OS clock. On replay, this timestamp will differ from the original
execution. Any logic that branches on a timestamp (e.g., "is this request within the SLA
window?") will diverge.

**Why the sandbox catches it:** The sandbox intercepts `time.time()` alongside other wall-clock
calls. The error appears at the point of the call, making it straightforward to fix.

**What to do instead:** Use `workflow.now().timestamp()` to obtain the deterministic timestamp
recorded in the event history.

```python
# Wrong — OS epoch time
import time
ts = time.time()  # raises in sandbox

# Correct — event-history timestamp
ts = workflow.now().timestamp()
```

---

### `threading.Thread()`

**What happens:** Spawning threads inside workflow code introduces execution order
non-determinism. Thread scheduling is controlled by the OS and differs between runs. Two threads
may complete in different orders on the original run versus replay, causing any order-dependent
state transitions to diverge.

**Why the sandbox catches it:** The sandbox intercepts `threading.Thread` directly. Workflow code
runs in a single-threaded asyncio event loop — no worker threads are permitted inside the sandbox.

**What to do instead:** Offload threaded work to activities. Activities run outside the sandbox
in the worker's thread pool and may use any Python library freely — threading, blocking I/O,
network calls.

```python
# Wrong — threading inside workflow code
import threading
t = threading.Thread(target=my_fn)  # raises in sandbox

# Correct — offload to an activity
result = await workflow.execute_activity("my_threaded_action", state, ...)
```

---

### `uuid.uuid4()`

**What happens:** Generates a random UUID using the OS random number generator. On replay, a
different UUID is generated. Any logic that stores the UUID (e.g., in a database) or compares
it will diverge from the original execution.

**Why the sandbox catches it:** The sandbox intercepts `uuid.uuid4()` because it uses the OS
random number generator internally.

**What to do instead:** Use `str(workflow.uuid4())`, which derives a deterministic UUID from
the workflow's event history seed. Same workflow execution point always produces the same UUID.

```python
# Wrong — OS random UUID
import uuid
wf_uuid = uuid.uuid4()  # raises in sandbox

# Correct — deterministic UUID from event history
wf_uuid = str(workflow.uuid4())
```

---

### Iterating `set` or `dict` in branching logic

**What happens:** Python sets have no guaranteed iteration order (even though CPython 3.7+ dicts
are insertion-ordered, sets are not, and relying on dict iteration order is an implementation
detail that cannot be relied upon across Python versions or worker restarts). If workflow
control flow branches based on iterating a set or dict, replay may iterate in a different order,
causing the workflow to take a different path.

**Why the sandbox does NOT catch it:** The sandbox cannot intercept arbitrary iteration patterns.
This is a silent divergence — the workflow continues running but on a different execution path
from the original, causing hard-to-diagnose state corruption.

**What to do instead:** Convert sets to sorted lists (`sorted(my_set)`) before any branching
logic. The sorted order is deterministic across all Python versions and environments.

```python
# Wrong — set iteration order may differ on replay
active_features = {"feature_a", "feature_b", "feature_c"}
for feature in active_features:  # order is undefined
    if should_enable(feature):
        ...

# Correct — sorted list has deterministic order
for feature in sorted(active_features):
    if should_enable(feature):
        ...
```

---

### Global mutable state

**What happens:** Workflow workers share a process. Global variables modified during one
workflow execution persist and affect other executions or replays. On replay, the global state
may already be modified from a previous run, producing different behavior than the first
execution.

**Why the sandbox does NOT catch it:** The sandbox cannot intercept mutations to module-level
or class-level variables. Python does not provide a hook for intercepting attribute assignment
on arbitrary objects.

**What to do instead:** All state must flow through workflow input parameters and return values.
The accumulated state dict passed through `_execute_step` is the correct pattern for DSL
workflows — never store execution state in module-level variables.

```python
# Wrong — global state persists across workflow executions and replays
_order_counter = 0

@workflow.defn
class DSLWorkflow:
    @workflow.run
    async def run(self, defn, input):
        global _order_counter
        _order_counter += 1  # Different value on replay if another workflow ran first
        ...

# Correct — all state in the accumulated state dict
@workflow.defn
class DSLWorkflow:
    @workflow.run
    async def run(self, defn, input):
        state = dict(input)  # State flows through input/output, never global variables
        ...
```

---

### `asyncio.sleep()` in workflow

**What happens:** Calling `asyncio.sleep()` inside workflow code pauses execution for a
real-time duration, bypassing Temporal's durable timer mechanism. On replay, the sleep is
executed again, adding real latency. Worse, if the worker is restarted during the sleep,
Temporal has no record of the timer and cannot resume correctly — the sleep is simply lost.

**Why the sandbox does NOT catch it:** `asyncio.sleep()` is a legitimate coroutine primitive
that the sandbox cannot distinguish from legitimate async awaits. This is one of the most
common silent violations.

**What to do instead:** Use `await workflow.sleep(timedelta(...))`. This records a durable timer
in the event history. A worker restart during the sleep resumes correctly from the timer record.

```python
# Wrong — real-time sleep, lost on worker restart
import asyncio
await asyncio.sleep(300)  # 5 minutes real time, not durable

# Correct — durable timer recorded in event history
from datetime import timedelta
await workflow.sleep(timedelta(minutes=5))
```

---

### Pydantic validator with I/O

**What happens:** Pydantic `model_validator` and `field_validator` functions run every time a
model is instantiated, including during deserialization inside workflow code. If a validator
performs a network call, database read, or file read, the operation executes on replay — but the
sandbox does NOT intercept calls made inside validators.

This produces two problems:
1. **Non-determinism:** The I/O result may differ between the original run and replay.
2. **External side effects on every replay:** Every worker restart and replay triggers the I/O
   again, potentially causing unintended operations (e.g., incrementing a counter, logging,
   charging for an API call).

**Why the sandbox does NOT catch it:** Validators are pure Python methods. The sandbox cannot
distinguish between a validator that checks `len(value) > 0` and one that makes a network call.

**What to do instead:** Keep all validators pure — validate shape, field constraints, and
internal consistency only. Move any I/O that validators would perform into activities, where
non-deterministic operations are expected and safe.

```python
# Wrong — I/O in validator
class OrderInput(BaseModel):
    order_id: str

    @field_validator("order_id")
    @classmethod
    def validate_order_exists(cls, v: str) -> str:
        response = requests.get(f"https://api.example.com/orders/{v}")  # WRONG: network I/O
        if response.status_code == 404:
            raise ValueError(f"Order {v} does not exist")
        return v

# Correct — validator checks shape only; existence check is an activity
class OrderInput(BaseModel):
    order_id: str

    @field_validator("order_id")
    @classmethod
    def validate_order_id_format(cls, v: str) -> str:
        if not v.startswith("ORD-"):
            raise ValueError("order_id must start with 'ORD-'")
        return v
```

---

## The Golden Rule

Delegate all non-deterministic operations to activities. Workflow code must use only `workflow.*`
APIs for time, randomness, and sleeping. Activities run outside the sandbox and may use any
Python library freely — network calls, file I/O, database access, random number generation, and
threading are all safe inside an activity function.

---

## Anti-Pattern: Temporal Decorators in Domain Code

The most destructive pattern in Temporal projects is allowing `@workflow.defn`, `@activity.defn`,
or `workflow.execute_activity()` to appear in domain models or business logic modules. This
creates a permanent dependency on the `temporalio` package throughout the codebase.

**Why it is destructive:**

- Business logic becomes untestable without a running Temporal server. Every unit test that
  touches the domain model must import `temporalio`, start a worker, and connect to a Temporal
  service.
- The domain model cannot be reused with a different orchestration engine. Once `@workflow.defn`
  is in the domain layer, the entire codebase is bound to Temporal permanently.
- Temporal versioning constraints leak into domain code. Upgrading the Temporal SDK requires
  reviewing and potentially changing business logic.
- The DSL graph definition loses meaning. If workflow behavior is encoded in `@workflow.run`
  method logic rather than a `WorkflowDefinition` model, the graph cannot be validated,
  serialized, or analyzed without executing it.

**The rule:** `import temporalio` must never appear outside the adapter layer. In the
recommended directory structure, the only files that may import from `temporalio` are in
`workflows/adapters/`. All other modules — models, validators, services, domain logic — must
have zero `temporalio` imports.

Enforce this at the repository level with the AST-based pytest test described in
`stacks/python/adapter.md` Section 6.
