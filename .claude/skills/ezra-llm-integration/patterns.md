# Patterns

Use the smallest call-site change that gets observability and prompt management in place.

## Prompt Management

Langfuse is the source of truth. Prompts also live in code as `.md` fallbacks.

```python
from pathlib import Path

from pydantic_ai import Agent

from ezra_llm import (
    LLMRunContext,
    build_pydantic_ai_instrumentation,
    configure_langfuse_observability,
    fetch_prompt,
    run_agent,
)

configure_langfuse_observability(service_name="ezra-triage-worker")

_PROMPT_DIR = Path(__file__).parent / "prompts" / "agents"
FALLBACK_PROMPT = (_PROMPT_DIR / "classifier.md").read_text().strip()

prompt_ref = fetch_prompt("deals/triage/agents/classifier", label="latest", fallback=FALLBACK_PROMPT)
system_text = (
    prompt_ref.prompt_object.compile()
    if prompt_ref.prompt_object is not None
    else FALLBACK_PROMPT
)

agent = Agent(
    "anthropic:claude-sonnet-4-20250514",
    system_prompt=system_text,
    instrument=build_pydantic_ai_instrumentation(),
)

observed = await run_agent(
    agent,
    document_text,
    context=LLMRunContext(
        session_id=f"deal-triage-{deal_id}",
        user_id=deal.user_id,
        workflow_name="deal-triage",
        step_name="classify",
        tags=["deal-triage"],
        version="1.0",
        release=os.environ.get("GIT_SHA", "local"),
        prompt_ref=prompt_ref,
        metadata={"deal_id": deal_id},
    ),
)

result = observed.result.output
```

### Fetch with Fallback

Graceful degradation when Langfuse is not configured:

```python
_PROMPT_PATH = Path(__file__).parent / "prompts" / "classifier.md"
FALLBACK_PROMPT = _PROMPT_PATH.read_text().strip() if _PROMPT_PATH.exists() else "Classify this document."

prompt_ref = fetch_prompt("deals/triage/agents/classifier", label="latest", fallback=FALLBACK_PROMPT)
system_text = (
    prompt_ref.prompt_object.compile()
    if prompt_ref.prompt_object is not None
    else FALLBACK_PROMPT
)
```

## Agent Instrumentation

Best when the feature already owns an existing PydanticAI `Agent(...)`.

Before:

```python
from pydantic_ai import Agent

agent = Agent("anthropic:claude-sonnet-4-20250514")

result = await agent.run(document_text)
summary = result.output
```

After:

```python
import os
from pydantic_ai import Agent

from ezra_llm import (
    LLMRunContext,
    build_pydantic_ai_instrumentation,
    configure_langfuse_observability,
    fetch_prompt,
    run_agent,
)

configure_langfuse_observability(service_name="ezra-triage-worker")

_PROMPT_PATH = Path(__file__).parent / "prompts" / "classifier.md"
FALLBACK_PROMPT = _PROMPT_PATH.read_text().strip()

prompt_ref = fetch_prompt("deals/triage/agents/classifier", label="latest", fallback=FALLBACK_PROMPT)
system_text = (
    prompt_ref.prompt_object.compile()
    if prompt_ref.prompt_object is not None
    else FALLBACK_PROMPT
)

agent = Agent(
    "anthropic:claude-sonnet-4-20250514",
    system_prompt=system_text,
    instrument=build_pydantic_ai_instrumentation(),
)

observed = await run_agent(
    agent,
    document_text,
    context=LLMRunContext(
        session_id=f"deal-triage-{deal_id}",
        user_id=deal.user_id,
        workflow_name="deal-triage",
        step_name="classify",
        tags=["deal-triage"],
        version="1.0",
        release=os.environ.get("GIT_SHA", "local"),
        prompt_ref=prompt_ref,
        metadata={"deal_id": deal_id},
    ),
)

summary = observed.result.output
trace_id = observed.trace.trace_id
```

## Existing Custom Run Flow

Use `observe_run()` when the calling code already manages its own run lifecycle.

```python
import os
from ezra_llm import LLMRunContext, observe_run

with observe_run(
    LLMRunContext(
        session_id=f"deal-triage-{deal_id}",
        user_id=deal.user_id,
        workflow_name="deal-triage",
        step_name="classify",
        tags=["deal-triage"],
        version="1.0",
        release=os.environ.get("GIT_SHA", "local"),
        metadata={"deal_id": deal_id},
    )
) as trace:
    result = await agent.run(question, deps=deps)
```

## Multi-Step Workflow with ContextVar

For workflows with many LLM steps (e.g., Temporal activities), thread context via `ContextVar`:

```python
from contextvars import ContextVar

_current_step = ContextVar("_current_step", default="unknown")
_current_workflow = ContextVar("_current_workflow", default="deal-triage")
_current_session = ContextVar("_current_session", default=None)
_current_user = ContextVar("_current_user", default=None)

def set_trace_session(session_id: str) -> None:
    _current_session.set(session_id)

def set_trace_user(user_id: str) -> None:
    _current_user.set(user_id)

def build_context(step_name: str, **extra_metadata) -> LLMRunContext:
    return LLMRunContext(
        workflow_name=_current_workflow.get(),
        step_name=step_name,
        session_id=_current_session.get(),
        user_id=_current_user.get(),
        tags=["deal-triage"],
        version="1.0",
        release=os.environ.get("GIT_SHA", "local"),
        metadata=extra_metadata,
    )
```

Then at the start of each workflow action:

```python
set_trace_session(f"deal-triage-{state['deal_id']}")
if state.get("user_id"):
    set_trace_user(state["user_id"])
```

## Dataset Capture

Use only when the task explicitly asks for Langfuse eval or dataset support.

```python
from ezra_llm import LangfuseDatasetItem, upsert_dataset_items

upsert_dataset_items(
    dataset_name="deals/triage/agents/classifier-v1",
    items=[
        LangfuseDatasetItem(
            item_id=deal.id,
            input={"document_text": document_text},
            expected_output={"classification": corrected_classification},
            metadata={"deal_id": deal.id},
            source_trace_id=observed.trace.trace_id,
            source_observation_id=observed.trace.observation_id,
        )
    ],
)
```

## Tiny Eval Runner

Use only when the task explicitly asks to run Langfuse-backed evals over a
dataset and the caller can own the scoring logic.

```python
from ezra_llm import EvalScore, LLMRunContext, run_agent, run_dataset


async def run_case(item):
    return await run_agent(
        agent,
        item.input["question"],
        context=LLMRunContext(
            session_id=item.id,
            workflow_name="qa_eval",
            step_name="answer",
            tags=["deal-triage"],
            metadata={"dataset_item_id": item.id},
        ),
    )


def score_case(item, result):
    return [
        EvalScore(
            name="correct",
            value=result.output == item.expected_output["answer"],
        )
    ]


summary = await run_dataset(
    dataset_name="qa-golden-set",
    run_name="baseline",
    run_case=run_case,
    score_case=score_case,
)
```

Stop there. Do not add experiment runners or evaluator frameworks in this skill.
