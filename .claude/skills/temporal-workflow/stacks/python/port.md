# Engine Port Layer — Python Implementation

For concepts, patterns, and design decisions, see `references/port.md`.

This file contains the complete Python implementation: `typing.Protocol` with
`@runtime_checkable`, `WorkflowHandle[T]` generic, domain exception classes, optional extension
protocols, order processing example, and pytest tests.

All code in this file is Temporal-free. Import only from the Python standard library and the
DSL layer. The adapter layer (Phase 2) satisfies the Protocol without the domain layer ever
depending on the Temporal SDK.

---

## Section 1: WorkflowEngine Protocol

Define `WorkflowEngine` using `typing.Protocol` with `@runtime_checkable`. Structural subtyping
means `TemporalAdapter` satisfies the protocol without inheriting from it or importing from this
file. Domain code depends on this protocol — never on the concrete adapter.

```python
# workflows/ports/engine.py
from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from workflows.dsl.models import WorkflowDefinition

T = TypeVar("T")
```

Three core methods form the complete engine interface. Every adapter — Temporal, local, test
double — must implement all three:

```python
@runtime_checkable
class WorkflowEngine(Protocol):
    """Abstraction boundary between domain code and the workflow runtime.

    Domain code depends on this protocol. TemporalAdapter satisfies it structurally —
    no inheritance from WorkflowEngine or import of this module is required in the adapter.

    Structural subtyping: any class that defines these three async methods satisfies
    the protocol. Use isinstance(obj, WorkflowEngine) at runtime to verify (enabled by
    @runtime_checkable).

    This file contains zero engine-SDK imports. The adapter layer is the only component
    that imports the Temporal SDK.
    """

    async def start_workflow(
        self,
        workflow: WorkflowDefinition,
        input: dict,
        workflow_id: str | None = None,
    ) -> "WorkflowHandle": ...
    """Start a workflow from a DSL definition.

    Args:
        workflow: The WorkflowDefinition describing the graph to execute.
        input: Initial state dictionary passed to the first step.
        workflow_id: Optional stable identifier. When None, the adapter generates one.

    Returns:
        WorkflowHandle typed to the workflow result type.
    """

    async def signal(
        self,
        workflow_id: str,
        signal_name: str,
        payload: dict,
    ) -> None: ...
    """Send a named signal to a running workflow.

    Args:
        workflow_id: The identifier of the target workflow instance.
        signal_name: Name of the signal as registered in the workflow.
        payload: Signal data. Must be JSON-serialisable.
    """

    async def query(
        self,
        workflow_id: str,
        query_name: str,
    ) -> Any: ...
    """Query the current state of a running workflow.

    Args:
        workflow_id: The identifier of the target workflow instance.
        query_name: Name of the query handler registered in the workflow.

    Returns:
        The query result. The type depends on the query handler implementation.
    """
```

`@runtime_checkable` enables `isinstance(obj, WorkflowEngine)` at runtime. Without it,
`isinstance` raises `TypeError` for Protocol types.

---

## Section 2: WorkflowHandle Protocol

`WorkflowHandle[T]` is returned by `start_workflow`. Callers interact with a running workflow
instance through the handle — send signals, issue queries, and await the final result.

```python
class WorkflowHandle(Generic[T], Protocol):
    """Object-oriented interface to a running workflow instance.

    Generic over T — the result type of the workflow. Use WorkflowHandle[dict] when the
    result type is not known statically (the common case for DSL-driven workflows).

    Returned by WorkflowEngine.start_workflow. Never constructed directly by domain code.
    """

    async def signal(self, signal_name: str, payload: dict) -> None: ...
    """Send a named signal to this workflow instance.

    Args:
        signal_name: Name of the signal handler registered in the workflow.
        payload: Signal data. Must be JSON-serialisable.
    """

    async def query(self, query_name: str) -> Any: ...
    """Query the current state of this workflow instance.

    Args:
        query_name: Name of the query handler registered in the workflow.

    Returns:
        The query result.
    """

    async def result(self) -> T: ...
    """Await the final result of this workflow instance.

    Blocks until the workflow reaches a terminal state.

    Returns:
        The final state dict (or typed result T) after all steps complete.

    Raises:
        WorkflowError: If the workflow fails or times out.
        ActivityError: If an activity fails after all retries.
        WorkflowTimeoutError: If the workflow exceeds its execution timeout.
    """
```

Use `WorkflowHandle[dict]` for DSL-driven workflows where the result type is the accumulated
state dictionary. Type the handle more specifically when the workflow returns a known model type.

---

## Section 3: Domain Exception Hierarchy

Define all workflow exceptions in the port layer. The adapter catches engine-SDK exceptions and
translates them into these domain exceptions before re-raising. Domain code catches only these
exceptions — never SDK exception types.

