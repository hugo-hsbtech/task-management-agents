---
name: ezra-llm-integration
description: Use when the task is “instrument this PydanticAI agent”, “add Langfuse tracing”, “add Langfuse evals”, “make this agent observable”, “fetch prompts from Langfuse”, “manage system prompts”, “version prompts”, or “wire Langfuse prompt into agent”. Covers observability, prompt management, and eval capture via `ezra_llm`.
---

# Ezra LLM Integration

Use this skill when an existing product agent or model workflow needs
PydanticAI + Langfuse observability or Langfuse-managed prompts.

The goal is not to invent a platform. The goal is to make one real agent run
observable and its prompts version-controlled with the smallest possible shared layer.

## Mental Model: Prompts vs Agents

- **Prompt** = versioned text in Langfuse (system instructions, templates). Langfuse is the source of truth for all prompts in Ezra. Prompts are also kept as markdown files in code so the agent degrades gracefully when Langfuse is unavailable and so prompts are reviewable in PRs.
- **Agent** = code-defined structure (model, tools, deps, output type) that consumes a prompt. Lives in code, deployed with the service.

Prompts change often (tone, instructions, few-shot examples). Agent structure changes rarely (new tools, new deps). Keep them separate.

## Outcomes

By the end of the task:

- the agent is instrumented with `build_pydantic_ai_instrumentation()`
- the call site carries a small `LLMRunContext`
- Langfuse sees useful trace metadata
- system prompts are fetched from Langfuse via `fetch_prompt()`, not hardcoded (unless explicitly prototyping)
- `prompt_ref` is passed into `LLMRunContext` so traces link to the prompt version
- eval helpers are only added when the task explicitly asks for them
- business-domain models and workflow logic stay outside `ezra_llm`

## First Reads

Read these files before changing code:

- `backend/packages/domains/llm/README.md`
- `backend/packages/domains/llm/src/ezra_llm/client.py`
- `backend/packages/domains/llm/src/ezra_llm/langfuse.py`
- `backend/packages/domains/llm/src/ezra_llm/schemas.py`
- `backend/packages/domains/llm/src/ezra_llm/prompts.py`

Then read the lean references in this skill:

- integration shapes: [patterns.md](./patterns.md)
- before/after migration snippets: [migration-playbook.md](./migration-playbook.md)
- reduction guardrails: [checklist.md](./checklist.md)

## Prompt Management Conventions

Langfuse is the single source of truth for all prompts in Ezra. Every prompt must also exist in code.

### Prompt Naming — Auto-Derived from Directory Structure

Prompt names are derived automatically by `scripts/sync-langfuse-prompts.py` from the file path. The convention:

1. Find the `ezra_*` ancestor directory above `prompts/`
2. Strip the `ezra_` prefix
3. Take the path to the `.md` file, dropping the `prompts/` segment

Examples:
- `ezra_deals/triage/prompts/agents/classifier.md` → `deals/triage/agents/classifier`
- `ezra_deals/triage/prompts/gate_assessment.md` → `deals/triage/gate_assessment`
- `ezra_crm_sync/prompts/revision.md` → `crm_sync/revision`

Do not manually choose prompt names. Place the `.md` file in the right directory and the name follows.

### Prompt Storage in Code

Keep prompts as `.md` files in a `prompts/` directory within the domain package. Subdirectories are preserved in the Langfuse name:

```
backend/packages/domains/{domain}/src/ezra_{domain}/
  {module}/
    prompts/
      agents/
        classifier.md          → {domain}/{module}/agents/classifier
        deal_overview.md       → {domain}/{module}/agents/deal_overview
      matching/
        matcher.md             → {domain}/{module}/matching/matcher
      gate_assessment.md       → {domain}/{module}/gate_assessment
```

These serve as:
1. Fallbacks when Langfuse is unavailable
2. PR-reviewable prompt changes
3. The initial content to push to Langfuse for new prompts
4. Auto-discovery source for the sync script

### Syncing Prompts with Langfuse

Use `scripts/sync-langfuse-prompts.py` for all prompt sync operations. No manifest or config files needed.

```bash
# Preview discovered prompts and their Langfuse names
python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-up --dry-run

# Push local .md files to Langfuse
python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-up

# Pull Langfuse changes back to local .md files
python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-down

# Preview what sync-down would change
python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-down --dry-run
```

After the initial push, iterate on prompts in the Langfuse UI and run `--sync-down` to pull changes back to code.

## Tracing Conventions

All traces must carry enough context for filtering, cost attribution, and debugging in Langfuse.

### Required Trace Fields

| Field | Purpose | Format | Example |
|---|---|---|---|
| `tags` | Filter traces by app | `[“{app-name}”]` | `[“deal-triage”]` |
| `user_id` | Track LLM cost per account | From the entity's `user_id` field | `”user_abc123”` |
| `session_id` | Group traces by session/entity | `”{app}-{entity_id}”` | `”deal-triage-deal_456”` |
| `workflow_name` | Identify the app/workflow | `”{app-name}”` | `”deal-triage”` |
| `step_name` | Identify the specific action | Short verb/noun | `”classify”`, `”overview”`, `”gate1”` |
| `version` | Track agent version | Semver string | `”1.0”` |
| `release` | Track deployed code version | Git SHA or `”local”` | `os.environ.get(“GIT_SHA”, “local”)` |

