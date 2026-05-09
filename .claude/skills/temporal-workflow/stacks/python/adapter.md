# Temporal Adapter Layer — Python Implementation

For concepts, patterns, and the DSL-to-Temporal mapping table, see `references/adapter.md`.

This file contains the complete Python implementation: `DSLWorkflow` with all four step type
handlers, `TemporalAdapter`, `TemporalWorkflowHandle`, worker setup with `SandboxRestrictions`
and Pydantic passthrough, the AST-based import boundary test, retry policy wiring, typed signals,
and the full order processing integration example.

The adapter layer is the ONLY layer that imports from `temporalio`. All other layers — domain,
DSL, and port — are adapter-free.

---

## Section 1: DSL-to-Temporal Mapping

Each DSL concept maps to a specific Temporal primitive. The translation is one-directional.

| DSL Concept | Temporal Concept | Temporal API |
|-------------|-----------------|-------------|
| `WorkflowDefinition` | `@workflow.defn` class | `DSLWorkflow` interprets `WorkflowDefinition` at runtime |
| `StepDefinition` type=`"task"` | Activity | `workflow.execute_activity(step.action, ...)` |
| `StepDefinition` type=`"parallel"` | Async fan-out | `asyncio.gather(*[execute_activity(...)])` |
| `StepDefinition` type=`"decision"` | Conditional code flow | Transition conditions evaluated in graph traversal |
| `StepDefinition` type=`"event"` | Signal + `wait_condition` | `@workflow.signal` + `await workflow.wait_condition(...)` |
| `Transition` | Code flow / conditional | Graph traversal in `@workflow.run` |
| `RetryPolicy` | `temporalio.common.RetryPolicy` | Mapped 1:1 in `_execute_task` |

`DSLWorkflow` is a generic interpreter class — the same class handles any `WorkflowDefinition`
without code changes. The `WorkflowDefinition` is passed as an argument to `DSLWorkflow.run()`
at execution time.

---

## Section 2: DSLWorkflow Class

`DSLWorkflow` is the `@workflow.defn` class that Temporal executes. It receives a
`WorkflowDefinition` and initial state dict, then traverses the step graph.