```python
class WorkflowError(Exception):
    """Base class for all workflow engine errors.

    The adapter catches engine exceptions and re-raises as WorkflowError or one of
    its subclasses. Domain code catches WorkflowError to handle any engine failure
    without depending on the adapter layer.

    Attributes:
        message: Human-readable description of the failure.
        workflow_id: Identifier of the workflow instance that failed, if available.
    """

    def __init__(self, message: str, workflow_id: str | None = None) -> None:
        super().__init__(message)
        self.workflow_id = workflow_id


class ActivityError(WorkflowError):
    """Raised when an activity execution fails after all retries.

    The adapter raises this when an engine-level ActivityError surfaces after the
    retry policy is exhausted. Domain code catches ActivityError to distinguish
    activity failures from other workflow errors.

    Attributes:
        activity_name: Name of the activity function that failed.
        workflow_id: Identifier of the enclosing workflow instance.
    """

    def __init__(
        self,
        message: str,
        activity_name: str,
        workflow_id: str | None = None,
    ) -> None:
        super().__init__(message, workflow_id)
        self.activity_name = activity_name


class WorkflowTimeoutError(WorkflowError):
    """Raised when a workflow exceeds its execution timeout.

    The adapter raises this when the engine reports a workflow timeout. Domain code
    catches WorkflowTimeoutError to implement timeout-specific recovery logic.
    """
```

All three exceptions are catchable as `WorkflowError`. Domain code typically catches the base
class for general error handling, and specific subclasses for targeted recovery logic.

---

## Section 4: Optional Extension Protocols

These protocols extend the core `WorkflowEngine` interface with advanced lifecycle operations.
Wire them in Phase 3 when production hardening requires them.

```python
class WorkflowManagement(Protocol):
    """Optional extension: lifecycle control for running workflow instances.

    Wire in Phase 3 when the application needs to cancel or terminate workflows.
    TemporalAdapter implements this alongside WorkflowEngine without inheriting from it.
    """

    async def cancel(self, workflow_id: str) -> None: ...
    """Request cooperative cancellation of a running workflow.

    The workflow receives a cancellation signal and can perform cleanup before stopping.

    Args:
        workflow_id: Identifier of the workflow to cancel.
    """

    async def terminate(self, workflow_id: str, reason: str) -> None: ...
    """Forcibly terminate a running workflow immediately.

    Unlike cancel, terminate does not allow the workflow to clean up. Use only
    when cooperative cancellation is insufficient.

    Args:
        workflow_id: Identifier of the workflow to terminate.
        reason: Human-readable explanation logged with the termination event.
    """


class WorkflowObservation(Protocol):
    """Optional extension: introspection into running workflow instances.

    Wire in Phase 3 when observability requires inspecting workflow state.
    """

    async def describe(self, workflow_id: str) -> dict: ...
    """Return a snapshot of the workflow instance's current state.

    Args:
        workflow_id: Identifier of the workflow to describe.

    Returns:
        Dictionary with keys: status, start_time, close_time, execution_time,
        and any additional metadata provided by the engine.
    """
```

`TemporalAdapter` can implement both `WorkflowManagement` and `WorkflowObservation` alongside
`WorkflowEngine` without inheriting from any of them — structural subtyping handles all three.

---

## Section 5: Running Example — Order Processing

Domain code calls through `WorkflowEngine` without knowing whether the engine is `TemporalAdapter`,
an in-memory stub, or a test double.

```python
# Example: domain service calling through the WorkflowEngine Protocol
from __future__ import annotations

from workflows.dsl.models import WorkflowDefinition, StepDefinition, Transition
from workflows.ports.engine import WorkflowEngine, ActivityError, WorkflowTimeoutError


async def submit_order(engine: WorkflowEngine, order_id: str) -> dict:
    """Submit an order for processing through the workflow engine.

    The engine parameter accepts any object that satisfies WorkflowEngine Protocol.
    In production this is TemporalAdapter. In tests this is a stub or mock.
    """
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
        # Activity failed after retries — surface domain-level error
        raise RuntimeError(
            f"Order {order_id}: activity '{e.activity_name}' failed — {e}"
        ) from e

    except WorkflowTimeoutError as e:
        # Workflow exceeded execution timeout
        raise RuntimeError(
            f"Order {order_id}: workflow timed out — {e}"
        ) from e
```

Sending a signal to a running order workflow:

```python
# Signal an approval event to a waiting workflow instance
await engine.signal(
    workflow_id="order-12345",
    signal_name="payment_approved",
    payload={"approved_by": "payment-gateway", "transaction_id": "txn-789"},
)

# Query the current order status without blocking
status = await engine.query(
    workflow_id="order-12345",
    query_name="order_status",
)
```