### Trace Name

The trace name is automatically built as `{workflow_name}.{step_name}` (e.g., `deal-triage.classify`). This is the process name involving the LLM call, not the agent name.

### Tagging

All traces **and** prompts must be tagged with the platform app name that uses them (e.g., `deal-triage`). This enables filtering in Langfuse by app.

### Service Initialization

Each deployable service must call `configure_langfuse_observability(service_name=...)` during startup (lifespan):

```python
configure_langfuse_observability(service_name=”ezra-api”)
configure_langfuse_observability(service_name=”ezra-triage-worker”)
```

### Threading Context Through Async Workflows

For multi-step workflows (e.g., Temporal activities), use `ContextVar` to thread trace context:

```python
from contextvars import ContextVar

_current_step = ContextVar(“_current_step”, default=”unknown”)
_current_session = ContextVar(“_current_session”, default=None)
_current_user = ContextVar(“_current_user”, default=None)

def set_trace_session(session_id: str) -> None:
    _current_session.set(session_id)

def set_trace_user(user_id: str) -> None:
    _current_user.set(user_id)
```

Set these at the start of each workflow action, then read them when building `LLMRunContext`.

## Workflow

1. Find the existing `Agent(...)` definition and `agent.run(...)` call site.
2. If the agent has a hardcoded system prompt, extract it to a `.md` file, push to Langfuse, and fetch via `fetch_prompt()`.
3. Keep tools, deps, and business-domain models where they already live.
4. Check whether the task has the runtime inputs needed for a live integration.
5. If required information is missing, ask the user for it directly and concisely before wiring the integration.
6. Add `instrument=build_pydantic_ai_instrumentation()` at agent construction.
7. Wrap the real call site with `run_agent()`, `run_agent_sync()`, or `observe_run()`.
8. Attach all required trace fields: `tags`, `user_id`, `session_id`, `workflow_name`, `step_name`, `version`, `release`, and `prompt_ref`.
9. If the user explicitly wants Langfuse eval capture, add dataset helpers or the tiny dataset runner.
   Do not add experiment runners, evaluator registries, or scoring DSLs.

## Required Runtime Inputs

Before implementing or claiming the integration is usable, confirm the task has:

- a real PydanticAI model/provider choice for the target call site, if the code will make live model requests
- provider credentials required by that chosen model, if live requests are expected
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST`

If any of those are missing and the user wants a working live integration, ask for the missing values.

If the task is only to wire the code path or update the abstraction layer, it is fine to proceed without secrets, but say clearly that live Langfuse traces, dataset capture, and eval runs will not work until the env vars are configured.

## Implementation Rules

- Prefer instrumenting an existing agent definition over inventing a shared agent factory.
- Prefer `run_agent()` when you are already touching the call site.
- Prefer `observe_run()` when the feature already owns its own agent invocation flow.
- Keep business request/response types in the business domain, not in `ezra_llm`.
- Keep provider and model selection in product code, not in `ezra_llm`.
- If secrets or runtime identifiers are missing, ask the user for them before promising a live integration.
- Use `fetch_prompt()` to get prompts from Langfuse; pass result as `prompt_ref` in `LLMRunContext`.
- Call `.prompt_object.compile(**vars)` when the Langfuse prompt uses template variables.
- Provide `fallback=` during initial rollout so the agent degrades gracefully if Langfuse is unavailable.
- Prompts must always exist as `.md` files in code AND in Langfuse. Langfuse is the source of truth; code files are fallbacks and PR-reviewable snapshots.
- If eval capture is needed, save curated examples with trace provenance.
- If dataset evaluation is needed, keep scoring logic in the caller-supplied function.

## Anti-Patterns

Do not:

- add demo apps
- add tests unless the user asks
- add provider registries, workflow frameworks, or generalized agent infrastructure
- move business-domain schemas into `ezra_llm`
- add Pydantic Evals wrappers by default
- add Langfuse experiment orchestration helpers
- hand-roll model-call tracing in product code when `ezra_llm` can do the small shared part
- hardcode system prompts in production agents — fetch from Langfuse instead
- create traces without `tags`, `user_id`, or `session_id` — these are required for filtering and cost attribution
- use generic trace names — always use `{app}.{action}` format (e.g., `deal-triage.classify`)
- manually choose prompt names — let the sync script derive them from the file path
- create `_langfuse.json` or manifest files — the directory structure is the convention
- forget to run `--sync-up` after adding a new `.md` prompt file

## If You Think The Shared Layer Needs To Grow

Pause and prove it.

Only add shared code when a real call site benefits immediately and the new code
is still obviously about observability, prompt fetching, or tiny eval capture, not platform
design.