```python
# workflows/adapters/temporal_adapter.py
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy as TemporalRetryPolicy
from temporalio.exceptions import ActivityError as TemporalActivityError
from temporalio.exceptions import TimeoutError as TemporalTimeoutError
from temporalio.worker import SandboxedWorkflowRunner, Worker
from temporalio.worker.workflow_sandbox import SandboxRestrictions

from workflows.dsl.models import ApprovalPayload, StepDefinition, Transition, WorkflowDefinition
from workflows.ports.engine import ActivityError as DomainActivityError
from workflows.ports.engine import WorkflowError, WorkflowTimeoutError


@workflow.defn
class DSLWorkflow:
    """Generic workflow interpreter for WorkflowDefinition graphs.

    Registered with the Temporal Worker. Never called directly from domain code —
    domain code calls through TemporalAdapter.start_workflow(). Temporal deserialises
    the WorkflowDefinition from the workflow history on replay.

    State flows through the workflow as an accumulated dict. Each step receives the
    current state and returns an updated state dict. The final state is returned when
    the last step (one with no outgoing transitions) completes.
    """

    def __init__(self) -> None:
        self._signal_received: bool = False
        self._signal_payload: dict = {}
        self._state_snapshot: dict = {}

    @workflow.run
    async def run(self, defn: WorkflowDefinition, input: dict) -> dict:
        """Interpret WorkflowDefinition step-by-step.

        Builds step and transition lookup maps, finds the entry point (step with
        no incoming transitions), and traverses the graph until a terminal step
        is reached (no outgoing transitions).

        For decision steps, transition selection uses the Transition.condition strings
        evaluated against the current state. For parallel steps, all successor steps
        are discovered via the transition map and fanned out concurrently.

        Args:
            defn: WorkflowDefinition describing the graph to execute.
            input: Initial state dict. Passed to the first step's activity.

        Returns:
            Final accumulated state dict after all steps complete.
        """
        state = dict(input)
        self._state_snapshot = state

        # Build lookup maps for O(1) step and transition access
        step_map: dict[str, StepDefinition] = {s.id: s for s in defn.steps}
        transition_map: dict[str, list[Transition]] = {}
        for t in defn.transitions:
            transition_map.setdefault(t.from_step, []).append(t)

        # Find entry point — step with no incoming transitions
        steps_with_incoming = {t.to_step for t in defn.transitions}
        current_id: str | None = next(
            s.id for s in defn.steps if s.id not in steps_with_incoming
        )

        while current_id is not None:
            step = step_map[current_id]
            state = await self._execute_step(step, state, transition_map)
            self._state_snapshot = state

            # Determine next step: decision steps evaluate conditions; others take first
            outgoing = transition_map.get(current_id, [])
            current_id = self._select_next(step, state, outgoing)

            # Check continue_as_new after each step (see Section 7 / persistence.md)
            if workflow.info().is_continue_as_new_suggested():
                workflow.continue_as_new(
                    args=[defn, {**state, "_continued_from": workflow.info().run_id}]
                )

        return state

    async def _execute_step(
        self,
        step: StepDefinition,
        state: dict,
        transition_map: dict[str, list[Transition]],
    ) -> dict:
        """Dispatch to the correct step handler based on step type."""
        if step.type == "task":
            return await self._execute_task(step, state)
        elif step.type == "parallel":
            return await self._execute_parallel(step, state, transition_map)
        elif step.type == "decision":
            return self._execute_decision(step, state)
        elif step.type == "event":
            return await self._execute_event(step, state)
        return state

    async def _execute_task(self, step: StepDefinition, state: dict) -> dict:
        """Execute a task step: call the named activity with current state.

        Maps DSL RetryPolicy to temporalio.common.RetryPolicy field-by-field.
        The activity function is a thin shell that resolves from the ActionRegistry.

        Args:
            step: StepDefinition with type="task". step.action is the activity name.
            state: Current accumulated state dict.

        Returns:
            Updated state dict returned by the activity.
        """
        retry_policy = _build_retry_policy(step.retry_policy) if step.retry_policy else None

        return await workflow.execute_activity(
            step.action,
            state,
            start_to_close_timeout=timedelta(seconds=step.timeout_seconds),
            retry_policy=retry_policy,
        )

    async def _execute_parallel(
        self,
        step: StepDefinition,
        state: dict,
        transition_map: dict[str, list[Transition]],
    ) -> dict:
        """Execute a parallel step: fan out to all successor task steps concurrently.

        Discovers parallel branches by following the transition map from the parallel
        node — each successor step is a branch. Fan-out via asyncio.gather with results
        merged last-write-wins per key.

        Per RESEARCH.md Open Question 3: parallel branches are discovered from
        transitions, NOT from a parallel_actions field on StepDefinition. The DSL
        model has no parallel_actions field.

        Args:
            step: StepDefinition with type="parallel".
            state: Current accumulated state dict passed to all branches.
            transition_map: Complete transition map from the workflow run.

        Returns:
            Merged state dict. When branch results share keys, the last result wins.
        """
        # Discover branches from outgoing transitions of the parallel node
        outgoing = transition_map.get(step.id, [])
        branch_actions = [
            # Each successor is expected to be a task step — its action is the activity name
            t.to_step
            for t in outgoing
        ]

        # Fan out: run all branch activities concurrently with the same state
        tasks = [
            workflow.execute_activity(
                branch_action,
                state,
                start_to_close_timeout=timedelta(seconds=step.timeout_seconds),
            )
            for branch_action in branch_actions
        ]
        results = await asyncio.gather(*tasks)

        # Merge results — last-write-wins per key
        merged = dict(state)
        for r in results:
            if isinstance(r, dict):
                merged.update(r)
        return merged

    def _execute_decision(self, step: StepDefinition, state: dict) -> dict:
        """Execute a decision step: return state unchanged.

        Decision steps are pure routing nodes. They do not execute any activity.
        Transition selection based on Transition.condition strings happens in
        _select_next() after _execute_step() returns. The step itself is a no-op.

        Args:
            step: StepDefinition with type="decision".
            state: Current accumulated state dict.

        Returns:
            State dict unchanged.
        """
        return state

    async def _execute_event(self, step: StepDefinition, state: dict) -> dict:
        """Execute an event step: suspend the workflow until a signal arrives.

        Calls workflow.wait_condition with a 72-hour timeout, recording a durable
        timer in the event history. The workflow is safely suspended — the worker can
        be restarted without losing the wait. When approval_received() sets
        _signal_received=True, wait_condition wakes and execution continues.

        Use this pattern for human-approval gates, payment callbacks, and any
        external event that must arrive before the workflow can proceed.

        Args:
            step: StepDefinition with type="event".
            state: Current accumulated state dict.

        Returns:
            State dict with signal payload merged in.
        """
        from temporalio.exceptions import ApplicationError

        self._signal_received = False
        try:
            await workflow.wait_condition(
                lambda: self._signal_received,
                timeout=timedelta(hours=72),
                timeout_summary="manager-approval",
            )
        except asyncio.TimeoutError:
            raise ApplicationError("Manager approval timed out after 72 hours")
        self._signal_received = False
        # Merge signal payload into state so downstream steps can access it
        return {**state, **self._signal_payload}

    @workflow.signal
    async def receive_signal(self, payload: dict) -> None:
        """Generic signal handler. Unblocks any waiting event step.

        Called by Temporal when a signal is delivered to this workflow instance.
        Sets _signal_received=True which satisfies the wait_condition in
        _execute_event(). Stores the payload for state merging.

        Args:
            payload: Signal data dict. Merged into workflow state by _execute_event().
        """
        self._signal_received = True
        self._signal_payload = dict(payload)

    @workflow.signal
    async def approval_received(self, payload: ApprovalPayload) -> None:
        """Typed signal handler for approval events.

        The Pydantic data converter (enabled by temporalio[pydantic]) deserializes
        the incoming signal payload directly into ApprovalPayload. No manual parsing.

        ApprovalPayload is defined in the DSL layer (workflows/dsl/models.py) —
        per D-07, adapter imports payload models from DSL; DSL never imports from adapter.

        Args:
            payload: Typed approval payload. Merged into workflow state via model_dump().
        """
        self._signal_received = True
        self._signal_payload = payload.model_dump()

    @workflow.query
    def get_state(self) -> dict:
        """Query handler. Returns the current accumulated state snapshot.

        Called by TemporalAdapter.query() when domain code queries workflow state.
        Returns the state after the most recently completed step.

        Must be synchronous def, not async def — Temporal raises TypeError for
        async query handlers. Must not mutate state.

        Returns:
            Current state dict. Empty dict before the first step completes.
        """
        return dict(self._state_snapshot)

    @workflow.query
    def get_order_status(self) -> dict:
        """Query handler for order status. Returns current accumulated state.

        Must not mutate state. Synchronous def required.
        """
        return dict(self._state_snapshot)

    def _select_next(
        self,
        step: StepDefinition,
        state: dict,
        outgoing: list[Transition],
    ) -> str | None:
        """Select the next step ID from outgoing transitions.

        For decision steps: evaluates Transition.condition strings against the
        current state. Returns the first matching transition's to_step.
        For all other steps: returns the first outgoing transition (unconditional).
        When no outgoing transitions exist, returns None (terminal step).

        Condition evaluation uses eval() with state as the namespace. Conditions
        must be safe string expressions (e.g., "state.get('validated') is True").
        Avoid complex expressions — conditions encode routing logic, not business logic.

        Args:
            step: The step that just completed.
            state: Current accumulated state dict.
            outgoing: List of Transition objects from the current step.

        Returns:
            Next step ID, or None if this is a terminal step.
        """
        if not outgoing:
            return None

        if step.type == "decision":
            # Evaluate conditions in order — first match wins
            for t in sorted(outgoing, key=lambda t: t.condition is None):
                if t.condition is None:
                    # Unconditional fallback — return if no other condition matched
                    continue
                try:
                    if eval(t.condition, {"state": state}):  # noqa: S307
                        return t.to_step
                except Exception:
                    continue
            # Fall through to unconditional fallback
            for t in outgoing:
                if t.condition is None:
                    return t.to_step
            # If no condition matched and no fallback, take first
            return outgoing[0].to_step

        # Non-decision steps: take first outgoing transition
        return outgoing[0].to_step
```

