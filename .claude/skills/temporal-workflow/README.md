# temporal-workflow

A Claude Code skill that guides you through building Temporal workflow systems with clean, portable architecture. Temporal is treated as an execution engine — never as the source of truth for workflow definition.

**Stack-agnostic by design.** The skill teaches patterns that work in any language. Stack-specific implementation lives in a separate layer — the same architecture the skill itself teaches.

## The Problem

Most Temporal projects end up with workflow definition decorators and activity execution calls scattered across domain code. This couples your business logic to Temporal permanently. Testing requires a running Temporal server. Switching orchestration engines means rewriting everything.

This skill prevents that by teaching a 4-layer ports-and-adapters architecture where Temporal never leaks into domain code.

### File Structure

```
temporal-workflow/
  SKILL.md                          # Main skill — stack-agnostic guided build procedure
  references/                       # WHAT to build (concepts, patterns, rules)
    architecture.md                 #   4-layer diagram + layer roadmap
    dsl.md                          #   DSL schema, validation algorithms, executor concept
    port.md                         #   Port pattern, interface contracts, exception hierarchy
    adapter.md                      #   Adapter pattern, mapping table, step dispatch logic
    registry.md                     #   Registry pattern, thin-shell activities, dual registration
    determinism.md                  #   Determinism rules, violation categories, golden rule
    observability.md                #   Tracing concepts, correlation, heartbeat patterns
    persistence.md                  #   Persistence model, versioning strategy, continue_as_new
    ezra-conventions.md             #   Ezra monorepo: naming, file placement, worker wiring, new workflow checklist
  stacks/                           # HOW to build it (language-specific implementation)
    python/                         #   Python: Pydantic v2, typing.Protocol, temporalio SDK
      dsl.md                        #     Pydantic models, graph validation, InMemoryExecutor
      port.md                       #     typing.Protocol, domain exceptions, WorkflowHandle
      adapter.md                    #     temporalio SDK, DSLWorkflow, worker setup, signals
      registry.md                   #     Decorator pattern, ActionContract, pytest tests
      determinism.md                #     Python sandbox caught/not-caught table
      observability.md              #     TracingInterceptor, OTel Python SDK
      persistence.md                #     Pydantic WorkflowInstance, workflow.patched()
```

**The separation mirrors what the skill teaches:** `references/` is the domain layer (concepts). `stacks/` is the adapter layer (implementation). The same pattern, applied to the skill itself.

## Usage

Invoke the skill in Claude Code:

```
/temporal-workflow
```

Claude will:
1. Ask which stack you're building with
2. Assess your Temporal experience level
3. Scan your project for existing code
4. Guide you through the 4-phase build

## The Journey

The skill takes you through 4 phases. Each phase builds one architectural layer, and each layer depends on the one before it. You end up with a production-ready workflow system.

### Phase 1 — DSL Layer (No Temporal Required)

**What you build:** Pure domain workflow definitions that are completely independent from Temporal.

**You create:**
- Four core model types: `WorkflowDefinition`, `StepDefinition`, `Transition`, `RetryPolicy`
- A graph validator enforcing 4 constraints (single entry point, terminal steps, no orphans, no infinite loops without event breaks)
- An in-memory executor that runs workflows without a Temporal server

**What you prove:** Your workflow definitions are valid, testable, and completely Temporal-free. You can define, validate, and execute a workflow graph in pure domain code.

**Running example:** An order processing workflow (`validate -> charge -> fulfill -> notify`) is used throughout all 4 phases. You map each concept to your own domain as you go.

**Verification checkpoint:** All 6 DSL unit tests pass. The in-memory executor runs the order processing workflow end-to-end.

### Phase 2 — Engine Port, Temporal Adapter, and Action Registry

**What you build:** The abstraction boundary that lets domain code talk to Temporal without knowing Temporal exists.

