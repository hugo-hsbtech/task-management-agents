# Ezra Platform Conventions

Project-specific conventions for Temporal workflows in the Ezra monorepo. These extend the
stack-agnostic patterns in the other reference files with naming, file placement, and
dependency wiring rules specific to this codebase.

---

## Section 1: File Placement in the Monorepo

Each workflow spans three locations. The `workflows` domain is pure infrastructure — it owns
the DSL, registry, adapter base, tracing, and port. Domain-specific code lives in the
domain package that owns the business logic.

| Concern | Package | Path | Example |
|---------|---------|------|---------|
| Workflow definition | Domain | `{domain}/definitions/{name}_workflow.py` | `ezra_deals/triage/definitions/triage_workflow.py` |
| Business actions | Domain | `{domain}/actions/{name}.py` | `ezra_deals/triage/actions/triage.py` |
| Activity adapter shells | Domain | `{domain}/activities.py` | `ezra_deals/triage/activities.py` |
| Worker assembly | Worker app | `ezra_worker/worker.py` | Single unified worker |
| DSL models | Workflows domain | `ezra_workflows/dsl/models.py` | Shared across all domains |
| ActionRegistry | Workflows domain | `ezra_workflows/registry/actions.py` | Shared singleton |
| TemporalAdapter | Workflows domain | `ezra_workflows/adapters/temporal_adapter.py` | Shared adapter |
| Tracing | Workflows domain | `ezra_workflows/adapters/tracing.py` | Shared interceptor |
| Settings | Workflows domain | `ezra_workflows/settings.py` | `TemporalSettings` |

Activity shells live in the domain package, not in the workflows domain. This keeps the
workflows domain free of domain-specific knowledge and prevents circular dependencies.

---

## Section 2: Naming Conventions

### Action Names

Pattern: `{domain_prefix}_{verb}` or `{domain_prefix}_{noun}`

```
deal_triage_classify
deal_triage_download_files
knowledge_run_ingestion_pipeline
knowledge_download_document
sales_interaction_extract
sales_interaction_send_to_hubspot
```

### Activity Function Names

Pattern: `{action_name}_activity` suffix

```
deal_triage_classify_activity
knowledge_download_document_activity
sales_interaction_extract_activity
```

### Task Queues

Kebab-case domain name:

```
deal-triage
knowledge-ingestion
sales-interaction
```

### Workflow Definition IDs

Pattern: `{domain}-{name}-v{version}`

```
deal-triage-v2
knowledge-ingest-document
sales-interaction-v1
```

### Runtime Workflow IDs

Pattern: `{domain}-{entity_id}`

```
deal-triage-{deal.id}
knowledge-ingest-{run_id}
sales-interaction-{interaction.id}
```

### Workflow Definition Variables

Pattern: `{domain}_workflow`

```
deal_triage_workflow
ingestion_workflow
sales_interaction_workflow
```

### Task Queue Constants

Co-located with the workflow definition. Both the API (starter) and worker need the same
queue name — co-locating it with the definition prevents drift.

```python
# In {domain}/definitions/{name}_workflow.py
SALES_INTERACTION_TASK_QUEUE = "sales-interaction"
```

---

## Section 3: Retry Policy Presets

Each workflow definition file declares reusable retry presets rather than inline retry
policies. Three preset categories cover most use cases:

```python
RETRY_LLM = RetryPolicy(
    max_attempts=3,
    initial_interval_seconds=5,
    backoff_coefficient=2.0,
    max_interval_seconds=60,
)

RETRY_IO = RetryPolicy(
    max_attempts=3,
    initial_interval_seconds=2,
    backoff_coefficient=2.0,
    max_interval_seconds=30,
)

RETRY_POLL = RetryPolicy(
    max_attempts=60,
    initial_interval_seconds=30,
    backoff_coefficient=1.0,
    max_interval_seconds=40,
)
```

| Preset | Use Case | Examples |
|--------|----------|---------|
| `RETRY_LLM` | LLM API calls that may hit rate limits or transient errors | classify, summarize, extract |
| `RETRY_IO` | File downloads, uploads, notifications | S3 operations, email, rendering |
| `RETRY_POLL` | Waiting for external state changes | claim worker slot, wait for approval |

---

## Section 4: Activity List Export

Each domain's `activities.py` exports an `ACTIVITIES` list constant containing all activity
shell functions for that domain. The worker app imports these lists to assemble workers.