---

## Section 3: TemporalAdapter Class

`TemporalAdapter` satisfies `WorkflowEngine` Protocol through structural subtyping — it does NOT
inherit from `WorkflowEngine`. All Temporal SDK exceptions are caught at the adapter boundary
and re-raised as domain exceptions.

```python
# workflows/adapters/temporal_adapter.py (continued)


class TemporalAdapter:
    """Satisfies WorkflowEngine Protocol. The sole Temporal-aware object domain code holds.

    Wraps temporalio.client.Client and delegates all engine operations through it.
    Catches all Temporal SDK exceptions and re-raises as WorkflowError, DomainActivityError,
    or WorkflowTimeoutError so domain code is never exposed to temporalio.exceptions.

    Does NOT inherit from WorkflowEngine — structural subtyping via typing.Protocol is used.
    isinstance(adapter, WorkflowEngine) returns True because @runtime_checkable is enabled
    in port.md and all three required methods are defined here.

    Usage::

        client = await Client.connect("localhost:7233", namespace="default")
        adapter = TemporalAdapter(client, task_queue="order-processing")
        # isinstance(adapter, WorkflowEngine) → True
        handle = await adapter.start_workflow(order_workflow, {"order_id": "12345"})
        result = await handle.result()
    """

    def __init__(self, client: Client, task_queue: str) -> None:
        """Initialise with a connected Temporal Client and task queue name.

        Args:
            client: A connected temporalio.client.Client instance.
            task_queue: Task queue name. Must match the task queue the Worker polls.
        """
        self._client = client
        self._task_queue = task_queue

    async def start_workflow(
        self,
        workflow: WorkflowDefinition,
        input: dict,
        workflow_id: str | None = None,
    ) -> "TemporalWorkflowHandle":
        """Start a workflow from a DSL definition.

        Passes the WorkflowDefinition and initial input as arguments to DSLWorkflow.run.
        The Temporal data converter serialises both arguments using the Pydantic converter
        (enabled when temporalio[pydantic] is installed).

        Args:
            workflow: WorkflowDefinition to execute.
            input: Initial state dict passed to the first step.
            workflow_id: Stable identifier for the workflow instance. When None,
                generates "{workflow.id}-{workflow.version}" as the default.

        Returns:
            TemporalWorkflowHandle wrapping the Temporal handle.

        Raises:
            WorkflowError: On any Temporal SDK exception during workflow start.
        """
        wf_id = workflow_id or f"{workflow.id}-{workflow.version}"
        try:
            handle = await self._client.start_workflow(
                DSLWorkflow.run,
                args=[workflow, input],
                id=wf_id,
                task_queue=self._task_queue,
            )
            return TemporalWorkflowHandle(handle)
        except Exception as exc:
            raise WorkflowError(str(exc), workflow_id=wf_id) from exc

    async def signal(
        self,
        workflow_id: str,
        signal_name: str,
        payload: dict,
    ) -> None:
        """Send a named signal to a running workflow instance.

        Retrieves the handle and dispatches the signal. The signal wakes any
        event step waiting via workflow.wait_condition.

        Args:
            workflow_id: Identifier of the target workflow instance.
            signal_name: Name of the registered signal handler (e.g., "receive_signal").
            payload: Signal data dict. Must be JSON-serialisable.

        Raises:
            WorkflowError: On any Temporal SDK exception during signal dispatch.
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            await handle.signal(signal_name, payload)
        except Exception as exc:
            raise WorkflowError(str(exc), workflow_id=workflow_id) from exc

    async def query(
        self,
        workflow_id: str,
        query_name: str,
    ) -> Any:
        """Query the current state of a running workflow instance.

        Retrieves the handle and issues the query. Returns the result of the
        registered query handler (e.g., get_state() → current state dict).

        Args:
            workflow_id: Identifier of the target workflow instance.
            query_name: Name of the registered query handler (e.g., "get_state").

        Returns:
            The query result. Type depends on the query handler implementation.

        Raises:
            WorkflowError: On any Temporal SDK exception during query.
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            return await handle.query(query_name)
        except Exception as exc:
            raise WorkflowError(str(exc), workflow_id=workflow_id) from exc
```

