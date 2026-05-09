# DSL Layer — Python Implementation

For concepts, patterns, and design decisions, see `references/dsl.md`.

This file contains the complete Python implementation: Pydantic v2 models, graph validation
algorithms, validation pipeline, in-memory executor, order processing example, and pytest tests.

---

## Section 1: Core Models

Four Pydantic v2 model classes. Use `model_validator`, `field_validator`, and `Field` — never
`@validator`, `@root_validator`, or `class Config`.

```python
from pydantic import BaseModel, Field, model_validator, field_validator, ConfigDict
from typing import Literal, Optional


class RetryPolicy(BaseModel):
    """Controls retry behavior for a workflow step.

    Fields:
        max_attempts: Total number of execution attempts (1–100).
        initial_interval_seconds: Delay before the first retry (1–3600).
        backoff_coefficient: Multiplier applied to each subsequent interval (1.0–10.0).
        max_interval_seconds: Upper bound on the computed interval. Must be >= initial_interval_seconds.
        non_retryable_error_types: Optional list of exception class names (as strings) that
            stop the retry loop immediately. Pass string names, NOT class references.
            Added in Phase 3. Example: ["ValueError", "ValidationError"].
    """

    max_attempts: int = Field(ge=1, le=100)
    initial_interval_seconds: int = Field(ge=1, le=3600)
    backoff_coefficient: float = Field(ge=1.0, le=10.0)
    max_interval_seconds: Optional[int] = None
    non_retryable_error_types: Optional[list[str]] = None  # Added in Phase 3

    @model_validator(mode="after")
    def validate_max_interval(self) -> "RetryPolicy":
        if (
            self.max_interval_seconds is not None
            and self.max_interval_seconds < self.initial_interval_seconds
        ):
            raise ValueError("max_interval_seconds must be >= initial_interval_seconds")
        return self


class StepDefinition(BaseModel):
    """A single node in the workflow graph.

    Fields:
        id: Unique identifier for this step within the workflow.
        type: Execution category. Determines how the executor processes the step.
            - "task": Calls a registered action function. Requires `action`.
            - "decision": Routing node. Must not define `action`.
            - "parallel": Fork/join node. Must not define `action`.
            - "event": Waits for an external signal before proceeding.
        action: Name of the callable registered in the executor or action registry.
            Required for "task" steps. Must not be set for "decision" or "parallel" steps.
        timeout_seconds: Maximum wall-clock time for this step (1–86400). Defaults to 30.
        retry_policy: Optional retry configuration. When absent, the step fails immediately on error.
    """

    id: str = Field(min_length=1, max_length=100)
    type: Literal["task", "decision", "parallel", "event"]
    action: Optional[str] = None
    timeout_seconds: int = Field(default=30, ge=1, le=86400)
    retry_policy: Optional[RetryPolicy] = None

    @model_validator(mode="after")
    def validate_action_requirements(self) -> "StepDefinition":
        if self.type == "task" and not self.action:
            raise ValueError("task steps must define an action")
        if self.type in ("decision", "parallel") and self.action:
            raise ValueError(f"{self.type} steps must not define an action")
        return self


class Transition(BaseModel):
    """A directed edge in the workflow graph.

    Fields:
        from_step: ID of the source step.
        to_step: ID of the target step.
        condition: Optional expression string. When present, the transition fires only when
            the condition evaluates to True at runtime. Leave None for unconditional edges.
    """

    from_step: str
    to_step: str
    condition: Optional[str] = None


class WorkflowDefinition(BaseModel):
    """Complete workflow graph definition.

    Fields:
        id: Unique workflow identifier used for logging and persistence.
        version: Semantic version string. Increment when the graph shape changes.
        steps: Ordered list of StepDefinition nodes. IDs must be unique within this list.
        transitions: List of directed edges connecting steps. Defines execution order and routing.
    """

    id: str = Field(min_length=1, max_length=100)
    version: str
    steps: list[StepDefinition]
    transitions: list[Transition]

    @field_validator("steps")
    @classmethod
    def unique_step_ids(cls, steps: list[StepDefinition]) -> list[StepDefinition]:
        ids = [s.id for s in steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step ids must be unique")
        return steps
```

