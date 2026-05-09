# Action Registry — Python Implementation

For concepts, patterns, and design decisions, see `references/registry.md`.

This file contains the complete Python implementation: `ActionContract` Pydantic v2 model,
`ActionRegistry` class with `@registry.action()` decorator factory, thin-shell activity pattern,
dual registration explanation, and pytest tests.

Sections 1–3 and 5–7 are infrastructure-free. Section 4 (thin-shell activities) is the only
section that imports from the Temporal SDK.

---

## Section 1: ActionContract Model

`ActionContract` declares metadata about a registered action. Store one contract per registered
callable to enable runtime introspection without invoking the action.

```python
# workflows/registry/actions.py
from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, Field


class ActionContract(BaseModel):
    """Metadata contract for a registered action.

    Stores the action's declared properties alongside the callable in the registry.
    Enables runtime introspection of action characteristics without invoking the action.

    Fields:
        name: The registration key used in StepDefinition.action.
        idempotent: True when the action can be called multiple times with the same input
            and always produce the same result. Idempotent actions are safe to retry
            without side-effect accumulation.
        input_schema: JSON Schema dict describing expected input structure. Empty dict
            means no schema validation is applied.
        output_schema: JSON Schema dict describing the returned output structure. Empty dict
            means no schema validation is applied.
    """

    name: str
    idempotent: bool = False
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
```

---

## Section 2: ActionRegistry Class

`ActionRegistry` maintains two parallel dictionaries: one mapping action names to callables,
one mapping action names to their `ActionContract` metadata.

```python
class ActionRegistry:
    """Registry mapping action name strings to callable implementations.

    DSL steps reference actions by name (StepDefinition.action = "validate_order").
    The registry resolves these names to actual Python callables at execution time.

    Two registration paths:
        1. Decorator: @registry.action("validate_order") — registers at import time.
        2. Imperative: registry.register("validate_order", fn) — for programmatic registration.

    Module-level singleton usage::

        registry = ActionRegistry()

        @registry.action("validate_order", idempotent=True)
        async def validate_order(state: dict) -> dict:
            ...
    """

    def __init__(self) -> None:
        self._callables: dict[str, Callable] = {}
        self._contracts: dict[str, ActionContract] = {}

    def action(self, name: str, *, idempotent: bool = False) -> Callable:
        """Decorator factory that registers the decorated function under name.

        The decorator runs at module import time. The decorated module must be imported
        before registry.get() is called (see Section 3 for import ordering).

        Args:
            name: The registration key. Must match StepDefinition.action exactly.
            idempotent: Declare whether this action can safely be retried without
                accumulating side effects. Defaults to False.

        Returns:
            A decorator that registers the function and returns it unchanged.

        Example::

            @registry.action("validate_order", idempotent=True)
            async def validate_order(state: dict) -> dict:
                return {**state, "validated": True}
        """

        def decorator(fn: Callable) -> Callable:
            self.register(name, fn, idempotent=idempotent)
            return fn

        return decorator

    def register(self, name: str, fn: Callable, *, idempotent: bool = False) -> None:
        """Imperatively register a callable under name.

        Use when the decorator pattern is not possible — for example, when registering
        lambda functions, dynamically generated callables, or functions from third-party
        modules.

        Args:
            name: The registration key. Must match StepDefinition.action exactly.
            fn: The callable to register. Accepts a dict (state) and returns a dict.
            idempotent: Declare whether this action can safely be retried.
        """
        self._callables[name] = fn
        self._contracts[name] = ActionContract(name=name, idempotent=idempotent)

    def get(self, name: str) -> Callable:
        """Resolve an action name to its registered callable.

        Args:
            name: The action name string from StepDefinition.action.

        Returns:
            The callable registered under name.

        Raises:
            KeyError: If no callable is registered under name. The message includes the
                registered names to help diagnose import-ordering issues.
        """
        if name not in self._callables:
            available = sorted(self._callables.keys())
            raise KeyError(
                f"Action '{name}' is not registered. "
                f"Registered actions: {available}. "
                "Import the module where actions are decorated before calling registry.get()."
            )
        return self._callables[name]

    def get_contract(self, name: str) -> ActionContract:
        """Return the ActionContract for a registered action.

        Args:
            name: The action name string.

        Returns:
            ActionContract with name, idempotent, input_schema, output_schema.

        Raises:
            KeyError: If name is not registered.
        """
        if name not in self._contracts:
            raise KeyError(f"No contract for action '{name}'. Register it first.")
        return self._contracts[name]

    def registered_names(self) -> list[str]:
        """Return a sorted list of all registered action names.

        Returns:
            Sorted list of action name strings.
        """
        return sorted(self._callables.keys())


# Module-level singleton — import this instance everywhere
registry = ActionRegistry()
```

---

## Section 3: Decorator Registration Pattern

The `@registry.action` decorator registers the function at module import time. The decorator
factory pattern keeps the registration call co-located with the function definition.

