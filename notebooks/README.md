# Manual system-inspection notebooks

Hands-on notebooks for poking at HSBTech internals — intermediate state that
the automated test suite (106 unit / 18 evals / 59 integration) doesn't surface:
prompt assembly, queue contents, MCP responses, hook outputs, guardrail wiring.

These notebooks **do not replace** the test suite. They complement it by giving
you a place to read agent state interactively while the system is paused.

## Tiers

| Notebook | What it covers | LLM/MCP cost | Side effects |
|----------|----------------|--------------|--------------|
| `00_guardrails_audit.ipynb` | G1/G2/G3/G4/G9/RISK-04 invariants + runtime adapter audit | None | None |
| `01_contracts_playground.ipynb` | Pydantic boundary fuzzing — QA cycle cap, G9, etc. | None | None |
| `02_risk_and_global_pure_logic.ipynb` | Risk score formula, priority queue, ready-task filter | None | None |
| `03_main_orchestrator_dispatch.ipynb` | Cascade vs parallel, T-4-04 env allowlist, worktree lifecycle | None | Creates a temp git repo locally |
| `04_linear_and_knowledge_readonly.ipynb` | Linear MCP read-only + Knowledge Store retrieval + runtime probes | Low (read-only) | None |
| `05_per_agent_smoke.ipynb` | Backlog / Builder / Git / QA / UAT on minimal fixtures | Variable, gated | Variable, gated |
| `06_wio_full_loop.ipynb` | One Work Item Orchestrator end-to-end (Claude-only by hard-block) | High, gated | Yes — gated on `HSB_NOTEBOOK_RUN_LIVE=1` |

Notebooks 04–06 read environment flags before doing anything that costs tokens
or touches Linear/git. Default state = explore-only. Set the flag explicitly
when you want to run live.

## Runtime selection (Claude vs Codex)

These notebooks are **runtime-agnostic**: each notebook supports both Claude
and Codex via `HSB_RUNTIME_<AGENT>` (per the
[Codex alt-runtime spec](../docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md)).
There's one set of files — you don't pick a notebook by runtime, you pick a
runtime by env var. The first cell of each notebook prints the current
selection so it's obvious what you're about to exercise.

Today only the **Backlog Agent** is fully runtime-flippable. WIO (notebook 06)
is hard-blocked from Codex because its multi-turn `ClaudeSDKClient` session
has no Codex equivalent yet — `resolve_runtime("wio")` raises if you set
`HSB_RUNTIME_WIO=codex`. The other agents inherit the default (Claude) until
they're ported through the runtime seam.

## Running

From the repo root:

```bash
uv sync --extra dev          # installs jupyter alongside dev deps
uv run jupyter lab notebooks/
```

Or, if you prefer a plain venv:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
jupyter lab notebooks/
```

To non-interactively confirm every cell still passes (CI / sanity check):

```bash
for nb in notebooks/0*.ipynb; do
  uv run jupyter nbconvert --to notebook --execute "$nb" \
    --output "/tmp/$(basename $nb .ipynb)-executed.ipynb"
done
```

To regenerate the notebooks from their compact source spec (useful after
editing `_build_notebooks.py`):

```bash
uv run python notebooks/_build_notebooks.py
```

## Environment

The notebooks read these (all optional, all gated):

| Var | Notebook | Purpose |
|-----|----------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | 04, 05, 06 | OAuth2 token for Claude (G1 — never use `ANTHROPIC_API_KEY`) |
| `CODEX_HOME` | 04, 05 | Override `~/.codex` location for the Codex auth/config probe |
| `HSB_RUNTIME_<AGENT>` | 04, 05 | Per-agent runtime — `claude` (default) or `codex`. WIO hard-blocked from `codex`. |
| `HSB_NOTEBOOK_RUN_LIVE` | 04, 05, 06 | Set to `1` to actually call SDK / Linear MCP |
| `HSB_NOTEBOOK_LINEAR_TEAM_ID` | 04, 05 | Sandbox Linear team ID for read probes |
| `HSB_NOTEBOOK_LINEAR_ISSUE_ID` | 04 | Linear issue ID for the `get_issue` read probe |
| `HSB_NOTEBOOK_PLAN_MD` | 05 | Path to a plan.md to drive a Backlog Agent live run |
| `HSB_NOTEBOOK_SCRATCH_DIR` | 03, 05, 06 | Where to put a throwaway git repo for Builder / Git fixtures |
| `HSB_NOTEBOOK_WIO_TASK_ID` | 06 | Sandbox Linear LIN-ID for the WIO live run |

Forbidden (G1):

| Var | Why |
|-----|-----|
| `ANTHROPIC_API_KEY` | Metered API key — Claude must use OAuth via `CLAUDE_CODE_OAUTH_TOKEN`. |
| `OPENAI_API_KEY` | Metered API key — Codex must use OAuth via `codex login --device-auth`. |

Cells that need a flag the env doesn't set should print a clear "skipped — set
$VAR to run live" message and continue.

## Codex prerequisites

If any agent has `HSB_RUNTIME_<AGENT>=codex` and you intend to run a live cell:

1. `codex login --device-auth` — writes `~/.codex/auth.json`.
2. `~/.codex/config.toml` must contain `forced_login_method = "chatgpt"`
   (G1-Codex: API-key auth disallowed).
3. Any MCP server the agent uses must have a `[mcp_servers.<name>]` block in
   the same config — `verify_codex_mcp` will raise on the first missing block.

Notebook 04's setup cell calls `codex_available()` and prints whether the
above is satisfied before any live cell tries to instantiate `CodexRuntime`.

## Style

- Each notebook starts with a `# Setup` cell that imports from `_helpers.py`.
- Top of every section: a one-paragraph "what this checks and why" markdown cell.
- Assertions raise on failure — a green run = invariants hold.
- Never `git push`, `gh pr create`, or write to Linear from a notebook unless
  the cell explicitly says it does and is gated by `HSB_NOTEBOOK_RUN_LIVE=1`.

## Maintenance

The notebooks are generated from `_build_notebooks.py` to keep diffs clean
(no execution-count noise, deterministic JSON formatting). Edit the spec
lists in that file, run the script, and commit both. The shared helpers
in `_helpers.py` are the only seam between notebook code and `hsb.*`. If
the runtime adapter relocates (`hsb.runtime.*` -> something else), update
`_helpers.py` first — that's the only file that should need to change.