**You create:**
- A `WorkflowEngine` interface with `start_workflow`, `signal`, `query` — zero Temporal SDK imports. Domain code depends on this interface only.
- A `TemporalAdapter` that satisfies the interface. `DSLWorkflow` interprets any `WorkflowDefinition` at runtime. This is the **only file** that imports the Temporal SDK.
- An `ActionRegistry` with decorator-based registration and idempotency metadata. Activities are thin shells that delegate to domain services.
- A parametrized worker (all config as parameters — caller decides how to source values).
- An AST-based import boundary test that fails CI if Temporal SDK imports appear outside the adapter.

**What you prove:** Domain code sends a signal, starts a workflow, or queries state through `WorkflowEngine` — without knowing Temporal is underneath. The import boundary test enforces this at CI level.

**Key concept — the mapping table:**

| DSL Concept | Temporal Concept |
|-------------|-----------------|
| WorkflowDefinition | Workflow definition (DSLWorkflow) |
| StepDefinition (task) | Activity execution |
| StepDefinition (parallel) | Concurrent activity execution (gather/fan-out) |
| StepDefinition (decision) | Conditional flow in interpreter |
| StepDefinition (event) | Wait condition (signal-driven) |
| Transition | Code flow in interpreter |
| RetryPolicy | Activity retry options |
| Event/Signal | Signal / Query handlers |

**Verification checkpoint:** Start a local Temporal server (`temporal server start-dev`), run the order processing workflow through the full stack, and confirm all Phase 1 tests still pass.

### Phase 3 — Production Hardening

**What you build:** Everything needed for production: retry policies, typed signals, observability, persistence, and safe deployment patterns.

**What gets added:**

1. **Retry Policies** — Every DSL `RetryPolicy` field maps to a Temporal activity option. A centralized helper handles the translation. Non-retryable error types are specified as strings, not class references.

2. **Typed Signals and Queries** — Signal payloads are schema models defined in the DSL layer (not the adapter). The `ApprovalPayload` model enables human-in-the-loop workflows with a wait condition and timeout SLA.

3. **OpenTelemetry Tracing** — Tracing interceptor attached to both the Temporal client and worker. Custom business spans inside activities with domain entity IDs, step names, and correlation IDs. Heartbeat pattern for long-running activities. Backend-agnostic — you choose the exporter.

4. **WorkflowInstance Persistence** — A schema for storing workflow state outside Temporal. `temporal_workflow_id` is the foreign key linking domain state to Temporal execution. `StepRecord` provides append-only history. No ORM or database prescribed — the schema is storage-agnostic.

5. **Safe Versioning** — `workflow.patched()` migration guide with a 3-phase rollout: introduce patch alongside old code, deprecate after old executions drain, remove after retention period. Patch IDs encode the specific change.

6. **Long-Running Workflows** — `continue_as_new` triggered by the SDK's `is_continue_as_new_suggested()` inside the step execution loop. State carries a `_continued_from` key for audit continuity. Never called from signal handlers.

**Verification checkpoint:** Retry policies wire correctly, typed signals unblock event steps, OTel spans appear in output, WorkflowInstance round-trips through serialization.

### Phase 4 — Orchestration Philosophy and Portability

**What you learn:** The architectural framing that makes the system extensible.

**The principle:** Temporal guarantees execution. Something else decides what to execute. The `WorkflowEngine` interface is the boundary — any decision layer (HTTP handler, queue consumer, AI agent, cron job) connects through it. No specific framework is prescribed.

**Stack portability:**

| Concept | Stack-specific? | Equivalent in other stacks |
|---------|----------------|---------------------------|
| Schema models | Yes | Zod (TS); structs + validator (Go) |
| Structural interface | Yes | `interface` (TS/Go) |
| Decorator registry | Yes | DI container (TS); function map (Go) |
| Graph model | No — portable | Same schema types; graph logic transfers |
| Port pattern | No — portable | Interface (TS); implicit interface (Go) |

## Architecture Overview

```
Domain Layer (your business logic)
    |
    v
DSL Layer (WorkflowDefinition, StepDefinition, Transition)
    |
    v
Engine Port (WorkflowEngine interface — the abstraction boundary)
    |
    v
Temporal Adapter (the ONLY place that imports the Temporal SDK)
    |
    v
Temporal Runtime (execution guarantee)
```

