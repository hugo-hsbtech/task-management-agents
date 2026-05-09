---
name: temporal-workflow
description: >
  ALWAYS invoke this skill when building Temporal workflows, implementing workflow
  abstraction layers, or when asked about Temporal, workflow engines, or durable
  execution. Guides developers through a 4-layer ports-and-adapters architecture that
  keeps Temporal out of domain code. Do not attempt to write Temporal workflow code
  directly -- invoke this skill first.
argument-hint: "[project-name or phase-number]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Temporal Workflow Skill

Build a Temporal workflow system where Temporal never leaks into domain code.

---

## Start Here

### Step 1: Select Stack

Ask: "Which language/stack are you building with? (Python is supported -- Go/TS patterns coming soon)"

If the user selects Go, TypeScript, Java, or any non-Python stack: "Python is the supported stack. Go/TS patterns are coming soon. Proceed with Python?"

### Step 2: Assess Experience Level

Ask: "Have you worked with Temporal before?"

- **Yes (experienced):** Skip Step 4 (architecture orientation) and proceed directly to Phase 1. Focus on the abstraction boundary — experienced Temporal developers often skip this and end up with leaky adapters.
- **No (newcomer):** Complete all Start Here steps. Step 4 presents the architecture diagram and layer roadmap before building begins. Include brief concept explanations inline with each step.

### Step 3: Scan the Project

Scan the project for existing code before generating anything:

1. Look for package manifest files (`pyproject.toml`, `package.json`, `go.mod`) — detect stack and installed packages.
2. Search for Temporal SDK imports (`temporalio`, `@temporalio`, `go.temporal.io`) — detect existing Temporal usage.
3. Search for `WorkflowDefinition`, workflow definition decorators, `StepDefinition` — detect existing DSL patterns.
4. Detect project structure (src layout vs flat) — infer the output directory.
5. Suggest an output path (e.g., `src/workflows/` or `workflows/`) and ask the user to confirm or override.

If existing code is detected:

- Validate it against best practices. See [references/dsl.md](references/dsl.md) for validation rules.
- Flag issues (e.g., "Your workflow definitions contain Temporal SDK imports outside the adapter layer — this violates the abstraction boundary").
- Continue from where the user is rather than restarting from scratch.

### Step 4: Show the Architecture

Read [references/architecture.md](references/architecture.md) and present:

1. The 4-layer Mermaid diagram showing how the layers depend on each other.
2. The layer roadmap table showing what each phase builds and its key deliverables.

This gives the user the full journey before the first step.

---

## Phase 1 — DSL Layer

Goal: Define the workflow graph in pure domain code. No Temporal imports. Prove the abstraction with an in-memory executor.

Running example: order processing workflow (validate -> charge -> fulfill -> notify). Map each concept to the target domain as it is introduced.

---

### Step 1: Define DSL Models

Create the four core model types: `WorkflowDefinition`, `StepDefinition`, `Transition`, `RetryPolicy`.

See the abstract field tables and cross-field constraints in [references/dsl.md](references/dsl.md) Section 1.

**Skeleton to customize:**

```
WorkflowDefinition:
  id: string (1-100 chars)
  version: string
  steps: list[StepDefinition]  // ids must be unique
  transitions: list[Transition]

StepDefinition:
  id: string (1-100 chars)
  type: "task" | "decision" | "parallel" | "event"
  action: string or null      // required for task; forbidden for decision/parallel
  timeout_seconds: int (1-86400, default 30)
  retry_policy: RetryPolicy or null

RetryPolicy:
  max_attempts: int (1-100)
  initial_interval_seconds: int (1-3600)
  backoff_coefficient: float (1.0-10.0)
  max_interval_seconds: int or null  // must be >= initial_interval_seconds

Transition:
  from_step: string
  to_step: string
  condition: string or null
```

Map `action` to the project's naming convention (e.g., `handler`, `callable_name`).

**Verification checkpoint:** Verify the DSL models import correctly and construct without error.

See stacks/{stack}/ for the concrete implementation and import check command.

---

### Step 2: Add Graph Validation

Create the graph validator with the 4-constraint algorithm.

See the complete algorithm and BFS/DFS pseudocode in [references/dsl.md](references/dsl.md) Section 2.

The validator enforces these four constraints:

1. **Single entry point** — exactly one step has no incoming transitions.
2. **Terminal steps exist** — at least one step has no outgoing transitions.
3. **No orphan steps** — all steps reachable from entry (BFS traversal).
4. **No infinite loops without event break** — cycles allowed only when an `event`-type step is in the cycle (DFS with three-color marking).

**Verification checkpoint:** Construct an invalid workflow with two entry points and confirm `validate_graph()` raises an error citing "exactly one entry point".

---

### Step 3: Build In-Memory Executor

Create the in-memory executor. This proves the DSL abstraction works without a running Temporal server.

See the executor algorithm in [references/dsl.md](references/dsl.md) Section 3.

How it works:

1. Register action handlers by name: `executor.register("action_name", callable)`.
2. Call `executor.run(workflow_definition, initial_state_dict)`.
3. The executor validates the graph, then traverses from the entry step, calling registered handlers for each `task` step.
4. Each handler receives the accumulated state dict and returns an updated state dict.
5. Returns the final state with `status: "completed"` appended.

The Phase 1 executor handles `task` steps only. `decision`, `parallel`, and `event` step types raise a not-implemented error — the Phase 2 Temporal adapter handles them.

**Verification checkpoint:** Run the order processing example and assert `result["status"] == "completed"`. All six DSL checkpoint tests must pass before proceeding to Phase 2. See [references/dsl.md](references/dsl.md) Section 5.

See stacks/{stack}/ for the concrete executor implementation and test file.

---

## Determinism Warning

Non-deterministic code in workflow functions causes silent replay failures. Flag these patterns immediately when encountered in the project:

- System random number generation — use `workflow.random()` instead (Phase 2+)
- Wall-clock current time — use `workflow.now()` instead (Phase 2+)
- Real-time sleep in workflow code — use `workflow.sleep(duration)` instead (Phase 2+)
- Network or I/O calls in workflow code — delegate to activities (Phase 2+)
- Iterating unordered collections in branching logic — convert to sorted list first

Full sandbox rules and the table of what the SDK catches vs. what it does NOT catch: [references/determinism.md](references/determinism.md)

---

## Project Conventions

When working in this project, follow the project-specific conventions in [references/ezra-conventions.md](references/ezra-conventions.md). Key rules:

- **Activity shells live in each domain package** (`{domain}/activities.py`), not in the workflows domain
- **Each domain exports an `ACTIVITIES` list** that the worker app imports
- **The workflows domain is pure infrastructure** — DSL, registry, adapter, tracing, settings. No domain-specific code.
- **The worker app assembles everything** — imports activity lists, calls `configure()`, creates Worker instances
- **Action names** use `{domain_prefix}_{verb}` format (e.g., `deal_triage_classify`)
- **Task queues** use kebab-case (e.g., `deal-triage`)
- **Retry presets** (`RETRY_LLM`, `RETRY_IO`, `RETRY_POLL`) are defined per workflow definition file
- **Task queue constants** are co-located with the workflow definition

When adding a new workflow to the existing system, follow the checklist in [references/ezra-conventions.md](references/ezra-conventions.md) Section 9.

---

## Anti-Pattern: Temporal Decorators in Domain Code

The most destructive pattern in Temporal projects: workflow definition decorators, activity definition decorators, or activity execution calls appearing in domain models or business logic.

**The rule:** Temporal SDK imports must never appear outside the adapter layer. Only files in `workflows/adapters/` may import from the Temporal SDK.

When found during project scan, flag immediately: "This file imports the Temporal SDK outside the adapter layer. This couples your domain logic to the SDK permanently."

Enforce at the repository level with a lint rule or CI import guard. See [references/determinism.md](references/determinism.md) and [references/adapter.md](references/adapter.md) Section 6.

---

## Phase 2 — Engine Port and Temporal Adapter

Goal: Wire the DSL-validated workflow into a running Temporal environment through a strict abstraction boundary.

Running example: continue the order processing workflow (validate -> charge -> fulfill -> notify).

---

### Step 1: Define the WorkflowEngine Interface

Create the `WorkflowEngine` structural interface, `WorkflowHandle`, and domain exceptions.

See the method signatures and exception hierarchy in [references/port.md](references/port.md).

The interface uses structural subtyping (runtime-checkable protocol). Three async methods form the interface: `start_workflow`, `signal`, `query`. Zero Temporal SDK imports in this file — domain code depends on the interface, never on the concrete adapter.