Using the typed `WorkflowHandle[dict]` pattern:

```python
from workflows.ports.engine import WorkflowHandle

# Handle typed to dict — DSL workflows accumulate state as a dictionary
handle: WorkflowHandle[dict] = await engine.start_workflow(
    order_workflow,
    {"order_id": "12345"},
)

# Send a signal through the handle (alternative to engine.signal)
await handle.signal("payment_approved", {"transaction_id": "txn-789"})

# Await the final accumulated state
result: dict = await handle.result()
assert result["status"] == "completed"
```

---

## Section 6: Verification Checkpoint

Save as `tests/test_port_checkpoint.py` and run with:

```
python -m pytest tests/test_port_checkpoint.py -v
```

All tests must pass and the import boundary test must confirm the port file is engine-SDK-free.

```python
# tests/test_port_checkpoint.py
# Phase 2 — Plan 1 verification: WorkflowEngine Protocol + domain exceptions + import boundary

import ast
from pathlib import Path

import pytest

from workflows.ports.engine import (
    ActivityError,
    WorkflowEngine,
    WorkflowError,
    WorkflowHandle,
    WorkflowTimeoutError,
)


def test_workflow_engine_is_runtime_checkable():
    """WorkflowEngine Protocol is @runtime_checkable and has all three required methods."""

    # Confirm @runtime_checkable — isinstance check must not raise TypeError
    class StubEngine:
        async def start_workflow(self, workflow, input, workflow_id=None):
            ...

        async def signal(self, workflow_id, signal_name, payload):
            ...

        async def query(self, workflow_id, query_name):
            ...

    engine = StubEngine()
    assert isinstance(engine, WorkflowEngine), (
        "StubEngine with all three async methods must satisfy WorkflowEngine Protocol"
    )


def test_workflow_engine_incomplete_does_not_satisfy():
    """A class missing required methods does not satisfy WorkflowEngine Protocol."""

    class IncompleteEngine:
        async def start_workflow(self, workflow, input, workflow_id=None):
            ...

        # Missing signal and query methods

    incomplete = IncompleteEngine()
    assert not isinstance(incomplete, WorkflowEngine), (
        "IncompleteEngine missing signal and query must NOT satisfy WorkflowEngine Protocol"
    )


def test_domain_exceptions_instantiate_and_catch():
    """Domain exceptions instantiate correctly and can be caught as WorkflowError."""

    # WorkflowError — base exception
    err = WorkflowError("something failed", workflow_id="order-12345")
    assert err.workflow_id == "order-12345"
    assert str(err) == "something failed"

    # ActivityError — caught as WorkflowError
    act_err = ActivityError(
        "payment failed",
        activity_name="process_payment",
        workflow_id="order-12345",
    )
    assert act_err.activity_name == "process_payment"
    assert act_err.workflow_id == "order-12345"
    assert isinstance(act_err, WorkflowError), "ActivityError must be a WorkflowError"

    # WorkflowTimeoutError — caught as WorkflowError
    timeout_err = WorkflowTimeoutError("timed out", workflow_id="order-12345")
    assert isinstance(timeout_err, WorkflowError), (
        "WorkflowTimeoutError must be a WorkflowError"
    )

    # All three catchable as base WorkflowError
    for exc in (err, act_err, timeout_err):
        try:
            raise exc
        except WorkflowError:
            pass  # Correct — all domain exceptions caught as base class


def test_port_layer_import_boundary():
    """The port layer file (workflows/ports/engine.py) is free of engine-SDK imports.

    This is the import boundary test — PORT-03. Parses the AST to detect any
    import of the Temporal SDK or similar engine packages that would violate the
    abstraction boundary.
    """
    engine_path = Path("workflows/ports/engine.py")
    if not engine_path.exists():
        pytest.skip(
            "workflows/ports/engine.py does not exist yet — create it from port.md Section 1"
        )

    source = engine_path.read_text()
    tree = ast.parse(source)

    # Build forbidden prefix at runtime to keep this documentation file import-free
    engine_pkg = "temporal" + "io"
    sdk_imports = []
    forbidden_prefixes = (engine_pkg,)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name.startswith(p) for p in forbidden_prefixes):
                    sdk_imports.append(f"import {alias.name} (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom):
            if node.module and any(
                node.module.startswith(p) for p in forbidden_prefixes
            ):
                sdk_imports.append(
                    f"from {node.module} import ... (line {node.lineno})"
                )

    assert not sdk_imports, (
        f"PORT-03 VIOLATION: engine-SDK imports found in workflows/ports/engine.py:\n"
        + "\n".join(f"  {i}" for i in sdk_imports)
    )
```