Rename `action` to match the project's naming convention if needed. All other field names are
canonical.

### Signal Payload Models (Phase 3)

Define signal payload models in the DSL layer — not in the adapter. The adapter imports these
from the DSL module, preserving the dependency direction (adapter depends on DSL, never the reverse).

```python
# workflows/dsl/models.py — add alongside the core models above

class ApprovalPayload(BaseModel):
    """Typed signal payload for human-in-the-loop approval steps."""
    approved_by: str
    approved_at: str  # ISO 8601 timestamp
    reason: Optional[str] = None
```

Add additional signal payload models as the project grows. Each payload is a Pydantic model
in the DSL layer, imported by the adapter's signal handler.

---

## Section 2: Graph Validation

Full implementation (not a skeleton). Call `validate_graph` after constructing a
`WorkflowDefinition` and before executing it. Enforces four structural constraints.

```python
from collections import deque


def validate_graph(defn: WorkflowDefinition) -> None:
    """4-constraint graph validation. Raises ValueError on any violation.

    Constraints:
        1. Exactly one entry point (step with no incoming transitions).
        2. At least one terminal step (step with no outgoing transitions).
        3. No orphan steps (all steps reachable from the entry point).
        4. No infinite loops without an event-type step in the cycle.
    """
    step_ids = {s.id for s in defn.steps}
    steps_with_incoming = {t.to_step for t in defn.transitions}
    steps_with_outgoing = {t.from_step for t in defn.transitions}

    # Constraint 1: Single entry point
    entry_steps = step_ids - steps_with_incoming
    if len(entry_steps) != 1:
        raise ValueError(f"Workflow must have exactly one entry point. Found: {entry_steps}")

    # Constraint 2: At least one terminal step
    terminal_steps = step_ids - steps_with_outgoing
    if not terminal_steps:
        raise ValueError("Workflow must have at least one terminal step (no outgoing transitions).")

    # Constraint 3: No orphan steps (all steps reachable from entry)
    entry_id = next(iter(entry_steps))
    reachable = _bfs_reachable(defn, entry_id)
    orphans = step_ids - reachable
    if orphans:
        raise ValueError(f"Orphan steps detected (unreachable from entry): {orphans}")

    # Constraint 4: No infinite loops without event break
    _assert_no_pure_loops(defn)


def _bfs_reachable(defn: WorkflowDefinition, start_id: str) -> set[str]:
    """Return the set of step IDs reachable from start_id via BFS."""
    adjacency: dict[str, list[str]] = {}
    for t in defn.transitions:
        adjacency.setdefault(t.from_step, []).append(t.to_step)

    visited: set[str] = set()
    queue: deque[str] = deque([start_id])
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        for neighbor in adjacency.get(node, []):
            if neighbor not in visited:
                queue.append(neighbor)
    return visited


def _assert_no_pure_loops(defn: WorkflowDefinition) -> None:
    """Raise ValueError if any cycle exists without an event-type step in it.

    Uses DFS with three-color marking:
        WHITE (0): not yet visited
        GRAY  (1): currently on the DFS stack (back edge = cycle detected)
        BLACK (2): fully explored

    A cycle is acceptable only when at least one step in the cycle has type == "event"
    (representing an event-driven waiting point that prevents infinite spin).
    """
    WHITE, GRAY, BLACK = 0, 1, 2

    adjacency: dict[str, list[str]] = {}
    for t in defn.transitions:
        adjacency.setdefault(t.from_step, []).append(t.to_step)

    step_type: dict[str, str] = {s.id: s.type for s in defn.steps}
    color: dict[str, int] = {s.id: WHITE for s in defn.steps}
    stack_path: list[str] = []

    def dfs(node: str) -> None:
        color[node] = GRAY
        stack_path.append(node)
        for neighbor in adjacency.get(node, []):
            if color[neighbor] == GRAY:
                # Back edge: cycle detected — extract cycle nodes from stack_path
                cycle_start = stack_path.index(neighbor)
                cycle_nodes = stack_path[cycle_start:]
                # Allow cycles that include at least one event-type step
                has_event = any(step_type.get(n) == "event" for n in cycle_nodes)
                if not has_event:
                    raise ValueError(
                        f"Infinite loop detected with no event break: {cycle_nodes}. "
                        "Add an 'event' type step to the cycle to make it event-driven."
                    )
            elif color[neighbor] == WHITE:
                dfs(neighbor)
        stack_path.pop()
        color[node] = BLACK

    for step in defn.steps:
        if color[step.id] == WHITE:
            dfs(step.id)
```

