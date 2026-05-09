# Migration Playbook

Use this when replacing an existing direct PydanticAI run or older shared LLM wrapper call.

## Hardcoded Prompt to Langfuse

1. Identify the hardcoded `SYSTEM_PROMPT` or `system_prompt=` string in the agent definition.
2. Save the prompt as a `.md` file in the domain's `prompts/` directory (e.g., `prompts/agents/classifier.md`).
3. Run `python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-up --dry-run` to verify the derived Langfuse name.
4. Run `python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-up` to push to Langfuse.
5. Replace the hardcoded string with `fetch_prompt(name, label="latest", fallback=FALLBACK_PROMPT)` using the derived name from step 3.
6. Call `.prompt_object.compile(**vars)` if the prompt uses template variables.
7. Pass the `prompt_ref` into `LLMRunContext` so traces link to the prompt version.
8. Keep the `.md` file as `fallback=` for graceful degradation.

Before:

```python
SYSTEM_PROMPT = "You are a document investigation agent..."

agent = Agent(model, system_prompt=SYSTEM_PROMPT)
```

After:

```python
from pathlib import Path
from ezra_llm import fetch_prompt

_PROMPT_PATH = Path(__file__).parent / "prompts" / "agents" / "document_investigation.md"
FALLBACK_PROMPT = _PROMPT_PATH.read_text().strip()

prompt_ref = fetch_prompt(
    "deals/triage/agents/document_investigation",
    label="latest",
    fallback=FALLBACK_PROMPT,
)
system_text = (
    prompt_ref.prompt_object.compile()
    if prompt_ref.prompt_object is not None
    else FALLBACK_PROMPT
)

agent = Agent(model, system_prompt=system_text)
```

## Agent Run

1. Keep the existing `Agent(...)` shape, tools, deps, and output models where they are.
2. Confirm the live runtime inputs exist:
   provider/model choice, provider credentials if needed, and Langfuse env vars if live tracing is expected.
3. If those inputs are missing, ask the user for them before claiming the integration is runnable.
4. Add `instrument=build_pydantic_ai_instrumentation()` to the agent definition.
5. Replace the direct `agent.run(...)` call with `run_agent(...)`.
6. Add `LLMRunContext` with all required fields:
   - `session_id` — `"{app}-{entity_id}"`
   - `user_id` — from the entity's owner for cost attribution
   - `workflow_name` — the app name
   - `step_name` — the specific action
   - `tags` — `["{app-name}"]`
   - `version` — agent version
   - `release` — `os.environ.get("GIT_SHA", "local")`
   - `prompt_ref` — from `fetch_prompt()`
7. Add only the metadata fields that will help someone inspect traces later.
8. Read `observed.result.output` and only propagate `observed.trace` if the caller needs it.

## Existing Manual Run Flow

1. Keep the existing agent invocation structure.
2. Add `observe_run(...)` around the business step that should become the root trace scope.
3. Include all required `LLMRunContext` fields (tags, user_id, session_id, workflow_name, step_name).
4. Leave the business code in place and only add the minimal shared observability wiring.

## Dataset Capture

1. Use dataset helpers only when the user explicitly wants Langfuse eval capture.
2. Save corrected or curated examples, not every raw run by default.
3. Attach `source_trace_id` and `source_observation_id` from the traced run.

## Tiny Dataset Eval

1. Use `run_dataset(...)` only when the user explicitly asks to run evals.
2. Keep `run_case(item)` small and focused on producing the real agent output.
3. Keep `score_case(item, result)` in product code so scoring logic stays near the feature.
4. Do not add experiment frameworks, evaluator registries, or a Pydantic Evals bridge.
