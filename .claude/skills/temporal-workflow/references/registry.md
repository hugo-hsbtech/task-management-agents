# Action Registry Reference

The Action Registry layer decouples DSL action name strings from callable implementations.
`StepDefinition.action` stores a name; `ActionRegistry.get()` resolves that name to a callable
at execution time. This indirection allows workflows to be defined without knowing which
functions will execute their steps.

The registry itself is infrastructure-free. Only the thin-shell activities (Section 4) touch
the Temporal adapter layer.

See stacks/{stack}/ for the concrete registry implementation in your language.

---

## Section 1: ActionContract Model (AREG-02)

`ActionContract` declares metadata about a registered action. Store one contract per registered
callable to enable runtime introspection of action properties without invoking the action.

### ActionContract Schema

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | — | Registration key used in `StepDefinition.action` |
| `idempotent` | boolean | false | True when repeated calls with the same input always produce the same result |
| `input_schema` | dict | {} | JSON Schema describing expected input; empty means no validation applied |
| `output_schema` | dict | {} | JSON Schema describing returned output; empty means no validation applied |

---

## Section 2: ActionRegistry Class (AREG-01)

`ActionRegistry` maintains two parallel lookup tables: one mapping action names to callables,
one mapping action names to their `ActionContract` metadata.

### Methods

**`register(name, fn, idempotent=false) -> void`**

Imperatively register a callable under a name. Use when the decorator pattern is not possible
(lambda functions, dynamically generated callables, functions from third-party modules).

**`action(name, idempotent=false) -> decorator`**

Decorator factory that registers the decorated function under name at decoration time. The
decorator runs at module import time. Returns the decorated function unchanged.

**`get(name) -> callable`**

Resolve an action name to its registered callable. Raises a key error if the name is not
registered — the error message includes all currently registered names to help diagnose
import-ordering issues.

**`get_contract(name) -> ActionContract`**

Return the `ActionContract` for a registered action. Raises a key error if the name is not
registered.

**`registered_names() -> list[string]`**

Return a sorted list of all registered action names.

### Module-Level Singleton

Create one `ActionRegistry` instance at module level and import that instance everywhere. This
ensures all registrations share a single lookup table.

---

## Section 3: Decorator Registration Pattern (D-11, D-12)

The `@registry.action` decorator registers the function at module import time. The decorator
factory pattern keeps the registration call co-located with the function definition.

### Registration (conceptual)

```
registry = ActionRegistry()

@registry.action("validate_order", idempotent=true)
async function validate_order(state: dict) -> dict:
  // delegates to OrderService — no business logic here
  return await OrderService.validate(state)

@registry.action("process_payment")
async function process_payment(state: dict) -> dict:
  // not idempotent — each call charges once
  return await PaymentService.charge(state)
```

### Import Ordering Requirement

The decorator runs at import time, not at definition time of the workflow. The module containing
decorated functions must be imported before `registry.get()` is called.

**Pitfall — action not found at runtime:**

```
// WRONG: registry.get() called before the decorated module is imported
result = registry.get("validate_order")  // error — decorated module not yet imported

// CORRECT: import the decorated module first to trigger registration side effects
import workflows.actions.order_actions   // triggers @registry.action decorators
result = registry.get("validate_order")  // resolves correctly
```

Worker startup code and application initialization must import all modules containing
decorated action functions before any registry resolution occurs.

### Idempotency Declaration (D-12)

Idempotency is declared at registration time. This metadata is stored in `ActionContract` and
accessible via `registry.get_contract(name).idempotent`.

| Action | Idempotent | Reason |
|--------|-----------|--------|
| `validate_order` | true | Pure validation; repeating does not accumulate side effects |
| `process_payment` | false | Each call charges the payment method once |
| `fulfill_order` | false | Each call dispatches a physical shipment |
| `send_confirmation` | true | Email deduplication means re-sending is safe |

---

## Section 4: Thin-Shell Activity Pattern (AREG-03)

**This code lives in the adapter layer — the only place that combines Temporal activity
registration with registry resolution.**

Activities are thin shells: resolve the callable from the registry, delegate to the registered
action function, and return the result. No business logic belongs in the activity shell.

### Pattern (conceptual)

