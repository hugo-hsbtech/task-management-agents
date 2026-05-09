# Determinism Rules for Temporal Workflows

Temporal replays workflow code to reconstruct state after a worker restart, upgrade, or failure.
During replay, the workflow function executes again from the beginning, but activity calls and
side effects are replayed from the recorded event history rather than re-executed. Any operation
that produces different output on replay causes workflow divergence and silent failure. This
reference enumerates every known violation category and whether the SDK sandbox catches it.

---

## Sandbox Behavior Table

The SDK runs workflow code in a sandbox that intercepts many non-deterministic operations.
However, the sandbox is not exhaustive. The table below distinguishes violations the sandbox
catches (raising an error immediately) from violations the sandbox does NOT catch (silent
divergence on replay).

| Violation | Caught by Sandbox? | Use Instead |
|-----------|--------------------|-------------|
| System random number generation | YES | `workflow.random()` — seeded from event history |
| Wall-clock current time | YES | `workflow.now()` — time recorded in event history |
| OS epoch timestamp | YES | `workflow.now().timestamp()` |
| Thread spawning in workflow code | YES | Activity (offload to worker thread pool) |
| Random UUID generation | YES | `workflow.uuid4()` — derived from event history seed |
| Iterating unordered collections in branching logic | NO — you must avoid | Convert to sorted list before branching |
| Global mutable state | NO — you must avoid | Use workflow input/state only |
| Real-time sleep in workflow | NO — you must avoid | `workflow.sleep(duration)` — durable timer |
| Model validators with I/O | NO — you must avoid | Keep validators pure (no network, no file I/O) |

---

## Why Each Violation Breaks Replay

### System random number generation

Produces different values on each call. On replay, the workflow expects the same random value
that was generated during the original execution. A different value causes the workflow to take
a different code path, diverging from the recorded history. Use `workflow.random()` instead —
the SDK's random instance is seeded deterministically from the workflow's event history.

### Wall-clock current time

Returns the current wall-clock time, which differs between the original run and replay. If
workflow branching logic depends on the current time (e.g., "is this a business-hours
request?"), replay may take a different branch. Use `workflow.now()`, which returns the time
recorded in the workflow's event history.

### OS epoch timestamp

Same class of violation as wall-clock time — returns the current epoch timestamp from the OS
clock. On replay, this timestamp will differ from the original execution. Use
`workflow.now().timestamp()` to obtain the deterministic timestamp from the event history.

### Thread spawning in workflow code

Spawning threads inside workflow code introduces execution order non-determinism. Thread
scheduling is controlled by the OS and differs between runs. The SDK sandbox intercepts thread
creation directly. Offload threaded work to activities, which run outside the sandbox in the
worker's thread pool.

### Random UUID generation

Generates a random UUID using the OS random number generator. On replay, a different UUID is
generated, making any logic that stores or compares the UUID diverge. Use `workflow.uuid4()`,
which derives a deterministic UUID from the workflow's event history seed.

### Iterating unordered collections in branching logic

Unordered collections (sets, and in some languages dict key iteration order) have no guaranteed
iteration order across runs or language versions. If workflow control flow branches based on
iterating such a collection, replay may iterate in a different order, causing the workflow to
take a different path. Convert to a sorted list before any branching logic. The sandbox does
NOT intercept this violation.

### Global mutable state

Workflow workers share a process. Global variables modified during one workflow execution
persist and affect other executions or replays. On replay, the global state may already be
modified from a previous run, producing different behavior. All state must flow through
workflow input parameters and return values. The sandbox does NOT intercept mutations to
module-level or class-level variables.

### Real-time sleep in workflow

Calling a real-time sleep inside workflow code pauses execution for a wall-clock duration,
bypassing Temporal's durable timer mechanism. On replay, the sleep is executed again, adding
real latency. If the worker is restarted during the sleep, Temporal has no record of the timer
and cannot resume correctly. Use `workflow.sleep(duration)` instead — this records a durable
timer in the event history that survives worker restarts.

### Model validators with I/O

Model validator functions run every time a model is instantiated, including during
deserialization inside workflow code. If a validator performs a network call, database read, or
file read, the operation executes on replay — but the sandbox does NOT intercept calls made
inside validators. This produces non-determinism and may cause external side effects on every
replay. Keep all validators pure: validate shape, constraints, and internal consistency only.

---

## The Golden Rule

Delegate all non-deterministic operations to activities. Workflow code must use only
`workflow.*` APIs for time, randomness, and sleeping. Activities run outside the sandbox and
may use any library freely — network calls, file I/O, database access, random number
generation, and threading are all safe inside an activity function.

---

## Anti-Pattern: Temporal Decorators in Domain Code

The most destructive pattern in Temporal projects is allowing workflow definition decorators,
activity definition decorators, or activity execution calls to appear in domain models or
business logic modules. This creates a permanent dependency on the Temporal SDK throughout
the codebase.

**Why it is destructive:**

- Business logic becomes untestable without a running Temporal server. Every unit test that
  touches the domain model must import the Temporal SDK, start a worker, and connect to a
  Temporal service.
- The domain model cannot be reused with a different orchestration engine. Once Temporal
  decorators are in the domain layer, the entire codebase is bound to Temporal permanently.
- Temporal versioning constraints leak into domain code. Upgrading the SDK requires reviewing
  and potentially changing business logic.
- The DSL graph definition loses meaning. If workflow behavior is encoded in the `@workflow.run`
  method logic rather than a `WorkflowDefinition` model, the graph cannot be validated,
  serialized, or analyzed without executing it.

**The rule:** The Temporal SDK import must never appear outside the adapter layer. In the
recommended directory structure, the only files that may import from the Temporal SDK are in
`workflows/adapters/` and `workers/`. All other modules — models, validators, services, domain
logic — must have zero Temporal SDK imports.

Enforce this at the repository level by adding a lint rule or import guard that fails CI if
the Temporal SDK appears outside the adapter directory. See adapter.md Section 6 for the
concrete import boundary test.