```python
# Example: registering order processing actions
from workflows.registry.actions import registry


@registry.action("validate_order", idempotent=True)
async def validate_order(state: dict) -> dict:
    """Validate order fields. Idempotent — safe to retry."""
    # Delegates to OrderService — no business logic here
    return await OrderService.validate(state)


@registry.action("process_payment")
async def process_payment(state: dict) -> dict:
    """Charge the payment method. Not idempotent — each call charges once."""
    return await PaymentService.charge(state)
```

**Import ordering requirement:** The decorator runs at import time, not at decoration time of
the workflow definition. The module containing decorated functions must be imported before
`registry.get()` is called.

**Pitfall — Action not found at runtime:**

```python
# WRONG: registry.get() called before the decorated module is imported
from workflows.registry.actions import registry
result = registry.get("validate_order")  # KeyError — decorated module not imported yet

# CORRECT: import the decorated module first, then resolve
import workflows.actions.order_actions  # noqa: F401  — import for side effect (registration)
from workflows.registry.actions import registry
result = registry.get("validate_order")  # Resolves correctly
```

The worker startup code and application initialization code must import all modules containing
`@registry.action` decorated functions before any registry resolution occurs.

**Idempotency declaration:**

```python
# Idempotent: safe to retry without accumulating side effects
@registry.action("validate_order", idempotent=True)
async def validate_order(state: dict) -> dict: ...

# Not idempotent: each invocation has observable side effects (charges payment, sends email)
@registry.action("process_payment")
async def process_payment(state: dict) -> dict: ...

@registry.action("send_confirmation")
async def send_confirmation(state: dict) -> dict: ...
```

Idempotency is stored in the `ActionContract` and accessible via
`registry.get_contract(name).idempotent`. The adapter layer uses this to inform retry behavior
decisions at the DSL-to-Temporal translation point.

---

## Section 4: Thin-Shell Activity Pattern

**This code lives in `workflows/adapters/activities.py` — the only file besides
`temporal_adapter.py` that imports from the Temporal SDK.**

Activities are thin shells: resolve the callable from the registry, delegate to the application
service, and return the result. No business logic belongs in an activity function.

```python
# workflows/adapters/activities.py
# This is adapter-layer code — the only file that imports the Temporal SDK
# alongside temporal_adapter.py.
from __future__ import annotations

from temporalio import activity

from workflows.registry.actions import registry


@activity.defn(name="validate_order")
async def validate_order_activity(state: dict) -> dict:
    """Thin shell: resolves and delegates to the registered validate_order action."""
    fn = registry.get("validate_order")
    return await fn(state)


@activity.defn(name="process_payment")
async def process_payment_activity(state: dict) -> dict:
    """Thin shell: resolves and delegates to the registered process_payment action."""
    fn = registry.get("process_payment")
    return await fn(state)


@activity.defn(name="fulfill_order")
async def fulfill_order_activity(state: dict) -> dict:
    """Thin shell: resolves and delegates to the registered fulfill_order action."""
    fn = registry.get("fulfill_order")
    return await fn(state)


@activity.defn(name="send_confirmation")
async def send_confirmation_activity(state: dict) -> dict:
    """Thin shell: resolves and delegates to the registered send_confirmation action."""
    fn = registry.get("send_confirmation")
    return await fn(state)
```

**Anti-pattern — business logic inside the activity:**

```python
# WRONG: business logic, branching, and multiple service calls inside the activity
@activity.defn(name="process_payment")
async def process_payment_activity(state: dict) -> dict:
    order = await OrderService.get(state["order_id"])
    if order.total > 1000:
        result = await PaymentService.charge_high_value(order)
    else:
        result = await PaymentService.charge_standard(order)
    await NotificationService.notify_payment(order.id, result)
    return {**state, "payment_id": result.id}
```

**Correct pattern — one call deep, no branching:**

```python
# CORRECT: one call to the registered action, which delegates to the service
@activity.defn(name="process_payment")
async def process_payment_activity(state: dict) -> dict:
    fn = registry.get("process_payment")
    return await fn(state)
```

The business logic (high-value routing, notification side effects) belongs in the action
function registered via `@registry.action`, not in the activity shell.

---

## Section 5: Running Example — Order Processing

Four actions registered via decorator, each delegating to a domain service stub:

```python
# workflows/actions/order_actions.py
# Import this module at worker startup to register all order actions.

from workflows.registry.actions import registry


class OrderService:
    """Stub: replace with real implementation."""

    @staticmethod
    async def validate(state: dict) -> dict:
        return {**state, "validated": True}

    @staticmethod
    async def fulfill(state: dict) -> dict:
        return {**state, "fulfilled": True}


class PaymentService:
    """Stub: replace with real implementation."""

    @staticmethod
    async def charge(state: dict) -> dict:
        return {**state, "paid": True}


class NotificationService:
    """Stub: replace with real implementation."""

    @staticmethod
    async def send_confirmation(state: dict) -> dict:
        return {**state, "confirmed": True}


@registry.action("validate_order", idempotent=True)
async def validate_order(state: dict) -> dict:
    """Validate order fields. Idempotent — retry-safe."""
    return await OrderService.validate(state)


@registry.action("process_payment")
async def process_payment(state: dict) -> dict:
    """Charge the payment method. Not idempotent."""
    return await PaymentService.charge(state)


@registry.action("fulfill_order")
async def fulfill_order(state: dict) -> dict:
    """Fulfil the order. Not idempotent."""
    return await OrderService.fulfill(state)


@registry.action("send_confirmation", idempotent=True)
async def send_confirmation(state: dict) -> dict:
    """Send order confirmation email. Idempotent — safe to send again."""
    return await NotificationService.send_confirmation(state)
```

