# Manual system-inspection notebooks

Hands-on notebooks for poking at HSBTech internals — intermediate state that
the automated test suite (106 unit / 18 evals / 59 integration) doesn't surface:
prompt assembly, queue contents, MCP responses, hook outputs, guardrail wiring.

These notebooks **do not replace** the test suite. They complement it by giving
you a place to read agent state interactively while the system is paused.

## Tiers

| Notebook | What it covers | LLM/MCP cost | Side effects |
|----------|----------------|--------------|--------------|
| `00_guardrails_audit.ipynb` | G1/G2/G4/RISK-04 structural invariants | None | None |
| `01_contracts_playground.ipynb` | Pydantic boundary fuzzing — QA cycle cap, G9, etc. | None | None |
| `02_risk_and_global_pure_logic.ipynb` | Risk score formula, priority queue, ready-task filter | None | None |
| `03_main_orchestrator_dispatch.ipynb` | Cascade vs parallel, T-4-04 env allowlist, worktree lifecycle | None | Creates a temp git repo locally |
| `04_linear_and_knowledge_readonly.ipynb` | Linear MCP read-only + Knowledge Store retrieval | Low (read-only) | None |
| `05_per_agent_smoke.ipynb` | Backlog / Builder / Git / QA / UAT on minimal fixtures | Variable, gated | Variable, gated |
| `06_wio_full_loop.ipynb` | One Work Item Orchestrator end-to-end | High, gated | Yes — gated on `HSB_NOTEBOOK_RUN_LIVE=1` |

Notebooks 04–06 read environment flags before doing anything that costs tokens
or touches Linear/git. Default state = explore-only. Set the flag explicitly
when you want to run live.

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

## Environment

The notebooks read these (all optional, all gated):

| Var | Notebook | Purpose |
|-----|----------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | 04, 05, 06 | OAuth2 token (G1 — never use `ANTHROPIC_API_KEY`) |
| `HSB_NOTEBOOK_RUN_LIVE` | 04, 05, 06 | Set to `1` to actually call SDK / Linear MCP |
| `HSB_NOTEBOOK_LINEAR_TEAM_ID` | 04, 05 | Sandbox Linear team ID for read probes |
| `HSB_NOTEBOOK_SCRATCH_DIR` | 03, 05, 06 | Where to put a throwaway git repo for Builder / Git fixtures |

Cells that need a flag the env doesn't set should print a clear "skipped — set
$VAR to run live" message and continue.

## Style

- Each notebook starts with a `# Setup` cell that imports from `_helpers.py`.
- Top of every section: a one-paragraph "what this checks and why" markdown cell.
- Assertions raise on failure — a green run = invariants hold.
- Never `git push`, `gh pr create`, or write to Linear from a notebook unless
  the cell explicitly says it does and is gated by `HSB_NOTEBOOK_RUN_LIVE=1`.

## Maintenance

These notebooks deliberately import from `hsb.agents.*` directly (not through
any runtime adapter abstraction). If a future runtime-flip lands a `runtime/`
Python package, update the helper imports in `_helpers.py` first — that's the
only file that should need to change.