---

## Section 4: TemporalWorkflowHandle Class

`TemporalWorkflowHandle` wraps `temporalio.client.WorkflowHandle` to satisfy the
`WorkflowHandle[T]` Protocol from `port.md`. Domain code holds a `WorkflowHandle[dict]` typed
reference and calls `signal`, `query`, and `result` through it without importing `temporalio`.

```python
# workflows/adapters/temporal_adapter.py (continued)


class TemporalWorkflowHandle:
    """Wraps temporalio.client.WorkflowHandle to satisfy WorkflowHandle[T] Protocol.

    Returned by TemporalAdapter.start_workflow(). Domain code interacts with a running
    workflow instance through this handle. Type as WorkflowHandle[dict] when the
    workflow accumulates state as a dictionary (the common case for DSL workflows).

    Does NOT inherit from WorkflowHandle — structural subtyping via typing.Protocol.
    """

    def __init__(self, handle: Any) -> None:
        """Wrap a temporalio.client.WorkflowHandle instance.

        Args:
            handle: The raw Temporal client handle returned by client.start_workflow().
        """
        self._handle = handle

    async def signal(self, signal_name: str, payload: dict) -> None:
        """Send a named signal to this workflow instance.

        Args:
            signal_name: Name of the signal handler registered in the workflow.
            payload: Signal data dict. Must be JSON-serialisable.
        """
        await self._handle.signal(signal_name, payload)

    async def query(self, query_name: str) -> Any:
        """Query the current state of this workflow instance.

        Args:
            query_name: Name of the query handler registered in the workflow.

        Returns:
            The query result from the registered handler.
        """
        return await self._handle.query(query_name)

    async def result(self) -> Any:
        """Await the final result of this workflow instance.

        Blocks until the workflow reaches a terminal state. Returns the final
        accumulated state dict when all steps complete.

        Returns:
            Final state dict returned by DSLWorkflow.run().

        Raises:
            WorkflowError: If the workflow fails.
            DomainActivityError: If an activity fails after all retries.
            WorkflowTimeoutError: If the workflow exceeds its execution timeout.
        """
        try:
            return await self._handle.result()
        except TemporalActivityError as exc:
            raise DomainActivityError(
                str(exc),
                activity_name=getattr(exc, "activity", "unknown"),
                workflow_id=str(self._handle.id),
            ) from exc
        except TemporalTimeoutError as exc:
            raise WorkflowTimeoutError(
                str(exc),
                workflow_id=str(self._handle.id),
            ) from exc
        except Exception as exc:
            raise WorkflowError(
                str(exc),
                workflow_id=str(self._handle.id),
            ) from exc
```

---

## Section 5: Worker Setup

All configuration arrives via function parameters — never read directly from the environment
inside the function. The caller decides whether values come from environment variables, config
files, or CLI arguments.

The critical configuration item is `SandboxRestrictions.default.with_passthrough_modules("pydantic")`.
Without this, Pydantic is re-imported inside the sandbox on each workflow execution (100–500ms
overhead per workflow start). The passthrough tells the sandbox to use the already-loaded
Pydantic module from the outer process, eliminating the re-import cost.