Registering, resolving, and calling an action:

```python
# At startup: import the decorated module to trigger registration
import workflows.actions.order_actions  # noqa: F401

from workflows.registry.actions import registry

# Verify all four actions are registered
assert registry.registered_names() == [
    "fulfill_order",
    "process_payment",
    "send_confirmation",
    "validate_order",
]

# Resolve an action and call it with order state
fn = registry.get("validate_order")
result = await fn({"order_id": "12345"})
assert result["validated"] is True

# Check idempotency via contract
contract = registry.get_contract("validate_order")
assert contract.idempotent is True

contract = registry.get_contract("process_payment")
assert contract.idempotent is False
```

---

## Section 6: Dual Registration Requirement

The ActionRegistry registration is a domain-layer concern. Worker activity registration is a
Temporal-layer concern. **A function in the ActionRegistry is NOT automatically registered
with the Worker** — both registrations are required for execution.

```
ActionRegistry.register(name, fn)   ← Domain layer: resolve name → callable
Worker(activities=[fn, ...])        ← Temporal layer: register activity with the engine
```

Both registrations must reference the same underlying function:

```python
# workflows/adapters/activities.py (Temporal adapter layer)
from temporalio import activity
from workflows.registry.actions import registry


@activity.defn(name="validate_order")     # <-- Temporal registration
async def validate_order_activity(state: dict) -> dict:
    fn = registry.get("validate_order")    # <-- ActionRegistry resolution
    return await fn(state)


# workers/worker.py
from temporalio.worker import Worker
from workflows.adapters.activities import validate_order_activity  # Temporal registration

worker = Worker(
    client,
    task_queue="order-processing",
    activities=[validate_order_activity],  # <-- required: Temporal worker registration
)
```

The thin-shell activity bridges both registrations:
- The `@activity.defn` name must match the `@registry.action` name exactly.
- The activity function calls `registry.get(name)` at invocation time — registration happens
  at import time, resolution happens at execution time.

---

## Section 7: Verification Checkpoint

Save as `tests/test_registry_checkpoint.py` and run with:

```
python -m pytest tests/test_registry_checkpoint.py -v
```

All five tests must pass before proceeding to the adapter.

```python
# tests/test_registry_checkpoint.py
# Phase 2 — Plan 1 verification: ActionRegistry + ActionContract + decorator pattern

import pytest

from workflows.registry.actions import ActionContract, ActionRegistry


def test_registry_registers_and_resolves_by_name():
    """ActionRegistry registers a callable and resolves it by name."""
    reg = ActionRegistry()

    async def my_action(state: dict) -> dict:
        return {**state, "done": True}

    reg.register("my_action", my_action)
    resolved = reg.get("my_action")
    assert resolved is my_action


def test_decorator_registers_at_decoration_time():
    """Decorator pattern registers the function when the decorator is applied."""
    reg = ActionRegistry()

    @reg.action("decorated_action", idempotent=True)
    async def decorated_action(state: dict) -> dict:
        return {**state, "decorated": True}

    # Must be resolvable immediately after decoration
    resolved = reg.get("decorated_action")
    assert resolved is decorated_action


def test_unregistered_action_raises_key_error():
    """Resolving an unregistered action raises KeyError with a helpful message."""
    reg = ActionRegistry()

    with pytest.raises(KeyError, match="not registered"):
        reg.get("nonexistent_action")


def test_action_contract_stores_idempotency_flag():
    """ActionContract stores the idempotency flag declared at registration."""
    reg = ActionRegistry()

    @reg.action("idempotent_action", idempotent=True)
    async def idempotent_action(state: dict) -> dict:
        return state

    @reg.action("non_idempotent_action", idempotent=False)
    async def non_idempotent_action(state: dict) -> dict:
        return state

    assert reg.get_contract("idempotent_action").idempotent is True
    assert reg.get_contract("non_idempotent_action").idempotent is False


def test_registered_names_returns_sorted_list():
    """registered_names() returns a sorted list of all registered action names."""
    reg = ActionRegistry()

    reg.register("validate_order", lambda s: s)
    reg.register("process_payment", lambda s: s)
    reg.register("fulfill_order", lambda s: s)
    reg.register("send_confirmation", lambda s: s)

    names = reg.registered_names()
    assert names == [
        "fulfill_order",
        "process_payment",
        "send_confirmation",
        "validate_order",
    ], f"Expected sorted names, got: {names}"
```
