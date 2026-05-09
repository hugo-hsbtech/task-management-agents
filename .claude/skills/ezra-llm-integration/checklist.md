# Checklist

Before finishing, verify:

## Observability

- the agent definition now uses `build_pydantic_ai_instrumentation()`
- the call site now goes through `run_agent()`, `run_agent_sync()`, or `observe_run()`
- `LLMRunContext` includes all required fields:
  - `session_id` — format: `"{app}-{entity_id}"`
  - `user_id` — from the entity's owner/account for cost attribution
  - `workflow_name` — the app name (e.g., `"deal-triage"`)
  - `step_name` — the specific action (e.g., `"classify"`, `"overview"`)
  - `tags` — includes the app name (e.g., `["deal-triage"]`)
  - `version` — agent version string (e.g., `"1.0"`)
  - `release` — `os.environ.get("GIT_SHA", "local")`
- the trace name resolves to `{workflow_name}.{step_name}` (e.g., `deal-triage.classify`)
- metadata is useful for trace inspection but not overloaded
- missing provider credentials or Langfuse env vars were either supplied by the user or explicitly called out as remaining setup
- `configure_langfuse_observability(service_name=...)` is called in the service lifespan

## Prompt Management

- system prompt is fetched from Langfuse via `fetch_prompt()`, not hardcoded (unless explicitly prototyping)
- prompt also exists as a `.md` file in the domain's `prompts/` directory (fallback + PR reviewability)
- prompt name is auto-derived from file path (e.g., `deals/triage/agents/classifier`) — verify with `--sync-up --dry-run`
- prompt is tagged in Langfuse with the app name (e.g., `deal-triage`)
- `prompt_ref` is passed into `LLMRunContext` for trace linkage
- if using template variables, `.compile(**vars)` is called with the correct keys
- `fallback=` is provided for graceful degradation when Langfuse is unavailable

## Boundaries

- business schemas, deps, and tools stayed in the business domain
- no tests, demo apps, registries, workflow frameworks, or generalized agent infrastructure were added by default
- if dataset capture was requested, saved items include `source_trace_id` and `source_observation_id`
- if dataset evaluation was requested, scoring stayed in caller-supplied functions