```python
# workers/worker.py
from __future__ import annotations

from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

from workflows.adapters.activities import (
    fulfill_order_activity,
    process_payment_activity,
    send_confirmation_activity,
    validate_order_activity,
)
from workflows.adapters.temporal_adapter import DSLWorkflow


async def create_worker(
    host: str,
    port: int,
    namespace: str,
    task_queue: str,
) -> Worker:
    """Create and configure a production Temporal Worker.

    Connects to the Temporal server, registers DSLWorkflow and all thin-shell activities,
    and applies SandboxRestrictions with Pydantic passthrough for performance.

    Args:
        host: Temporal server hostname (e.g., "localhost" for local dev).
        port: Temporal server port (e.g., 7233 for the default gRPC port).
        namespace: Temporal namespace to connect to (e.g., "default").
        task_queue: Task queue name this worker will poll (e.g., "order-processing").
            Must match the task_queue passed to TemporalAdapter.__init__().

    Returns:
        Configured Worker instance. Call await worker.run() to start polling.

    Example::

        worker = await create_worker("localhost", 7233, "default", "order-processing")
        await worker.run()
    """
    client = await Client.connect(
        f"{host}:{port}",
        namespace=namespace,
    )

    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[DSLWorkflow],
        activities=[
            validate_order_activity,
            process_payment_activity,
            fulfill_order_activity,
            send_confirmation_activity,
        ],
        workflow_runner=SandboxedWorkflowRunner(
            restrictions=SandboxRestrictions.default.with_passthrough_modules("pydantic")
        ),
    )
    return worker
```

**Pydantic passthrough:** The passthrough is a performance optimisation — it reduces workflow
startup overhead from hundreds of milliseconds to near zero by reusing the already-imported
Pydantic module instead of re-importing it inside the sandbox on every workflow execution.

**Activity registration — dual requirement:** Each activity in `activities=[...]` is the Temporal
registration. The same function calls `registry.get()` internally — that is the ActionRegistry
registration. See `stacks/python/registry.md` Section 6 for the dual registration explanation.

---

## Section 6: Import Boundary Enforcement (AST-based)

The import boundary rule — `import temporalio` must not appear outside `workflows/adapters/` —
is enforced by a pytest test that uses `ast.parse` to scan source files. AST inspection only
matches real import statements (not comments, docstrings, or string literals).

```python
# tests/test_import_boundary.py
# Phase 2 — Plan 2 verification: import boundary enforcement (ADPT-03)
# Fails if any .py file outside workflows/adapters/ and workers/ imports from temporalio.

import ast
from pathlib import Path

import pytest


def _collect_temporalio_imports(path: Path) -> list[str]:
    """Parse path with ast.parse and return any temporalio import lines found."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []  # Skip unparseable files

    # Build the forbidden prefix at runtime so this file itself does not contain it
    forbidden_pkg = "temporal" + "io"
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == forbidden_pkg or alias.name.startswith(forbidden_pkg + "."):
                    violations.append(
                        f"{path}:{node.lineno}: import {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == forbidden_pkg or module.startswith(forbidden_pkg + "."):
                names = ", ".join(a.name for a in node.names)
                violations.append(
                    f"{path}:{node.lineno}: from {module} import {names}"
                )

    return violations


def test_temporalio_import_boundary():
    """Verify temporalio is not imported outside the adapter layer.

    Scans all .py files under workflows/ excluding adapters/ and workers/
    (the permitted import zones). Fails with a clear list if any violations found.
    """
    workflows_root = Path("workflows")
    if not workflows_root.exists():
        pytest.skip(
            "workflows/ directory does not exist yet — "
            "create it from the reference files before running this test."
        )

    # Scan all .py files, excluding the permitted import zones
    violations: list[str] = []
    for py_file in sorted(workflows_root.rglob("*.py")):
        # Skip the adapter and worker directories — they are the permitted import zones
        relative = py_file.relative_to(workflows_root)
        parts = relative.parts
        if parts and parts[0] in ("adapters", "workers"):
            continue
        violations.extend(_collect_temporalio_imports(py_file))

    assert not violations, (
        "ADPT-03 VIOLATION: temporalio imported outside the adapter layer.\n"
        "Only workflows/adapters/ and workers/ may import temporalio.\n"
        "Violations found:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_adapter_file_imports_temporalio():
    """Verify temporal_adapter.py (the import zone) does import temporalio.

    This is the positive half of the import boundary test — confirms the adapter
    file actually uses temporalio, not just that others don't.
    """
    adapter_path = Path("workflows/adapters/temporal_adapter.py")
    if not adapter_path.exists():
        pytest.skip("workflows/adapters/temporal_adapter.py not yet created.")

    imports = _collect_temporalio_imports(adapter_path)
    assert imports, (
        "temporal_adapter.py must import from temporalio — "
        "it is the designated adapter import zone."
    )
```

---

## Section 7: Retry Policy Wiring

Per-step retry policies only. Steps without a `retry_policy` field fail immediately on error.

### `_build_retry_policy` Helper