**Verification checkpoint:** Verify a stub class implementing all three methods satisfies the interface via the runtime-checkable protocol check. Confirm the port file has no SDK imports via AST scan.

See stacks/{stack}/ for the concrete interface definition and test file.

---

### Step 2: Build the TemporalAdapter

Create `DSLWorkflow` and `TemporalAdapter` in the adapter layer.

See the DSL-to-Temporal mapping table in [references/adapter.md](references/adapter.md) Section 1. The table is the primary reference for how each DSL concept maps to a Temporal primitive.

`DSLWorkflow` is the workflow-decorated class that interprets `WorkflowDefinition` at runtime — one generic class handles any `WorkflowDefinition`. `TemporalAdapter` satisfies the `WorkflowEngine` interface through structural subtyping (no inheritance required). All four step types are handled: `task`, `parallel`, `decision`, `event`. This is the ONLY file that imports the Temporal SDK. Run the import boundary test (Step 5) immediately after this step.

**Verification checkpoint:** Confirm `TemporalAdapter` has all three interface methods (`start_workflow`, `signal`, `query`).

See stacks/{stack}/ for the concrete adapter implementation.

---

### Step 3: Build the ActionRegistry

Create `ActionContract` and `ActionRegistry`.

See the complete registry design in [references/registry.md](references/registry.md).

Use a decorator pattern to register actions at import time — decorated modules must be imported before `registry.get()` is called. Activities are thin shells: one call to a domain service, no business logic. The registry stores both the callable and an `ActionContract` with idempotency metadata.

**Verification checkpoint:** Register a test action, resolve it by name, confirm the idempotency contract is stored correctly, and confirm `registered_names()` returns a sorted list.

See stacks/{stack}/ for the concrete registry implementation and test file.

---

### Step 4: Set Up the Worker

Create the worker with parametrized configuration.

See the worker setup algorithm in [references/adapter.md](references/adapter.md) Section 5.

Connect the Temporal client, create a worker with sandbox restrictions configured to allow the model validation library inside the sandbox, and register activities. All configuration is passed as function parameters — the caller decides how to source host, port, namespace, and task queue values.

**Verification checkpoint:** Confirm the worker module imports without error.

See stacks/{stack}/ for the concrete worker setup.

---

### Step 5: Run the Import Boundary Test

Create the import boundary test from [references/adapter.md](references/adapter.md) Section 6.

This test uses AST parsing to scan every source file outside the adapter and worker directories and fails CI if any Temporal SDK import is found outside those directories. Run it immediately after creating the adapter.

**Verification checkpoint:** Run the import boundary test suite — all tests must pass.

---

### Step 6: Integration Checkpoint

Start a local Temporal server and run the order processing workflow through the full stack.

```
temporal server start-dev
```

Run the order processing workflow end-to-end: DSL definition -> `TemporalAdapter.start_workflow` -> `DSLWorkflow` interpreter -> activity execution -> accumulated result. Confirm all Phase 1 tests still pass.

See [references/adapter.md](references/adapter.md) Section 9.

---

## Phase 3 — Production Hardening

Extends the adapter with retry policies, typed signals, observability, and persistence. See [references/adapter.md](references/adapter.md) Sections 7-8, [references/observability.md](references/observability.md), [references/persistence.md](references/persistence.md).

---

### Step 1: Wire Retry Policies

Extend `RetryPolicy` with a fifth field: `non_retryable_error_types` (list of exception class name strings). Extract retry policy mapping into a standalone `_build_retry_policy` helper in the adapter. See the field mapping table in [references/adapter.md](references/adapter.md) Section 7.

**Verification checkpoint:** Construct a `RetryPolicy` with `non_retryable_error_types` set and confirm the field is stored correctly.

---

### Step 2: Add Typed Signals and Queries

Define signal payload models in the DSL layer, not in the adapter. The `ApprovalPayload` model captures the approval decision and approver identity. Upgrade the signal handler from a plain dict payload to a typed payload model. Add a `wait_condition` with a timeout (e.g., 72 hours) in `execute_event` so the workflow fails fast when no signal arrives within the SLA window.

See the payload schema and signal-with-start pattern in [references/adapter.md](references/adapter.md) Section 8.