**BFS** (Breadth-First Search) in `_bfs_reachable` detects orphan steps — any step not reachable
from the entry point will be missing from the `visited` set.

**DFS three-color marking** in `_assert_no_pure_loops` detects back edges (cycles). GRAY nodes
are "on the current DFS stack" — a back edge to a GRAY node means we found a cycle. The cycle
is only allowed if an `"event"` step exists in it (preventing infinite spin).

---

## Section 3: Schema Validation Pipeline

Four sequential stages. Each catches a distinct class of problem.

1. **Schema validation** — Pydantic handles this at model construction time. Type checking,
   field constraints (`Field(ge=1, le=100)`), and cross-field validators (`model_validator`)
   run automatically when the model is instantiated. A `ValidationError` means the YAML/JSON
   input is malformed.

2. **Graph validation** — `validate_graph()` checks structural integrity: entry point,
   terminal steps, orphan detection, loop detection. A `ValueError` means the workflow graph
   is logically broken.

3. **Execution constraint validation** — Checks that runtime values are within safe bounds:
   timeout totals, retry backoff ceilings, step count limits. A `ValueError` means the workflow
   would be unreliable or unsafe.

4. **Action contract validation** — Verifies every `action` string referenced in steps has a
   corresponding registered handler. Runs at executor-creation time, not at model-construction
   time, because the registry is assembled after the workflow is defined.

```python
def validate_workflow(
    defn: WorkflowDefinition,
    registry: dict[str, callable] | None = None,
) -> None:
    """Run full validation pipeline. Raises ValueError on any failure.

    Args:
        defn: The workflow definition to validate.
        registry: Optional map of action name -> callable. When provided,
            Stage 4 verifies all referenced actions are registered.
    """
    # Stage 1: Schema — already passed (Pydantic validated at construction)
    # Stage 2: Graph
    validate_graph(defn)
    # Stage 3: Execution constraints
    _validate_execution_constraints(defn)
    # Stage 4: Action contracts (if registry provided)
    if registry is not None:
        _validate_action_contracts(defn, registry)


def _validate_execution_constraints(defn: WorkflowDefinition) -> None:
    """Check execution-time safety constraints."""
    for step in defn.steps:
        if step.retry_policy:
            rp = step.retry_policy
            # Verify backoff ceiling: initial * coefficient^(max_attempts-1) must be bounded
            if rp.max_interval_seconds is None and rp.backoff_coefficient > 2.0 and rp.max_attempts > 10:
                raise ValueError(
                    f"Step '{step.id}': backoff_coefficient={rp.backoff_coefficient} with "
                    f"max_attempts={rp.max_attempts} and no max_interval_seconds cap "
                    "produces unbounded retry intervals. Set max_interval_seconds."
                )


def _validate_action_contracts(
    defn: WorkflowDefinition,
    registry: dict[str, callable],
) -> None:
    """Verify every action referenced in the workflow has a registered handler."""
    missing = [
        step.id
        for step in defn.steps
        if step.action and step.action not in registry
    ]
    if missing:
        raise ValueError(
            f"Steps reference unregistered actions: {missing}. "
            "Register all actions before running the workflow."
        )
```