```python
# workflows/adapters/temporal_adapter.py
# Source: python.temporal.io/temporalio.common.RetryPolicy.html
from temporalio.common import RetryPolicy as TemporalRetryPolicy
from datetime import timedelta


def _build_retry_policy(rp) -> TemporalRetryPolicy:
    """Map DSL RetryPolicy fields to temporalio.common.RetryPolicy.

    All five DSL fields are mapped 1:1. non_retryable_error_types are passed
    as string class names — NOT class references. Temporal serializes error
    types across the server boundary as strings.
    """
    return TemporalRetryPolicy(
        maximum_attempts=rp.max_attempts,
        initial_interval=timedelta(seconds=rp.initial_interval_seconds),
        backoff_coefficient=rp.backoff_coefficient,
        maximum_interval=(
            timedelta(seconds=rp.max_interval_seconds)
            if rp.max_interval_seconds is not None
            else None
        ),
        non_retryable_error_types=rp.non_retryable_error_types,
    )
```

### DSL Field Mapping Table

| DSL Field | Temporal Parameter | Notes |
|-----------|-------------------|-------|
| `max_attempts` | `maximum_attempts` | DSL Field ge=1 le=100 |
| `initial_interval_seconds` | `initial_interval` | Wrap in `timedelta(seconds=...)` |
| `backoff_coefficient` | `backoff_coefficient` | Direct float pass-through |
| `max_interval_seconds` | `maximum_interval` | `timedelta(seconds=...)` or None |
| `non_retryable_error_types` | `non_retryable_error_types` | `list[str]` — string names only |

### Non-Retryable Error Types

Pass them as **string class names**, not as Python class references:

```python
# Correct — string names
RetryPolicy(
    max_attempts=3,
    initial_interval_seconds=2,
    backoff_coefficient=2.0,
    non_retryable_error_types=["ValueError", "ValidationError"],
)

# Wrong — class references (raises at Temporal serialization boundary)
# non_retryable_error_types=[ValueError, ValidationError]  # DO NOT DO THIS
```

**Errors that should NOT retry** (business logic errors, bad input):
- `"ValueError"` — invalid input data that will fail again on retry
- `"ValidationError"` — Pydantic validation failed; the input is structurally wrong

**Errors that SHOULD retry** (transient infrastructure failures):
- `"ConnectionError"` — network partition; retry may succeed
- `"TimeoutError"` — downstream service slow; retry with backoff is appropriate

Order processing example — payment validation should not retry on bad card data:

```python
StepDefinition(
    id="process-payment",
    type="task",
    action="process_payment",
    timeout_seconds=30,
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_interval_seconds=2,
        backoff_coefficient=2.0,
        non_retryable_error_types=["ValueError", "ValidationError"],
    ),
)
```

---

## Section 8: Typed Signals and Queries

### Typed Signal Payload Pattern

Signal payload models live in the DSL layer — adapter imports from DSL, DSL never imports from
adapter (D-07):

```python
# workflows/dsl/models.py (or workflows/dsl/signals.py)
# Signal payload models live in the DSL layer
from pydantic import BaseModel
from typing import Optional


class ApprovalPayload(BaseModel):
    approved_by: str
    approved_at: str  # ISO 8601
    reason: Optional[str] = None
```

The typed `@workflow.signal` handler on `DSLWorkflow` (shown in Section 2 as `approval_received`)
uses the Pydantic data converter to deserialize the incoming payload directly into the typed
model. No manual parsing required.

### Signal-with-Start Pattern

Atomically start a workflow and deliver a signal in one operation:

```python
# workflows/adapters/temporal_adapter.py — client-side signal-with-start
# Source: docs.temporal.io/develop/python/message-passing
handle = await client.start_workflow(
    DSLWorkflow.run,
    args=[workflow_def, input],
    id=workflow_id,
    task_queue=task_queue,
    start_signal="approval_received",
    start_signal_args=[ApprovalPayload(approved_by="gateway", approved_at="2026-01-01T00:00:00Z")],
)
```

### Async Completion Pattern

An activity returns a "pending" status, and a subsequent signal completes the step:

1. Workflow reaches an `"event"` step → calls `_execute_event` → `workflow.wait_condition` suspends.
2. Preceding `"task"` step activity returns `{"status": "pending", ...}`.
3. Domain code calls `WorkflowEngine.signal()` with approval payload.
4. `DSLWorkflow.approval_received()` sets `_signal_received = True`, waking `wait_condition`.
5. `_execute_event` merges signal payload into state and returns — workflow continues.

A worker restart between steps 2 and 3 loses nothing — the wait is recorded in Temporal's event
history.

---

## Section 9: Running Example — Order Processing

### Step 1: Domain code starts the workflow