**Verification checkpoint:** Send a typed approval signal to the order processing workflow and verify it unblocks the event step and updates the accumulated state.

---

### Step 3: Set Up OpenTelemetry Tracing

Call `configure_tracing()` before `Client.connect()` — `TracingInterceptor` captures the OTel tracer at construction time. Pass the same `TracingInterceptor` instance to both the client and worker. Add custom business spans inside activity functions. Set domain entity ID and `workflow.step` attributes on every span. Add `heartbeat()` calls in long-running activities with `heartbeat_timeout` set to 2–3x the heartbeat interval. Always re-raise `CancelledError`.

See [references/observability.md](references/observability.md) for the complete setup, span naming convention, and heartbeat pattern.

**Verification checkpoint:** Run the order processing workflow and confirm spans appear in the console output, including auto-instrumented Temporal spans and custom business spans.

---

### Step 4: Define WorkflowInstance Persistence Model

Create `WorkflowInstance` and `StepRecord` models. `WorkflowInstance` is a schema-only domain record — no storage implementation is prescribed. `temporal_workflow_id` is the foreign key linking the domain record to the Temporal execution. Set it to null at creation and assign only after `TemporalAdapter.start_workflow()` returns successfully. `StepRecord` is append-only history — never mutate or remove records.

See the field schemas in [references/persistence.md](references/persistence.md) Section 1.

**Verification checkpoint:** Construct a `WorkflowInstance`, serialize it, deserialize it, and confirm `definition_id` is preserved and `temporal_workflow_id` is null.

See stacks/{stack}/ for the concrete model definition.

---

### Step 5: Add Safe Versioning

Implement `workflow.patched()` inside `DSLWorkflow.run` to safely deploy changes to the interpreter logic. Deploy in three phases: add the patched block alongside old code; call `workflow.deprecate_patch()` once all pre-patch executions finish; remove both calls after the retention period.

Encode the specific interpreter change in the patch ID — `"dsl-interpreter-v2-parallel-merge"`, not `"v2"`. Patch IDs must be globally unique and descriptive.

See [references/persistence.md](references/persistence.md) Section 2 for the three-phase migration pattern.

**Verification checkpoint:** Confirm `workflow.patched("patch-id")` appears in `DSLWorkflow.run` source with both branches present.

---

### Step 6: Handle Long-Running Workflows

Add `is_continue_as_new_suggested()` check inside the step execution loop in `DSLWorkflow.run`, after each step completes. When the check returns true, call `workflow.continue_as_new(args=[defn, {**state, "_continued_from": current_run_id}])`. The `_continued_from` key records the previous run ID for audit continuity.

Call `continue_as_new` only from the `@workflow.run` coroutine — never from a signal handler. Signal handlers may have queued signals awaiting processing; calling `continue_as_new` from inside a handler drops those queued signals silently.

See [references/persistence.md](references/persistence.md) Section 3.

**Verification checkpoint:** Confirm `is_continue_as_new_suggested` and `_continued_from` both appear in `DSLWorkflow.run`.

---

## Phase 4 — Orchestration and Portability

The abstraction built in Phases 1–3 separates decision from execution. A calling layer decides which workflow to start and when. Temporal guarantees each step executes, retries on failure, and survives restarts. No orchestration framework is prescribed — any decision layer connects through the `WorkflowEngine` interface.

**Orchestration philosophy:** Temporal executes. Something else decides. The `WorkflowEngine` interface is the seam between the two concerns. Domain services, API handlers, scheduled jobs, and event consumers all call through the interface without knowing how execution is implemented.

**Stack portability:**

| DSL Concept | Stack-specific? | Equivalent in other stacks |
|-------------|----------------|---------------------------|
| Schema models (Pydantic) | Yes — Python | Zod (TS); structs + validator (Go) |
| Structural interface (Protocol) | Yes — Python | `interface` (TS/Go) |
| Decorator registry | Yes — Python | DI container (TS); function map (Go) |
| Graph model | No — portable | Same schema types; graph logic transfers directly |
| Port pattern | No — portable | Interface (TS); implicit interface (Go) |

The graph validation algorithm, in-memory executor concept, DSL-to-Temporal mapping, import boundary enforcement, and WorkflowInstance persistence model are all stack-agnostic. Only the concrete syntax and validation library differ by stack.

See stacks/{stack}/ for stack-specific implementation of all four phases.