```
// Domain package: {domain}/activities (co-located with the business actions)

@temporal_activity_decorator(name="validate_order")
async function validate_order_activity(state: dict) -> dict:
  fn = registry.get("validate_order")
  return await fn(state)
```

The Temporal activity name must match the registry action name exactly. The activity shell
makes exactly one registry resolution call — no branching, no additional service calls.

In the Ezra monorepo, activity shells live in each domain package (e.g.,
`ezra_deals/triage/activities.py`), not in a centralized adapter directory. Each domain
exports an `ACTIVITIES` list that the worker app imports for assembly. See
[ezra-conventions.md](ezra-conventions.md) for the full file placement rules.

### Why Two Registrations Are Required

| Registration | Layer | Purpose |
|-------------|-------|---------|
| `ActionRegistry.register(name, fn)` | Domain layer | Resolve name string -> callable at DSL execution time |
| `Worker(activities=[fn, ...])` | Temporal adapter layer | Register the activity shell with the Temporal worker |

The thin-shell activity is the bridge: it carries both the Temporal activity decorator (for
the worker registration) and the registry resolution call (for the domain layer lookup).

See adapter.md Section 4 for the full dual registration wiring.

---

## Section 5: Running Example — Order Processing

Four actions registered via decorator, each delegating to a domain service stub.

### Registration (conceptual)

```
// workflows/actions/order_actions (import at worker startup to trigger registration)

@registry.action("validate_order", idempotent=true)
async function validate_order(state) -> dict:
  return await OrderService.validate(state)   // {**state, validated: true}

@registry.action("process_payment")
async function process_payment(state) -> dict:
  return await PaymentService.charge(state)   // {**state, paid: true}

@registry.action("fulfill_order")
async function fulfill_order(state) -> dict:
  return await OrderService.fulfill(state)    // {**state, fulfilled: true}

@registry.action("send_confirmation", idempotent=true)
async function send_confirmation(state) -> dict:
  return await NotificationService.confirm(state)  // {**state, confirmed: true}
```

### Resolution and Idempotency Check (conceptual)

```
// At startup: import the decorated module to trigger registration
import workflows.actions.order_actions

// Verify all four actions are registered
assert registry.registered_names() == [
  "fulfill_order",
  "process_payment",
  "send_confirmation",
  "validate_order",
]

// Resolve an action and call it
fn = registry.get("validate_order")
result = await fn({"order_id": "12345"})
assert result["validated"] == true

// Check idempotency via contract
assert registry.get_contract("validate_order").idempotent == true
assert registry.get_contract("process_payment").idempotent == false
```

---

## Section 6: Dual Registration Requirement

Summary of the two independent registration steps and their relationship:

```
Step 1 (domain layer, at import time):
  @registry.action("validate_order", idempotent=true)
  function validate_order(state) -> dict: ...

Step 2 (adapter layer, at worker startup):
  @temporal_activity(name="validate_order")
  function validate_order_activity(state) -> dict:
    fn = registry.get("validate_order")
    return await fn(state)

  Worker(activities=[validate_order_activity, ...])
```

Both steps must complete before a workflow that references `"validate_order"` can execute.
Missing Step 1: registry resolution fails at runtime. Missing Step 2: Temporal cannot find
the activity on any worker.

See adapter.md Section 5 for the full worker setup including activity list assembly.

---

## Section 7: Verification Checkpoint

After building the registry layer, verify it before proceeding to the adapter. Run the registry
checkpoint tests. All five tests must pass:

1. **Register and resolve by name** — `registry.register("my_action", fn)` followed by `registry.get("my_action")` returns the same callable.
2. **Decorator registers at decoration time** — a function decorated with `@registry.action("name")` is immediately resolvable via `registry.get("name")`.
3. **Unregistered action raises key error** — `registry.get("nonexistent")` raises a key error with a message containing "not registered".
4. **ActionContract stores idempotency flag** — a function registered with `idempotent=true` returns `true` from `registry.get_contract(name).idempotent`; one registered with `idempotent=false` returns `false`.
5. **registered_names returns sorted list** — after registering the four order processing actions, `registry.registered_names()` returns them in sorted alphabetical order.

See stacks/{stack}/ for the concrete test file.