```python
# Domain service — zero temporalio imports
from workflows.dsl.models import StepDefinition, Transition, WorkflowDefinition
from workflows.ports.engine import ActivityError, WorkflowEngine, WorkflowTimeoutError


async def submit_order(engine: WorkflowEngine, order_id: str) -> dict:
    """Submit an order for processing. Engine is TemporalAdapter in production."""
    order_workflow = WorkflowDefinition(
        id="order-processing",
        version="1.0",
        steps=[
            StepDefinition(id="validate-order", type="task", action="validate_order"),
            StepDefinition(id="process-payment", type="task", action="process_payment"),
            StepDefinition(id="fulfill-order", type="task", action="fulfill_order"),
            StepDefinition(id="send-confirmation", type="task", action="send_confirmation"),
        ],
        transitions=[
            Transition(from_step="validate-order", to_step="process-payment"),
            Transition(from_step="process-payment", to_step="fulfill-order"),
            Transition(from_step="fulfill-order", to_step="send-confirmation"),
        ],
    )

    try:
        handle = await engine.start_workflow(
            order_workflow,
            {"order_id": "12345"},
            workflow_id=f"order-{order_id}",
        )
        result = await handle.result()
        return result
    except ActivityError as e:
        raise RuntimeError(f"Order {order_id}: activity '{e.activity_name}' failed") from e
    except WorkflowTimeoutError as e:
        raise RuntimeError(f"Order {order_id}: workflow timed out") from e
```

### Step 2: DSLWorkflow traverses the step graph

```
current_id = "validate-order"          # entry point (no incoming transitions)

Step 1 → _execute_task("validate-order", {"order_id": "12345"})
         → workflow.execute_activity("validate_order", {"order_id": "12345"}, ...)
         → returns {"order_id": "12345", "validated": True}

Step 2 → _execute_task("process-payment", {"order_id": "12345", "validated": True})
         → workflow.execute_activity("process_payment", {...}, ...)
         → returns {"order_id": "12345", "validated": True, "paid": True}

Step 3 → _execute_task("fulfill-order", {..., "paid": True})
         → workflow.execute_activity("fulfill_order", {...}, ...)
         → returns {..., "fulfilled": True}

Step 4 → _execute_task("send-confirmation", {..., "fulfilled": True})
         → workflow.execute_activity("send_confirmation", {...}, ...)
         → returns {..., "confirmed": True}

current_id = None                       # "send-confirmation" has no outgoing transitions
return {"order_id": "12345", "validated": True, "paid": True,
        "fulfilled": True, "confirmed": True}
```

### Step 3: Activities delegate through the ActionRegistry

```python
# workflows/adapters/activities.py
@activity.defn(name="validate_order")
async def validate_order_activity(state: dict) -> dict:
    fn = registry.get("validate_order")   # resolves to the @registry.action function
    return await fn(state)                # delegates to OrderService.validate(state)
```

### Step 4: Signal and query during execution

```python
# Send approval signal — wakes the event step
await engine.signal(
    workflow_id="order-12345",
    signal_name="receive_signal",
    payload={"approved_by": "payment-gateway", "transaction_id": "txn-789"},
)

# Query current state without blocking on workflow completion
status = await engine.query(
    workflow_id="order-12345",
    query_name="get_state",
)
# status → {"order_id": "12345", "validated": True, ...current step's state}
```

---

## Section 10: Verification Checkpoint

Save as `tests/test_adapter_checkpoint.py` and run with:

```
python -m pytest tests/test_adapter_checkpoint.py -v
```

This checkpoint verifies the adapter layer structure without requiring a running Temporal server.

