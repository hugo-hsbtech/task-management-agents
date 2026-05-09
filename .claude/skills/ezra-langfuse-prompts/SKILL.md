---
name: ezra-langfuse-prompts
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Use when the task is "create a Langfuse prompt", "list Langfuse prompts", "version this prompt in Langfuse", or "connect a Langfuse-managed prompt to a PydanticAI agent". Focuses on prompt management through the Langfuse Python SDK and minimal integration with `ezra_llm`.
allowed-tools: Bash
---

# Ezra Langfuse Prompts

Use this skill when working with Langfuse prompt management.

Langfuse is the single source of truth for all prompts in Ezra. Prompts must also exist as `.md` files in code for fallback and PR reviewability.

## Outcomes

By the end of the task:

- the requested Langfuse prompt exists and is inspectable
- if the prompt already existed, a new version was created instead of overwriting local code
- the prompt is tagged with the owning domain name (e.g., `deals`)
- the prompt name is auto-derived from the directory structure (e.g., `deals/triage/agents/classifier`)
- a corresponding `.md` file exists in the domain's `prompts/` directory
- labels and commit messages are applied intentionally
- the user understands how to connect the managed prompt back to a PydanticAI agent run

## Required Inputs

Before doing live prompt operations, confirm these env vars exist:

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST`

If they are missing, ask the user for them before claiming the operation is runnable.

## First Reads

Read these files before changing code or running prompt operations:

- `backend/packages/domains/llm/README.md`
- `backend/packages/domains/llm/src/ezra_llm/schemas.py`
- `backend/packages/domains/llm/src/ezra_llm/langfuse.py`

Then use the bundled script:

- `scripts/langfuse_prompts.py`

Run it through the backend workspace so the Langfuse SDK is available:

- `cd backend && uv run python ../.claude/skills/ezra-langfuse-prompts/scripts/langfuse_prompts.py list`
- `cd backend && uv run python ../.claude/skills/ezra-langfuse-prompts/scripts/langfuse_prompts.py upsert ...`

## Naming Conventions

### Prompt Names — Auto-Derived from Directory Structure

Prompt names are **not chosen manually**. They are derived automatically from the file path by `scripts/sync-langfuse-prompts.py`:

1. Find the `ezra_*` ancestor directory above `prompts/`
2. Strip the `ezra_` prefix
3. Take the path from there to the `.md` file, dropping the `prompts/` segment

Examples:
```
ezra_deals/triage/prompts/agents/classifier.md        → deals/triage/agents/classifier
ezra_deals/triage/prompts/gate_assessment.md           → deals/triage/gate_assessment
ezra_deals/triage/prompts/matching/matcher.md          → deals/triage/matching/matcher
ezra_sales_interactions/extraction/prompts/extraction.md → sales_interactions/extraction/extraction
ezra_crm_sync/prompts/revision.md                      → crm_sync/revision
```

The `/` in names creates folder structure in Langfuse. Subdirectories under `prompts/` are preserved.

### Tags

Tags are the first component of the derived name (the domain name without `ezra_`):
- `deals` for all `deals/triage/...` prompts
- `sales_interactions` for all `sales_interactions/...` prompts
- `crm_sync` for all `crm_sync/...` prompts

### Labels

- `latest` — the current working version, used by `fetch_prompt(name, label="latest")`
- `production` — only applied when the user explicitly wants that version served as the default in production

## Prompt Storage in Code

Every prompt in Langfuse must also exist as a `.md` file in a `prompts/` directory within the owning package:

```
backend/packages/domains/{domain}/src/ezra_{domain}/
  {module}/
    prompts/
      agents/
        classifier.md
        deal_overview.md
      gate_assessment.md
      matching/
        matcher.md
```

These files serve as:
1. Fallback when Langfuse is unavailable
2. PR-reviewable prompt changes
3. The initial content to push to Langfuse for new prompts
4. Auto-discovery source for the sync script

Directories named `templates/` are excluded from discovery.

## Sync Script

The sync script at `scripts/sync-langfuse-prompts.py` handles all prompt sync operations. It auto-discovers prompts from `prompts/**/*.md` files — no manifest or config files needed.

### Usage

```bash
# Preview what would be synced (no network calls)
python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-up --dry-run

