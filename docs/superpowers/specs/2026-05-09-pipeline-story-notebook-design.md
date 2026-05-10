# End-to-End Pipeline Story Notebook — Design

**Date:** 2026-05-09
**Status:** Spec — pending implementation plan
**Branch:** `feature/pipeline-story-notebook` off `rebuild-notebooks-codex-aware`
**Target file:** `notebooks/07_full_pipeline_story.ipynb`

---

## 1. Goal

Add a new manual-inspection notebook that walks an operator through the **complete HSBTech pipeline end-to-end**, in real time, against real Linear / real GitHub / real Claude SDK sessions, paced one cell at a time.

The story the notebook tells, in operator order:

> "Here is my `plan.md`. Watch the Backlog Agent decompose it into an EPIC + User Stories + Tasks on a real Linear board. Watch the Global Orchestrator find the ready tasks. Watch the Risk Agent prioritize them. Watch the Main Orchestrator dispatch them in parallel. Watch each Work Item Orchestrator run Builder → Git → QA inside its own worktree, opening real stacked PRs against the EPIC integration branch. Watch UAT validate the User Story; if it fails, watch the fix subtasks appear in Linear and watch the next cycle pick them up. Repeat the outer cycle until no ready tasks remain. Inspect what landed in the Knowledge Store. Inspect any auto-improvement triggers Risk Agent skill 14 surfaced."

This is not automation. The operator drives — every phase is its own cell (or pair of cells), gated, costed, inspected, then the operator decides whether to advance.

## 2. Non-goals

- Not a runner / not a script / not unattended. There is no `while True`, no auto-retry, no scheduling.
- Not a fixture-based walkthrough. All execution is real; no mock / stub / pre-baked outputs.
- Not a replacement for any existing notebook. Notebooks 00–06 keep their slice-focused scope. This is the only one that crosses every slice in narrative order.
- Not an operator onboarding tutorial. `GET-STARTED.md` and `MILESTONE-UAT.md` already serve that pathway. This notebook assumes the operator has the prerequisites and wants to *see* the pipeline run end-to-end.
- Not a coverage gap closer for guardrails. Notebook 00 already audits G1/G2/G3/G4/G9/RISK-04 invariants in isolation. This notebook references them in passing as the relevant phase fires, but does not re-prove them.

## 3. Why this exists

The existing notebooks each cover a slice:

| Notebook | Slice |
|----------|-------|
| 00 | Guardrail invariants |
| 01 | Pydantic contract fuzzing |
| 02 | Risk score formula + ready-task filter (pure logic) |
| 03 | Main Orchestrator dispatch decision |
| 04 | Linear MCP + Knowledge Store probes (read-only) |
| 05 | Per-agent smoke on minimal fixtures |
| 06 | One Work Item Orchestrator end-to-end |

None of them tell the **outer story**: how a `plan.md` becomes a fully-decomposed Linear board, how Global+Main fan that out, how the round-trip continues across multiple cycles when UAT fails and creates fix subtasks, how the Knowledge Store accumulates lessons across runs. The user's prompt naming this gap directly:

> *"I am missing a notebook that tells the story end to end, like: I have a plan, here is how step by step everything would work."*

Filling that gap with one operator-paced live notebook lets a reviewer or new operator see the system run for real, without having to stitch six other notebooks together in their head.

## 4. Scope

### In scope