---

## Section 4: In-Memory Executor

Runs a `WorkflowDefinition` without Temporal infrastructure. Use it to validate DSL models
and graph correctness before connecting to a Temporal server.

```python
class InMemoryExecutor:
    """Executes a WorkflowDefinition without any Temporal infrastructure.

    Register action handlers by name before calling `run`. The executor resolves
    each step's `action` string to a registered callable and passes the accumulated
    state through the workflow graph.

    Usage::

        executor = InMemoryExecutor()
        executor.register("my_action", lambda state: {**state, "done": True})
        result = executor.run(workflow_definition, {"input_key": "value"})
    """

    def __init__(self) -> None:
        self._actions: dict[str, callable] = {}

    def register(self, name: str, fn: callable) -> None:
        """Register an action handler by name.

        Args:
            name: The action name as it appears in StepDefinition.action.
            fn: A callable that accepts a dict (state) and returns a dict (updated state).
        """
        self._actions[name] = fn

    def run(self, workflow: WorkflowDefinition, input: dict) -> dict:
        """Execute workflow steps in graph order. Raises on missing action.

        Validates the graph before execution. Traverses from the entry step, calling
        registered action handlers for each "task" step. Returns the final accumulated
        state with `"status": "completed"` appended.

        Args:
            workflow: A fully constructed and valid WorkflowDefinition.
            input: Initial state dict passed to the first step.

        Returns:
            Final state dict with "status" key set to "completed".

        Raises:
            ValueError: If graph validation fails.
            KeyError: If a "task" step references an unregistered action.
            NotImplementedError: If a "decision", "parallel", or "event" step is encountered
                (Phase 1 executor handles "task" steps only; other types are wired in Phase 2).
        """
        validate_graph(workflow)

        step_map = {s.id: s for s in workflow.steps}
        transition_map: dict[str, list[str]] = {}
        for t in workflow.transitions:
            transition_map.setdefault(t.from_step, []).append(t.to_step)

        steps_with_incoming = {t.to_step for t in workflow.transitions}
        entry_id = next(s.id for s in workflow.steps if s.id not in steps_with_incoming)

        state = dict(input)
        current_id: str | None = entry_id

        while current_id is not None:
            step = step_map[current_id]

            if step.type == "task":
                fn = self._actions.get(step.action)  # type: ignore[arg-type]
                if not fn:
                    raise KeyError(
                        f"Action '{step.action}' not registered in executor. "
                        "Call executor.register(name, fn) before running."
                    )
                state = fn(state)
            elif step.type in ("decision", "parallel", "event"):
                raise NotImplementedError(
                    f"Step '{step.id}' has type '{step.type}'. "
                    "The Phase 1 executor handles 'task' steps only. "
                    "'decision', 'parallel', and 'event' step types are defined in the schema "
                    "but are wired in the Phase 2 Temporal adapter."
                )

            next_ids = transition_map.get(current_id, [])
            current_id = next_ids[0] if next_ids else None

        return {**state, "status": "completed"}
```

The Phase 1 executor handles `task` steps only. The Phase 2 adapter (`stacks/python/adapter.md`)
handles all four step types including `decision`, `parallel`, and `event`.

---

## Section 5: Running Example — Order Processing

This example is used throughout all phases for consistency. Substitute step IDs, action names,
and field values for your domain.