# Push all local .md files to Langfuse
python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-up

# Preview what Langfuse has that differs from local
python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-down --dry-run

# Pull Langfuse prompts to local .md files
python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-down

# Use a specific label (default: latest)
python scripts/sync-langfuse-prompts.py --base-dir backend/packages --sync-down --label production
```

### What Each Mode Does

- **`--sync-up`** — For each discovered `.md` file, checks if Langfuse has a prompt with the same name and content. If missing or different, creates a new version.
- **`--sync-up --dry-run`** — Lists all discovered prompts and their derived Langfuse names. No network calls.
- **`--sync-down`** — For each discovered `.md` file, fetches the Langfuse version. If different, overwrites the local file. Also reports Langfuse-only prompts that have no local `.md` file.
- **`--sync-down --dry-run`** — Same as sync-down but prints diffs without writing files.

## Procedures

### Creating a New Prompt

1. Write the `.md` file in the appropriate `prompts/` directory.
2. Run `--sync-up --dry-run` to verify the derived Langfuse name looks correct.
3. Run `--sync-up` to push it to Langfuse.
4. Wire `fetch_prompt("derived/name", ...)` in the agent code with the name from step 2.
5. Commit the `.md` file and code change.

### Iterating on a Prompt

1. Edit the prompt in the Langfuse UI (fast feedback loop, no deploys).
2. When satisfied, run `--sync-down --dry-run` to preview changes.
3. Run `--sync-down` to pull the updated content to local `.md` files.
4. Commit the updated `.md` file(s) in a PR for review.

### Checking for Drift

1. Run `--sync-down --dry-run` to see what differs between Langfuse and local files.
2. Also surfaces Langfuse-only prompts that someone created in the UI without a local `.md` file.

### Before a Deploy

1. Run `--sync-up` to ensure Langfuse has the latest from code (in case someone edited `.md` files directly in a PR without pushing to Langfuse).

## Integration Guidance

For PydanticAI agents, prefer this shape:

1. Store the prompt as a `.md` file in the domain's `prompts/` directory.
2. Run `--sync-up` to push to Langfuse.
3. Fetch the prompt from Langfuse at runtime with `fetch_prompt()`, passing the `.md` content as `fallback=`.
4. Build the `Agent(...)` instructions or system prompt from that fetched prompt.
5. When running the agent, attach all required trace fields:
   - `workflow_name` for the app identity
   - `step_name` for the action
   - `tags` with the domain name
   - `user_id` for cost attribution
   - `session_id` for session grouping
   - `prompt_ref=prompt_ref` for trace linkage
6. Continue using `run_agent()` / `run_agent_sync()` for observability.

```python
from pathlib import Path
from ezra_llm import fetch_prompt, LLMRunContext, run_agent

_PROMPT_PATH = Path(__file__).parent / “prompts” / “agents” / “classifier.md”
FALLBACK_PROMPT = _PROMPT_PATH.read_text().strip()

prompt_ref = fetch_prompt(“deals/triage/agents/classifier”, label=”latest”, fallback=FALLBACK_PROMPT)
system_text = (
    prompt_ref.prompt_object.compile()
    if prompt_ref.prompt_object is not None
    else FALLBACK_PROMPT
)
```

This keeps prompt storage in Langfuse while leaving agent/tool/output logic in product code.

## Anti-Patterns

Do not:

- move business-domain output schemas into `ezra_llm`
- add a local prompt registry when Langfuse prompt management is enough
- mark every new prompt version as `production` by default
- add a second abstraction layer for prompts unless a real call site needs it
- claim a prompt is “updated” when the operation actually produced a new Langfuse version
- skip creating the `.md` fallback file in code
- manually choose prompt names — always let the sync script derive them from the file path
- create `_langfuse.json` or manifest files — the directory structure is the convention