- One new notebook `notebooks/07_full_pipeline_story.ipynb`
- Generation via `notebooks/_build_notebooks.py` (new `NB_07` spec list, registered in `main()`'s `targets` dict)
- README update under `notebooks/README.md` adding row 07 to the Tiers table and describing its env-var requirements
- New env vars only if needed beyond what notebooks 04–06 already declare; reuse `HSB_NOTEBOOK_PLAN_MD`, `HSB_NOTEBOOK_LINEAR_TEAM_ID`, `HSB_NOTEBOOK_RUN_LIVE`, `HSB_NOTEBOOK_SCRATCH_DIR`, `CLAUDE_CODE_OAUTH_TOKEN`

### Out of scope

- New helpers in `_helpers.py` beyond a small `assert_upstream_ran_live(state, phase)` shim if needed for the gating discipline (§7)
- Changes to any agent module
- Changes to any contract module
- New tests beyond an `nbconvert --execute` smoke check in CI (already the existing pattern per `notebooks/README.md`)
- New fixtures of any kind

## 5. Notebook structure

13 sections total: a setup block, an architecture map, and 11 numbered phases.

### Setup
- `assert_g1_safe()` — refuse to proceed if `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is set
- `runtime_summary()` — render which agents are Claude vs Codex per `HSB_RUNTIME_*`
- Env-var inventory cell — for each required var, render `set` / `unset` and what it controls. Banner text:
  > "This notebook makes real Linear writes, real GitHub PRs, real Claude SDK calls. Confirm `HSB_NOTEBOOK_LINEAR_TEAM_ID` points to a sandbox team."
- Hard-refusal: if `HSB_NOTEBOOK_RUN_LIVE` is unset, every live cell below will print a `gated(...)` skip banner. The operator can still walk the markdown.

### Phase 0 — Architecture map
**Markdown only, no execution.** ASCII diagram of the L0/L1/L2 spine + a table mapping each agent to:
- Its level (L0/L1/L2 or "support")
- Its execution pattern (stateful `ClaudeSDKClient` / one-shot `query()` / pure Python)
- Whether it's runtime-flippable (Backlog yes; WIO hard-blocked from Codex; others default-Claude until ported)
- Its allow-list shape (Backlog 4 tools, Builder 7, Git 12, QA 3, UAT 4, etc.)

Cross-referenced to `README.md` §3 and `_sdk_options.py` so a reader can verify the table against source.

### Phase 1 — Plan input *(read-only)*
Resolve `HSB_NOTEBOOK_PLAN_MD`. Print head and tail of the plan so the operator confirms what's about to be parsed. Render the `BacklogInput` Pydantic model (with `model_config = {"extra": "forbid"}` shown). Show the equivalent CLI: `hsb backlog plan --plan ...`.

No SDK calls, no Linear writes. This is the "are you sure?" cell.

### Phase 2 — Backlog Agent decomposes plan → Linear *(live)*
Construct `BacklogInput(plan_source=..., project_context=ProjectContext(...))`. Call `await run_backlog_agent(input)`.

What runs:
- One LLM call (Claude or Codex per `HSB_RUNTIME_BACKLOG`)
- Real Linear writes via `run_validated_linear_agent` — EPIC issue, User Story sub-issues, Task sub-issues, parent linkage, traceability metadata
- BKPK-05 idempotency: re-running this cell on the same plan creates **0** new EPICs

What gets rendered:
- The returned `BacklogOutput` tree (EPIC → Stories → Tasks with acceptance_criteria + traceability map)
- Active guardrails called out in markdown above the cell: G1 (OAuth-only), G5 (the `linear_write_guard` decorator on `LinearAgent` write methods is scoped to callers from `risk_agent.py` — Backlog is unaffected), Backlog allow-list (4 tools)

### Phase 3 — Inspect Linear *(live, read-only)*
Read back through `run_validated_linear_agent(operation="read", payload={"issueId": <epic_id>})` then traverse children. Render the EPIC → Story → Task tree as it actually landed on the board, with each issue's `id`, `status`, parent link, and labels.

CLI equivalent: `hsb show-state`. Operator can compare the rendered tree against the Linear UI directly.

### Phase 4 — Global Orchestrator → ready queue *(live, pure-Python, no LLM cost)*
Call `await GlobalOrchestrator().get_ready_tasks()`. Render:
- Ready tasks (status=todo, no blocking deps)
- Blocked tasks with the reason

Markdown calls out: this is **L1**, deterministic, no SDK session.

### Phase 5 — Risk Agent priority sort *(live, pure-Python)*
Call `RiskAgent().get_priority_queue(raw_task_ids, linear_state)`. This is the missing-from-original-draft step that `global_orchestrator.py:128` actually calls between "ready" and "dispatched."

Render the same queue from Phase 4, now risk-prioritized. Show each item's score and the formula contribution (start=100, −10/QA failure, −5/fix subtask, −15 if UAT failed, −5/rework cycle, min=0).

Markdown reference: RISK-01 deterministic property test (`hypothesis @given`).

### Phase 6 — Main Orchestrator dispatch (one cycle, parallel) *(live, expensive)*
The big one. Call `await run_main_orchestrator(mode="parallel")`.

What runs concurrently:
- Multiple `WorkItemOrchestrator` SDK sessions, each in its own git worktree at `.worktrees/<task-slug>`
- Each WIO drives Step 1 (Intelligence enrichment via Glob+Grep on `knowledge/`) → Steps 2-4 (Builder → Git → QA cycle, cap 3) → Step 5 (Intelligence ingestion if criteria met)
- Real `gh` calls: `gh pr create` against `epic/LIN-...`, `gh pr diff`, `gh pr view`
- Optimistic-lock claiming via `updatedAt` re-read (T-4-01 / MORD-03)

Output:
- Live structured stdout per WIO (skill prompts + every tool call) — verbose, several hundred KB
- Pre-cell warning: "expect a few minutes wall-clock"
- Post-cell render: `MainOrchestratorOutput` summary (mode, dispatched items, cycle_summary)

Active guardrails called out: G2 (no Agent tool), G3 (`assert_no_task_dispatch` in every WIO receive loop), G7 (`error_max_turns` raises), G8 (120K token warn), G9 (Knowledge ingest validation), MORD-03 (no double-claim), T-4-04 (5-key env allowlist on subprocess).

### Phase 7 — Inspect what one WIO did *(live, read-only)*
Operator picks one task ID from Phase 6's dispatched list. Cell renders:
- Linear comments on the task (decision / impl note / QA finding posts)
- `gh pr view <pr_url>` output
- `git log --oneline epic/LIN-...` to show the commit graph
- Verification of stacked-PR shape: assertion that the PR's base is `epic/LIN-...` and not `main`

Pure read-only. No state change.

### Phase 8 — Drive the next cycle *(live)*
Re-run `await run_main_orchestrator(mode="parallel")`. The Global Orchestrator may now report:
- Sibling tasks of Story 1 ready
- Story 1 itself UAT-ready (`_detect_uat_ready_user_stories` fires when all child tasks are QA-approved)
- UAT dispatched **inline** by Global Orchestrator (no separate cell — it happens within this cycle)

Cell renders the cycle summary, including which UAT runs fired and their pass/fail results. Re-running this cell drives one more cycle.

### Phase 9 — UAT outcome + the round-trip *(live, read-only after Phase 8)*
Read the `UATResult` from Linear comments. Render side-by-side with the Phase 2 acceptance_criteria so the operator sees the loop-back: "this is the same list."

Two paths:
- **Approved** → Story `uat_approved` → Story-level done
- **Changes required** → fix subtasks created in Linear (Global Orchestrator's `create_subtasks on changes_required` path)

The fix subtasks become new ready tasks. Re-running Phase 8 picks them up. **This is the round-trip the user asked for** — visible explicitly in Linear and in the next Phase 8 cycle output.

Active guardrails: G6 (UAT cycle cap = 3 with escalation comment), G10 (B1 coverage + B3 banned-token regex pre-persist).

### Phase 10 — Until done *(markdown + live read-only)*

Markdown instruction: "Re-run Phase 8 as many times as you want. The notebook intentionally does **not** auto-iterate. Each click of Phase 8 = one outer cycle. When `GlobalOrchestrator.get_ready_tasks()` returns empty, advance to this phase's read-only cell."

Read-only cell (no SDK / no Linear writes) that renders the final board state: every leaf `done`, Stories `uat_approved`, EPIC integration branch open with all stacked task PRs approved. **Awaiting human merge** — explicit marker in markdown that the system never merges to main. CLI equivalent: `hsb show-state`.

If the operator advances to this cell while ready tasks remain, the cell prints the still-ready queue and instructs them to go back to Phase 8.

### Phase 11 — Knowledge Store grew + skill 14 signals *(live, read-only + one cheap LLM call)*

Two cells:

**11a — Knowledge Store delta.** `ls knowledge/{architecture,qa,implementation,backlog,risk}/` — render new entries written during this run (compare against `git status` on the `knowledge/` directory). For each new entry, render its YAML frontmatter so the operator sees the G9-validated `applicability` field is concrete (not "all tasks", not "tbd").

**11b — Auto-improvement triggers.** Call `await RiskAgent().detect_improvement_triggers()`. This is the air-gapped haiku call:
- `allowed_tools=[]`
- `mcp_servers=None`
- `model="haiku"`
- `max_turns=3`
- `max_budget_usd=0.05`

Render any returned `AutoImprovementTrigger` items. Markdown reference: G4 (skill 14 air-gap), 4-layer RISK-04 defense.

### Phase 12 — Pointers
Markdown only. Links / file paths to:
- Notebooks 00–06 (with one-line description of each slice)
- `README.md` §3 The 11 agents, §4 Guardrails
- `GET-STARTED.md` for operator onboarding
- `.planning/MILESTONE-UAT.md` for the 24-step acceptance run
- CLI cheat sheet: `hsb show-state`, `hsb show-next-action`, `hsb run --parallel`, `python run_loop.py`

## 6. Per-phase contract

For each numbered phase, the spec list in `_build_notebooks.py` will produce three cells (or two for read-only / markdown-only phases):

1. **Markdown header.** One paragraph: what runs, why, side effects, which guardrails are active, CLI equivalent if any.
2. **Pre-flight + live cell.** Single Python cell that:
   - Calls `assert_g1_safe()`
   - Reads required env vars; if any missing, prints `gated(...)` and returns early
   - Phase 6+ additionally checks that upstream phases ran live this session (see §7)
   - Performs the actual call
   - Renders structured output (Pydantic dump, `gh` output, tree, etc.)
3. **(Phase 6, 8 only) Inspection cell.** Optional follow-up cell for read-back / verification.

## 7. Gating discipline

Every live cell:

- Calls `assert_g1_safe()` before constructing SDK options
- Checks its specific required env vars; prints `gated(...)` banner and skips if missing
- Won't run unless `HSB_NOTEBOOK_RUN_LIVE=1`
- **Phase 6+ additionally asserts upstream phases ran live in this session.** Implementation: a small in-notebook session-state dict (e.g., `_session_state = {"phase_2_ran": False, "epic_id": None, ...}`) that earlier live cells populate. Phase 6's cell asserts `_session_state["phase_2_ran"]` is `True` and that `_session_state["epic_id"]` is set; otherwise it refuses with a clear message ("run Phase 2 live first; you cannot dispatch against a board you haven't built").

This prevents the failure mode of "I read the markdown for Phases 1-5, I'll just click Phase 6 and see what happens" — which would dispatch against whatever's already in Linear, possibly a production board.

The session-state dict is small and lives in the notebook itself (no helper file). Resetting it just means restarting the kernel, which is the right model — a fresh kernel = a fresh story.

## 8. Implementation approach

### Files touched
- **New:** `notebooks/07_full_pipeline_story.ipynb` (generated)
- **Modified:** `notebooks/_build_notebooks.py` — add `NB_07: Spec = [...]` and register it in `main()`'s `targets` dict
- **Modified:** `notebooks/README.md` — add row 07 to the Tiers table; document env vars (which are already a subset of what's listed); add a paragraph describing the notebook's purpose
- **No source changes** — every helper this notebook needs already exists in `_helpers.py`. If the upstream-ran-live assertion logic grows more than ~10 lines, it goes in `_helpers.py` as `assert_upstream_ran_live(state, phase)`. Otherwise inline.

### Build flow
1. Author `NB_07` as a `Spec` list of `(cell_type, cell_id, source)` tuples in `_build_notebooks.py`, following the exact pattern of `NB_06`
2. Register in `targets` dict
3. Run `uv run python notebooks/_build_notebooks.py` to materialize the `.ipynb`
4. Open in `jupyter lab notebooks/` and review the rendered cells
5. Commit both the spec edit and the generated notebook in the same commit (matches the project's existing convention per `notebooks/README.md` §Maintenance)

### Helpers needed
None new for an MVP. If the session-state assertion logic becomes repetitive, extract `assert_upstream_ran_live(state: dict, phase: str)` to `_helpers.py`.

## 9. Testing approach

- **Smoke test (CI / pre-commit):** the existing nbconvert pattern from `notebooks/README.md`:
  ```bash
  uv run jupyter nbconvert --to notebook --execute notebooks/07_full_pipeline_story.ipynb \
    --output /tmp/07-executed.ipynb
  ```
  Without `HSB_NOTEBOOK_RUN_LIVE=1`, every live cell skips with a `gated(...)` banner and the notebook executes top-to-bottom in seconds. This confirms the markdown / imports / pre-flight code stays valid; it does NOT verify the live path.

- **Live verification:** the operator runs the notebook end-to-end against a sandbox Linear team and the `hsb-test-fixture` GitHub repo. This is by design — there's no automated way to verify the live path without spending real tokens, and the existing test suite (106 unit / 18 evals / 59 integration) is the assertion-bearing surface for the underlying code.

- **No new tests in `tests/`.** This notebook is a manual-inspection tool; its job is to make the system *legible*, not to assert correctness. Correctness is asserted by the test suite.

## 10. Risks and open questions

### Risks

- **R1 — Live cell kerning.** If a Phase 6 dispatch crashes mid-cycle (e.g., a real `gh` failure), the worktree cleanup must still run (via WIO's `try/finally`). Notebook should re-render the failure clearly, not swallow it. **Mitigation:** existing `error_max_turns` G7 handling already raises; notebook just lets the exception surface.

- **R2 — Operator dispatches against a non-sandbox Linear.** The setup banner names this risk explicitly, but there is no programmatic check for "is this team a sandbox?" **Mitigation:** the banner; reuse existing `HSB_NOTEBOOK_LINEAR_TEAM_ID` env var (operator must set it explicitly, can't fall back to default).

- **R3 — Spend during Phase 6 / 8.** Cumulative cost of multiple WIO sessions plus UAT plus Risk skill 14 could be material. **Mitigation:** explicit cost-warning markdown in Phase 6's header; Phase 8 is one cycle per operator click (no auto-iteration), so the operator decides when to stop; Phase 11b uses haiku capped at `max_budget_usd=0.05`.

- **R4 — Codex hard-block surfacing.** Phase 6 will fail if `HSB_RUNTIME_WIO=codex` is set in env. **Mitigation:** Setup cell renders `runtime_summary()`, which surfaces the WIO assignment so the operator catches this before clicking Phase 6.

### Open questions

- **OQ1 — Should Phase 0's architecture diagram be Mermaid or ASCII?** Mermaid renders nicely in Jupyter Lab but not in plain `nbconvert --to script` outputs. ASCII is universal but uglier. *Default: ASCII to match the existing notebook style; revisit if the operator wants a richer diagram.*

- **OQ2 — Should Phase 11b skip if Phase 6 skipped?** The skill 14 call is meaningful even on an empty system, but cheaper to run after some real work has happened. *Default: Phase 11b runs unconditionally if `HSB_NOTEBOOK_RUN_LIVE=1`; the haiku call is bounded at $0.05.*

- **OQ3 — Should the README's Tiers table get a new "cost" column?** Currently it has "LLM/MCP cost: Low / Variable / High". Notebook 07 spans Low → High depending on phase. *Default: tag it "Variable, gated per-phase" with a footnote pointing to §Phase 6 / §Phase 11b.*

## 11. Acceptance criteria for the spec

This design is implementation-ready when:

- [x] Each numbered phase has a clear "what runs / what's gated / what's rendered" definition (§5)
- [x] Gating discipline is unambiguous and consistent with existing notebooks 04–06 (§7)
- [x] No new env vars introduced (reuses existing inventory) (§4)
- [x] No source changes outside `notebooks/` and `notebooks/README.md` (§8)
- [x] Risks are named with mitigations or explicit residual acceptance (§10)
- [x] Open questions have defaults so the implementer is unblocked even if revisited later (§10)

When all six are checked and the operator approves the spec, the next step is to invoke the `superpowers:writing-plans` skill to produce the implementation plan.