```python
# tests/test_adapter_checkpoint.py
# Phase 2 — Plan 2 verification: TemporalAdapter structure + DSLWorkflow decorators + boundary

import ast
import importlib
import inspect
import sys
from pathlib import Path

import pytest


def test_temporal_adapter_has_workflow_engine_methods():
    """TemporalAdapter defines all three WorkflowEngine Protocol methods.

    Structural protocol check — does not require a live Temporal connection.
    Verifies method names and async-ness without running them.
    """
    adapter_path = Path("workflows/adapters/temporal_adapter.py")
    if not adapter_path.exists():
        pytest.skip("workflows/adapters/temporal_adapter.py not yet created.")

    spec = importlib.util.spec_from_file_location(
        "temporal_adapter", adapter_path
    )
    # Skip import if temporalio is not installed in test environment
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except ImportError:
        pytest.skip("temporalio not installed — skipping structural check.")

    adapter_cls = getattr(module, "TemporalAdapter", None)
    assert adapter_cls is not None, "TemporalAdapter class not found in temporal_adapter.py"

    for method_name in ("start_workflow", "signal", "query"):
        method = getattr(adapter_cls, method_name, None)
        assert method is not None, f"TemporalAdapter.{method_name} not found"
        assert inspect.iscoroutinefunction(method), (
            f"TemporalAdapter.{method_name} must be async"
        )


def test_dsl_workflow_has_defn_and_run():
    """DSLWorkflow is decorated with @workflow.defn and has a @workflow.run method.

    Checks both the class-level and method-level decorators are present via AST
    inspection — does not require temporalio to be installed.
    """
    adapter_path = Path("workflows/adapters/temporal_adapter.py")
    if not adapter_path.exists():
        pytest.skip("workflows/adapters/temporal_adapter.py not yet created.")

    source = adapter_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find class DSLWorkflow and check decorators
    dsl_workflow_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "DSLWorkflow":
            dsl_workflow_class = node
            break

    assert dsl_workflow_class is not None, "class DSLWorkflow not found in temporal_adapter.py"

    # Check @workflow.defn on the class
    decorator_names = []
    for dec in dsl_workflow_class.decorator_list:
        if isinstance(dec, ast.Attribute):
            decorator_names.append(f"{dec.value.id}.{dec.attr}")
        elif isinstance(dec, ast.Name):
            decorator_names.append(dec.id)
    assert "workflow.defn" in decorator_names, (
        "DSLWorkflow must be decorated with @workflow.defn"
    )

    # Check @workflow.run on the run method
    run_method_decorators = []
    for item in ast.walk(dsl_workflow_class):
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "run":
            for dec in item.decorator_list:
                if isinstance(dec, ast.Attribute):
                    run_method_decorators.append(f"{dec.value.id}.{dec.attr}")
    assert "workflow.run" in run_method_decorators, (
        "DSLWorkflow.run must be decorated with @workflow.run"
    )


def test_import_boundary_no_temporalio_outside_adapters():
    """Temporalio is not imported outside the adapter layer."""
    workflows_root = Path("workflows")
    if not workflows_root.exists():
        pytest.skip("workflows/ directory not yet created.")

    forbidden_pkg = "temporal" + "io"
    violations: list[str] = []

    for py_file in sorted(workflows_root.rglob("*.py")):
        relative = py_file.relative_to(workflows_root)
        if relative.parts and relative.parts[0] in ("adapters", "workers"):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == forbidden_pkg or alias.name.startswith(forbidden_pkg + "."):
                        violations.append(f"{py_file}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == forbidden_pkg or module.startswith(forbidden_pkg + "."):
                    violations.append(f"{py_file}:{node.lineno}: from {module} import ...")

    assert not violations, (
        "ADPT-03 VIOLATION: temporalio imported outside adapters/:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_create_worker_accepts_parametrized_config():
    """create_worker function accepts host, port, namespace, task_queue parameters.

    Verifies the function signature via AST — does not require temporalio or a
    running server.
    """
    worker_path = Path("workers/worker.py")
    if not worker_path.exists():
        pytest.skip("workers/worker.py not yet created.")

    source = worker_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    create_worker_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "create_worker":
            create_worker_fn = node
            break

    assert create_worker_fn is not None, "create_worker async function not found in workers/worker.py"

    arg_names = [arg.arg for arg in create_worker_fn.args.args]
    for expected_arg in ("host", "port", "namespace", "task_queue"):
        assert expected_arg in arg_names, (
            f"create_worker must accept '{expected_arg}' parameter. "
            "All configuration must flow through parameters (D-10)."
        )


def test_create_worker_has_no_env_var_reads():
    """create_worker does not read from the environment inside workers/worker.py.

    Enforces D-10: all configuration flows through function parameters.
    """
    worker_path = Path("workers/worker.py")
    if not worker_path.exists():
        pytest.skip("workers/worker.py not yet created.")

    source = worker_path.read_text(encoding="utf-8")
    # Build the forbidden pattern at runtime to avoid false positives in documentation
    env_attr = "os." + "environ"
    env_get = "environ." + "get"
    assert env_attr not in source, (
        f"D-10 VIOLATION: {env_attr} found in workers/worker.py. "
        "Pass all configuration as function parameters."
    )
    assert env_get not in source, (
        f"D-10 VIOLATION: {env_get} found in workers/worker.py. "
        "Pass all configuration as function parameters."
    )
```

**Full integration test** requires a running Temporal server:

```bash
temporal server start-dev
```

Then run the full stack:

```python
# integration_test_order.py — requires temporal server start-dev running on localhost:7233
import asyncio

from temporalio.client import Client
from workflows.adapters.temporal_adapter import TemporalAdapter
from workflows.dsl.models import StepDefinition, Transition, WorkflowDefinition

async def test_order_integration():
    client = await Client.connect("localhost:7233", namespace="default")
    adapter = TemporalAdapter(client, task_queue="order-processing")

    order_workflow = WorkflowDefinition(
        id="order-processing",
        version="1.0",
        steps=[
            StepDefinition(id="validate-order", type="task", action="validate_order"),
            StepDefinition(id="process-payment", type="task", action="process_payment"),
            StepDefinition(id="fulfill-order", type="task", action="fulfill_order"),
            StepDefinition(id="send-confirmation", type="task", action="send_confirmation"),
        ],
        transitions=[
            Transition(from_step="validate-order", to_step="process-payment"),
            Transition(from_step="process-payment", to_step="fulfill-order"),
            Transition(from_step="fulfill-order", to_step="send-confirmation"),
        ],
    )

    handle = await adapter.start_workflow(
        order_workflow,
        {"order_id": "12345"},
        workflow_id="order-12345-test",
    )
    result = await handle.result()

    assert result.get("validated") is True
    assert result.get("paid") is True
    assert result.get("fulfilled") is True
    assert result.get("confirmed") is True
    print(f"Integration test PASSED — result: {result}")

asyncio.run(test_order_integration())
```