```python
# ezra_deals/triage/activities.py
ACTIVITIES = [
    deal_triage_download_files_activity,
    deal_triage_classify_activity,
    ...
]

# ezra_worker/worker.py
from ezra_deals.triage.activities import ACTIVITIES as TRIAGE_ACTIVITIES
from ezra_knowledge_base.activities import ACTIVITIES as KNOWLEDGE_ACTIVITIES
```

---

## Section 5: The configure() Pattern

Actions need infrastructure dependencies (DB sessions, S3 clients, LLM clients). Each
domain's actions module exposes a `configure()` function called once at worker startup to
inject these dependencies via module-level globals.

```python
# ezra_deals/triage/actions/triage.py
_s3_client: S3Client | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

def configure(llm_client, s3_client, session_factory, config) -> None:
    global _s3_client, _session_factory
    _s3_client = s3_client
    _session_factory = session_factory

@registry.action("deal_triage_download_files")
async def deal_triage_download_files(state: dict) -> dict:
    async with _session_factory() as session:
        ...
```

The worker app calls `configure()` for each domain before creating workers:

```python
# ezra_worker/worker.py main()
configure_triage(llm_client, s3_client, session_factory, triage_config)
configure_knowledge(s3_client=s3_client, session_factory=session_factory, ...)
configure_sales_interactions(session_factory=session_factory, settings=settings, ...)
```

---

## Section 6: Import-Time Registration

Workers must import action modules with `noqa: F401` to trigger `@registry.action`
registration before workers start polling. Without this, `registry.get()` raises KeyError
at activity execution time.

```python
# ezra_worker/worker.py
import ezra_knowledge_base.actions.ingestion  # noqa: F401 — register knowledge actions
import ezra_sales_interactions.actions.extraction  # noqa: F401 — register sales interaction actions
```

Triage actions register via `configure()` which imports the module as a side effect.

---

## Section 7: Worker Startup Sequence

The unified worker app follows this startup order:

1. Configure observability (Langfuse)
2. Create DB engine + session factory
3. Create infrastructure clients (S3, HubSpot, webhook dispatcher)
4. Import action modules to trigger registration (noqa: F401)
5. Call each domain's `configure()` to inject dependencies
6. Connect Temporal client with tracing interceptor
7. Create Worker instances (one per task queue) with domain activity lists
8. Run reconciliation (catch stuck workflows from prior crashes)
9. Start worker tasks with graceful shutdown + fatal error propagation

---

## Section 8: FastAPI Integration

### Temporal Client Dependency

Two-tier dependency pattern for API routes:

```python
async def resolve_temporal_client(request: Request) -> TemporalClient | None:
    # Try app state first, reconnect if needed, return None on failure

async def get_temporal_client(request: Request) -> TemporalClient:
    # Calls resolve_temporal_client, raises HTTP 503 if None
```

Use `resolve_temporal_client` when the workflow is optional (graceful degradation).
Use `get_temporal_client` as a FastAPI `Depends()` when the route requires Temporal.

### Lifespan Initialization

Connect the Temporal client in the FastAPI lifespan with a timeout. Store as
`app.state.temporal_client` (may be `None` if Temporal is unavailable at startup).

### Starting Workflows from Routes

```python
adapter = TemporalAdapter(temporal_client, task_queue="deal-triage")
await adapter.start_workflow(
    deal_triage_workflow,
    input={"deal_id": str(deal.id), "user_email": user_email},
    workflow_id=f"deal-triage-{deal.id}",
)
```

---

## Section 9: Adding a New Workflow Checklist

When adding workflow N+1 to an existing system:

1. **Create workflow definition** in the domain package:
   `{domain}/definitions/{name}_workflow.py`
   - Define task queue constant
   - Define retry presets (or reuse existing)
   - Define `WorkflowDefinition` with steps and transitions

2. **Create business actions** in the domain package:
   `{domain}/actions/{name}.py`
   - Add `configure()` function for dependency injection
   - Register actions with `@registry.action("domain_action_name")`

3. **Create activity shells** in the domain package:
   `{domain}/activities.py`
   - One thin-shell function per action
   - Export `ACTIVITIES` list constant

4. **Add `temporalio` dependency** to the domain's `pyproject.toml`

5. **Wire the worker app** (`ezra_worker/worker.py`):
   - Import action module with `noqa: F401` for registration
   - Import `ACTIVITIES` list from the domain
   - Call `configure()` in `main()`
   - Add a new `Worker(...)` with the domain's task queue and activities

6. **Add API route** for starting the workflow:
   - Use `TemporalAdapter(client, task_queue=DOMAIN_TASK_QUEUE)`
   - Call `adapter.start_workflow(...)` with the definition and input

7. **Run import boundary test** to verify no Temporal imports leaked into domain business logic