```python
# Running example: Order Processing Workflow

workflow = WorkflowDefinition(
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

# Register stub actions for the in-memory executor
executor = InMemoryExecutor()
executor.register("validate_order", lambda s: {**s, "validated": True})
executor.register("process_payment", lambda s: {**s, "paid": True})
executor.register("fulfill_order", lambda s: {**s, "fulfilled": True})
executor.register("send_confirmation", lambda s: {**s, "confirmed": True})

result = executor.run(workflow, {"order_id": "12345"})
assert result["status"] == "completed"
assert result["confirmed"] is True
print("Order processing workflow: PASSED")
```

Graph structure:

```
validate-order → process-payment → fulfill-order → send-confirmation
```

- Entry point: `validate-order` (no incoming transitions)
- Terminal step: `send-confirmation` (no outgoing transitions)
- All steps reachable from entry
- No cycles

---

## Section 6: Verification Checkpoint

Save as `tests/test_dsl_checkpoint.py` and run with:

```
python -m pytest tests/test_dsl_checkpoint.py -v
```

All six tests must pass before proceeding to Phase 2.

```python
# tests/test_dsl_checkpoint.py
# Phase 1 verification: DSL models + graph validation + in-memory executor

import pytest
from workflows.dsl.models import WorkflowDefinition, StepDefinition, Transition, RetryPolicy
from workflows.dsl.validation import validate_graph
from workflows.dsl.executor import InMemoryExecutor


def test_order_processing_workflow():
    """Phase 1 verification: DSL models + validation + executor work end-to-end."""
    workflow = WorkflowDefinition(
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

    # Graph validation must pass without raising
    validate_graph(workflow)

    executor = InMemoryExecutor()
    executor.register("validate_order", lambda s: {**s, "validated": True})
    executor.register("process_payment", lambda s: {**s, "paid": True})
    executor.register("fulfill_order", lambda s: {**s, "fulfilled": True})
    executor.register("send_confirmation", lambda s: {**s, "confirmed": True})

    result = executor.run(workflow, {"order_id": "12345"})
    assert result["status"] == "completed"
    assert result["confirmed"] is True
    assert result["validated"] is True
    assert result["paid"] is True
    assert result["fulfilled"] is True


def test_invalid_graph_no_entry():
    """Graph validation raises when no single entry point exists."""
    # All steps have incoming transitions — circular graph with no entry
    with pytest.raises(ValueError, match="exactly one entry point"):
        workflow = WorkflowDefinition(
            id="circular",
            version="1.0",
            steps=[
                StepDefinition(id="step-a", type="task", action="action_a"),
                StepDefinition(id="step-b", type="task", action="action_b"),
            ],
            transitions=[
                Transition(from_step="step-a", to_step="step-b"),
                Transition(from_step="step-b", to_step="step-a"),
            ],
        )
        validate_graph(workflow)


def test_missing_action_raises_on_run():
    """Executor raises KeyError when a task step references an unregistered action."""
    workflow = WorkflowDefinition(
        id="order-processing",
        version="1.0",
        steps=[
            StepDefinition(id="validate-order", type="task", action="validate_order"),
        ],
        transitions=[],
    )

    executor = InMemoryExecutor()
    # Intentionally omit registering "validate_order"

    with pytest.raises(KeyError, match="validate_order"):
        executor.run(workflow, {"order_id": "12345"})


def test_retry_policy_max_interval_validation():
    """RetryPolicy raises when max_interval_seconds < initial_interval_seconds."""
    with pytest.raises(Exception):
        RetryPolicy(
            max_attempts=3,
            initial_interval_seconds=60,
            backoff_coefficient=2.0,
            max_interval_seconds=30,  # Invalid: less than initial_interval_seconds
        )


def test_task_step_requires_action():
    """StepDefinition raises when type='task' but action is missing."""
    with pytest.raises(Exception, match="task steps must define an action"):
        StepDefinition(id="my-step", type="task")  # action missing


def test_decision_step_must_not_have_action():
    """StepDefinition raises when type='decision' but action is set."""
    with pytest.raises(Exception, match="decision steps must not define an action"):
        StepDefinition(id="my-decision", type="decision", action="some_action")
```