**The rule:** Temporal SDK imports must never appear outside the adapter layer. The skill includes an AST-based import boundary test that enforces this at CI level.

## What the Skill Adapts To

When you invoke `/temporal-workflow`, the skill:

1. **Asks your stack** — Python is supported today. Go/TypeScript patterns are planned.
2. **Assesses your experience** — Temporal newcomers get an architecture orientation first. Experienced developers skip straight to building.
3. **Scans your project** — Detects package manifests, Temporal SDK imports, existing DSL patterns. If you already have code, it validates against best practices and continues from where you are.
4. **Suggests output directory** — Infers from your project structure and lets you override.

## Determinism Rules

Temporal replays event history to reconstruct workflow state. Non-deterministic code in workflow functions produces different commands on replay and permanently halts the workflow.

| Category | Example | Risk |
|----------|---------|------|
| Random number generation | System random in workflow code | Different values on replay |
| Wall-clock time | Current time reads in workflow code | Different timestamps on replay |
| Real-time sleep | Language-native sleep in workflow code | Different timing on replay |
| Network/IO calls | Direct HTTP/DB calls in workflow code | Different results on replay |
| Unordered iteration | Iterating sets/maps in branching logic | Different ordering on replay |
| Global mutable state | Shared variables across workflows | Race conditions on replay |

The full table of what the SDK sandbox catches vs. what it does NOT catch (with "Use Instead" alternatives) is in `references/determinism.md` and `stacks/{stack}/determinism.md`.

## Adding a New Stack

The skill is designed for multi-stack support. To add TypeScript, Go, or any other language:

1. Create `stacks/{language}/` with implementation files mirroring `stacks/python/`
2. Each file implements the concepts from the corresponding `references/` file in the target language
3. Update the stack gate in SKILL.md Step 1 to include the new language
4. The agnostic `references/` and `SKILL.md` procedure remain unchanged

The `references/` directory defines WHAT to build. The `stacks/` directory defines HOW. Adding a stack means only adding a HOW — the WHAT is already done.

## Requirements

**For Python stack:**
- Python 3.11+
- `temporalio[pydantic]` (1.24.0+)
- Pydantic v2 (2.12+)
- A running Temporal server for Phase 2+ (`temporal server start-dev` for local development)

**For other stacks:** See `stacks/{stack}/` for stack-specific requirements (when available).

## FAQ

**Q: Is this a code generator?**
No. It is a guided build. Claude walks you through creating each file, explains why each layer exists, and verifies your work at every step. You understand the architecture because you built it.

**Q: Can I use this with TypeScript or Go?**
The skill procedure and architecture patterns are stack-agnostic. Python implementation is available today in `stacks/python/`. TypeScript and Go implementations are planned. The concepts in `references/` apply to any language — only the concrete syntax differs.

**Q: What if I already have Temporal code?**
The skill scans your project and adapts. If it finds Temporal SDK imports in domain code, it flags the anti-pattern and shows you how to extract it into the adapter layer. It continues from where you are.

**Q: Do I need to follow all 4 phases?**
Phase 1 (DSL) and Phase 2 (Port + Adapter) are the core — they establish the abstraction boundary. Phase 3 (Production Hardening) and Phase 4 (Philosophy) add production concerns and framing. You can stop after Phase 2 and add production features later.

**Q: How does this compare to other Temporal skills?**
`temporalio/skill-temporal-developer` is documentation-first and language-agnostic — it points to official Temporal docs and samples. `mfateev/temporal-claude-skill` focuses on code generation with idiomatic Temporal patterns. This skill teaches the hexagonal/ports-and-adapters architecture that prevents Temporal from leaking into domain code — a pattern neither covers.

**Q: Why is the skill itself split into references/ and stacks/?**
The same reason it teaches you to split domain logic from the adapter. The skill practices what it preaches: `references/` contains the stack-agnostic patterns (the "domain"), `stacks/` contains the language-specific implementation (the "adapter"). Adding a new language means adding a new adapter — the core doesn't change.

## License

MIT
