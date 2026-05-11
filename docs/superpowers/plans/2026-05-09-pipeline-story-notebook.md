# Pipeline Story Notebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `notebooks/07_full_pipeline_story.ipynb` — an operator-paced live walkthrough of the full HSBTech pipeline (plan.md → Backlog → Linear → Global → Risk → Main → WIO fan-out → UAT → fix-subtask round-trip → Knowledge Store → Risk skill 14).

**Architecture:** The notebook is generated from a `Spec` list `NB_07` added to `notebooks/_build_notebooks.py`, registered in `main()`'s `targets` dict. Cells follow the existing `(cell_type, cell_id, source)` pattern using `md(...)` and `code(...)` helpers. The notebook makes real Linear writes / GitHub PRs / Claude SDK calls, gated behind `HSB_NOTEBOOK_RUN_LIVE=1` plus per-phase env vars and a kernel-session state dict that prevents skipping markdown to expensive cells.

**Tech Stack:** Python 3.12, `claude-agent-sdk`, `pydantic`, `hsb.agents.*`, `hsb.contracts.*`, Jupyter notebook JSON v4, `nbconvert` for the smoke test, `gh` CLI for the PR.

**Source spec:** [`docs/superpowers/specs/2026-05-09-pipeline-story-notebook-design.md`](../specs/2026-05-09-pipeline-story-notebook-design.md). Refer to the spec for *what* each phase does and *why*; this plan covers *how* — file edits, exact cell sources, commands, commit protocol.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `notebooks/_build_notebooks.py` | Modify | Add `NB_07: Spec = [...]` (~40 cells) and register `"07_full_pipeline_story.ipynb": NB_07` in `main()`'s `targets` dict |
| `notebooks/07_full_pipeline_story.ipynb` | Create (generated) | Materialized output from the build script — committed alongside the spec edit per the repo convention |
| `notebooks/README.md` | Modify | Add row 07 to the Tiers table; add a paragraph in §Environment if any new env vars are introduced (none expected) |
| `notebooks/_helpers.py` | No change | Existing helpers cover all needs |
| Source code | No change | This is a pure inspection notebook |

---

## Task 1: Add NB_07 spec to `_build_notebooks.py`

**Files:**
- Modify: `notebooks/_build_notebooks.py` (insert `NB_07` between `NB_06` and `def main()`; register in `targets`)

This is the bulk task. It creates the spec list of `(cell_type, cell_id, source)` tuples for ~40 cells covering Setup + Phase 0–12.

The full cell content is below in three groups:

### 1.1 Setup + Phase 0 (architecture map)

- [ ] **Step 1.1: Insert `NB_07: Spec = [` block after `NB_06`'s closing `]` and before `def main():`**

The full Setup + Phase 0 cell sources:

```python
NB_07: Spec = [
    (
        "markdown",
        "intro",
        md(
            """\
# 07 — Full pipeline story (live, operator-paced, gated)

Walks the complete HSBTech pipeline against your real Linear sandbox + the `hsb-test-fixture` GitHub repo + real Claude SDK calls, one cell at a time. No automation, no auto-iteration — every phase is one click and you decide whether to advance.

The story:

```
plan.md
  -> Backlog Agent decomposes -> EPIC + Stories + Tasks in Linear
  -> Global Orchestrator finds ready tasks
  -> Risk Agent priority-sorts the queue
  -> Main Orchestrator dispatches in parallel (one cycle)
  -> N x Work Item Orchestrator: enrichment -> Builder -> Git -> QA (cap 3) -> ingestion
  -> stacked PRs targeting epic/LIN-... (never main)
  -> UAT validates Story acceptance criteria
       -> approved: Story done
       -> changes_required: fix subtasks created -> next outer cycle picks them up
  -> repeat until GlobalOrchestrator.get_ready_tasks() returns empty
  -> inspect Knowledge Store delta + Risk Agent skill 14 auto-improvement triggers
```

**This notebook spends real money and writes to real Linear / GitHub.** Live cells require all of:

- `HSB_NOTEBOOK_RUN_LIVE=1`
- `HSB_NOTEBOOK_PLAN_MD` -> path to your plan.md
- `HSB_NOTEBOOK_LINEAR_TEAM_ID` -> a sandbox Linear team
- `CLAUDE_CODE_OAUTH_TOKEN` set; `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` UNSET

Setup + Phase 0 always run (markdown / runtime probes / env inventory). Phases 1+ skip with a `gated(...)` banner if any required var is missing. Phase 6+ additionally refuse to run unless upstream phases ran live in this kernel session — restart the kernel to reset."""
        ),
    ),
    (
        "code",
        "setup",
        code(
            """\
import asyncio
import json
import os
import subprocess
from pathlib import Path

from _helpers import (
    assert_g1_safe,
    ensure_src_on_path,
    gated,
    live_mode,
    runtime_summary,
    selected_runtime,
)

ROOT = ensure_src_on_path()
assert_g1_safe()

# Kernel-session state — populated by live cells, asserted by Phase 6+. Reset
# by restarting the kernel.
_session = {
    "phase_2_ran": False,
    "phase_6_ran": False,
    "phase_8_ran": False,
    "epic_id": None,
    "story_ids": [],
    "task_ids": [],
    "dispatched_task_ids": [],
}

print("HSBTech end-to-end story notebook ready")
print()
print("Runtime selection (HSB_RUNTIME_<AGENT>):")
print(runtime_summary())"""
        ),
    ),
    (
        "markdown",
        "env-md",
        md(
            """\
## Environment inventory

For each required var, this cell prints `set` / `unset`. Live cells skip on missing vars."""
        ),
    ),
    (
        "code",
        "env-inventory",
        code(
            """\
required = {
    "HSB_NOTEBOOK_RUN_LIVE": "master gate — set to 1 to allow live cells",
    "HSB_NOTEBOOK_PLAN_MD": "absolute path to plan.md (Phase 1+)",
    "HSB_NOTEBOOK_LINEAR_TEAM_ID": "sandbox Linear team ID (Phase 2+)",
    "CLAUDE_CODE_OAUTH_TOKEN": "Claude OAuth2 token (G1 — never use ANTHROPIC_API_KEY)",
}
forbidden = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")

for var, purpose in required.items():
    state = "set" if os.environ.get(var) else "UNSET"
    print(f"  {state:>5s}  {var}  ({purpose})")
print()
for var in forbidden:
    state = "SET (G1 violation!)" if var in os.environ else "unset"
    print(f"  {state}  {var}")

print()
print("HSB_NOTEBOOK_RUN_LIVE =", repr(os.environ.get("HSB_NOTEBOOK_RUN_LIVE", "")))
print("live_mode() =", live_mode())"""
        ),
    ),
    (
        "markdown",
        "phase-0-md",
        md(
            """\
## Phase 0 — Architecture map

Three orchestration levels (L0/L1/L2), eleven agents, three execution patterns. Read this once before clicking anything below.

```
+-----------------------+   +-------------------+   +------------------------+
| L0 Main Orchestrator  |   | L1 Global Orch    |   | L2 Work Item Orch      |
| pure Python           |-->| pure Python       |-->| stateful ClaudeSDK     |
| cascade vs parallel   |   | ready + risk sort |   | enrich / build / git / |
| worktree lifecycle    |   | UAT dispatch      |   | qa loop / ingest       |
+-----------------------+   +-------------------+   +------------------------+
                                     |                          |
                                     v                          v
                            +-----------------+         +----------------+
                            | Risk Agent      |         | Builder / Git /|
                            | priority queue  |         | QA / Intel /   |
                            | (pure Python)   |         | UAT (per-tool  |
                            +-----------------+         | allow-lists)   |
                                                        +----------------+
```

| Agent | Level | Pattern | Runtime-flippable |
|-------|-------|---------|-------------------|
| Main Orchestrator | L0 | pure Python | n/a |
| Global Orchestrator | L1 | pure Python | n/a |
| Risk Agent (skills 12+13) | support | pure Python | n/a |
| Risk Agent skill 14 | support | one-shot `query()` | no (haiku-pinned) |
| Work Item Orchestrator | L2 | stateful `ClaudeSDKClient` | **no — Claude only** |
| Backlog Agent | support | one-shot `query()` | yes |
| Builder / Git / QA | support | inline within WIO | follows WIO |
| Intelligence (skills 10+11) | support | inline within WIO | follows WIO |
| UAT Agent | support | one-shot `query()` | default Claude |
| Linear Agent | support | one-shot `query()` w/ MCP | default Claude |

See `README.md` §3 (the 11 agents) and `README.md` §4 (guardrails G1–G10) for authoritative detail."""
        ),
    ),
```

### 1.2 Phases 1–6

- [ ] **Step 1.2: Append the Phase 1–6 cell tuples after Phase 0's markdown.**

Phase 1 (plan input — read-only):

```python
    (
        "markdown",
        "phase-1-md",
        md(
            """\
## Phase 1 — Plan input (read-only)

Resolves `HSB_NOTEBOOK_PLAN_MD` and prints the plan so you confirm what you are about to feed into the Backlog Agent. No SDK calls, no Linear writes.

CLI equivalent (you would not normally run this directly — it is wrapped by the Backlog Agent): n/a (file inspection only)."""
        ),
    ),
    (
        "code",
        "phase-1",
        code(
            """\
plan_path_str = os.environ.get("HSB_NOTEBOOK_PLAN_MD", "")
if not plan_path_str:
    print(gated("Phase 1 — set HSB_NOTEBOOK_PLAN_MD to your plan.md path"))
else:
    plan_path = Path(plan_path_str).expanduser().resolve()
    if not plan_path.is_file():
        print(f"plan.md not found at {plan_path}")
    else:
        text = plan_path.read_text()
        lines = text.splitlines()
        print(f"plan: {plan_path}  ({len(lines)} lines, {len(text)} chars)")
        print()
        print("--- head (first 20 lines) ---")
        print("\\n".join(lines[:20]))
        print()
        print("--- tail (last 10 lines) ---")
        print("\\n".join(lines[-10:]))

from hsb.contracts.backlog import BacklogInput, ProjectContext
print()
print("BacklogInput schema:")
print(json.dumps(BacklogInput.model_json_schema(), indent=2)[:800], "...")"""
        ),
    ),
```

Phase 2 (Backlog → Linear, live):

```python
    (
        "markdown",
        "phase-2-md",
        md(
            """\
## Phase 2 — Backlog Agent decomposes plan -> Linear (live)

Runs Backlog Agent on your plan. **This makes real Linear writes** — an EPIC issue, User Story sub-issues under it, Task sub-issues under each Story, with parent linkage and traceability metadata.

Idempotent (BKPK-05): re-running this cell on the same plan creates **0** new EPICs.

Active guardrails: G1 (OAuth-only), Backlog allow-list (4 tools — `create_issue`, `list_issues`, `get_issue`, `Read`). G5 `linear_write_guard` is scoped to callers from `risk_agent.py` and does not affect Backlog.

CLI equivalent: `hsb backlog plan --plan <path>`"""
        ),
    ),
    (
        "code",
        "phase-2",
        code(
            """\
plan_path_str = os.environ.get("HSB_NOTEBOOK_PLAN_MD", "")
team_id = os.environ.get("HSB_NOTEBOOK_LINEAR_TEAM_ID", "")
if not (live_mode() and plan_path_str and team_id):
    print(gated("Phase 2 — set HSB_NOTEBOOK_RUN_LIVE=1, HSB_NOTEBOOK_PLAN_MD, HSB_NOTEBOOK_LINEAR_TEAM_ID"))
else:
    assert_g1_safe()
    from hsb.agents.backlog_agent import run_backlog_agent
    from hsb.contracts.backlog import BacklogInput, ProjectContext

    plan_path = Path(plan_path_str).expanduser().resolve()
    project_ctx = ProjectContext(
        name="HSBTech-pipeline-story-run",
        repository="https://github.com/hugo-hsbtech/hsb-test-fixture",
        technical_stack=["python", "fastapi"],
    )
    backlog_input = BacklogInput(
        plan_source=str(plan_path),
        project_context=project_ctx,
    )
    print(f"runtime backlog -> {selected_runtime('backlog')}")
    print(f"calling Backlog Agent on {plan_path} ...")
    output = run_backlog_agent(backlog_input)

    epics = output.epics
    epic_titles = [e.title for e in epics]
    story_count = sum(len(e.user_stories) for e in epics)
    task_count = sum(
        len(e.tasks) + sum(len(s.tasks) for s in e.user_stories) for e in epics
    )
    print(f"Backlog produced {len(epics)} EPIC(s), {story_count} Story(ies), {task_count} Task(s)")
    for e in epics:
        print(f"  [EPIC] {e.title}")
        for s in e.user_stories:
            print(f"    [Story] {s.title}  (tasks: {len(s.tasks)})")
            for t in s.tasks:
                print(f"      [Task] {t.title}")

    _session["phase_2_ran"] = True
    print()
    print("Phase 2 complete. Now look at the Linear UI to confirm the issues landed.")"""
        ),
    ),
```

Phase 3 (Linear inspection — live, read-only):

```python
    (
        "markdown",
        "phase-3-md",
        md(
            """\
## Phase 3 — Inspect Linear (live, read-only)

Reads back through `run_validated_linear_agent(operation="read", ...)` to confirm what landed on the board. CLI equivalent: `hsb show-state`."""
        ),
    ),
    (
        "code",
        "phase-3",
        code(
            """\
team_id = os.environ.get("HSB_NOTEBOOK_LINEAR_TEAM_ID", "")
if not (live_mode() and team_id):
    print(gated("Phase 3 — set HSB_NOTEBOOK_RUN_LIVE=1 and HSB_NOTEBOOK_LINEAR_TEAM_ID"))
else:
    assert_g1_safe()
    from hsb.agents.linear_agent import run_validated_linear_agent

    print(f"reading Linear team {team_id} ...")
    result = asyncio.run(
        run_validated_linear_agent(
            operation="read",
            payload={"teamId": team_id, "limit": 50},
        )
    )
    entities = result.linear_entities or []
    print(f"found {len(entities)} entit(y/ies)")
    for ent in entities[:30]:
        if isinstance(ent, dict):
            print(f"  {ent.get('id', '?')}  {ent.get('status', '?'):<10s}  {ent.get('title', '')[:80]}")
        else:
            print(f"  {getattr(ent, 'id', '?')}  {getattr(ent, 'status', '?'):<10s}  {getattr(ent, 'title', '')[:80]}")"""
        ),
    ),
```

Phase 4 (Global Orch ready queue — live, pure-Python):

```python
    (
        "markdown",
        "phase-4-md",
        md(
            """\
## Phase 4 — Global Orchestrator -> ready queue (live, pure Python, no LLM cost)

L1 deterministic. Filters by status=todo and no blocking deps."""
        ),
    ),
    (
        "code",
        "phase-4",
        code(
            """\
if not live_mode():
    print(gated("Phase 4 — set HSB_NOTEBOOK_RUN_LIVE=1"))
else:
    assert_g1_safe()
    from hsb.agents.global_orchestrator import GlobalOrchestrator

    go = GlobalOrchestrator()
    output = asyncio.run(go.get_ready_tasks())
    ready = output.ready_tasks
    print(f"ready tasks: {len(ready)}")
    for t in ready[:20]:
        title = getattr(t, "title", "")[:80]
        print(f"  {t.id:<14s}  {title}")"""
        ),
    ),
```

Phase 5 (Risk priority sort — live, pure-Python):

```python
    (
        "markdown",
        "phase-5-md",
        md(
            """\
## Phase 5 — Risk Agent priority sort (live, pure Python)

`global_orchestrator.py:128` calls `RiskAgent().get_priority_queue(...)` between "ready" and "dispatched". Quality score: start=100, -10/QA failure, -5/fix subtask, -15 if UAT failed, -5/rework cycle, min=0. Deterministic — RISK-01 hypothesis-tested."""
        ),
    ),
    (
        "code",
        "phase-5",
        code(
            """\
if not live_mode():
    print(gated("Phase 5 — set HSB_NOTEBOOK_RUN_LIVE=1"))
else:
    assert_g1_safe()
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    from hsb.agents.risk_agent import RiskAgent

    go = GlobalOrchestrator()
    ready_output = asyncio.run(go.get_ready_tasks())
    raw_ids = [t.id for t in ready_output.ready_tasks]
    if not raw_ids:
        print("no ready tasks — Phase 4 found nothing to prioritize")
    else:
        risk = RiskAgent()
        # Linear state is required by get_priority_queue; pull a snapshot.
        from hsb.agents.linear_agent import run_validated_linear_agent
        team_id = os.environ.get("HSB_NOTEBOOK_LINEAR_TEAM_ID", "")
        snapshot = asyncio.run(
            run_validated_linear_agent(
                operation="read",
                payload={"teamId": team_id, "limit": 100},
            )
        )
        priority_queue = risk.get_priority_queue(raw_ids, snapshot.linear_entities)
        print("priority order:")
        for i, item in enumerate(priority_queue.items, start=1):
            print(f"  {i:>2d}.  {item}")"""
        ),
    ),
```

Phase 6 (Main Orch parallel dispatch — live, expensive):

```python
    (
        "markdown",
        "phase-6-md",
        md(
            """\
## Phase 6 — Main Orchestrator dispatch, one cycle, parallel (live, expensive)

The big one. `await run_main_orchestrator(mode="parallel")` — multiple WIO sessions concurrently in `.worktrees/<task-slug>` git worktrees, real `gh pr create` against `epic/LIN-...`, real Builder/Git/QA cycles (cap 3), real Knowledge Store reads + writes.

Active guardrails: G2 (no Agent tool), G3 (`assert_no_task_dispatch` in every WIO receive loop), G7 (`error_max_turns` raises), G8 (120K token warn), G9 (Knowledge ingest validation), MORD-03 (no double-claim), T-4-04 (5-key env allowlist on subprocess).

WIO Codex hard-block re-asserted: this cell will fail loud if `HSB_RUNTIME_WIO=codex` is set.

Expect a few minutes wall-clock and several hundred KB of stdout."""
        ),
    ),
    (
        "code",
        "phase-6",
        code(
            """\
if not live_mode():
    print(gated("Phase 6 — set HSB_NOTEBOOK_RUN_LIVE=1"))
elif not _session["phase_2_ran"]:
    print("Phase 6 refused: Phase 2 has not run live in this kernel session.")
    print("Run Phase 2 first — you cannot dispatch against a board you haven't built.")
else:
    assert_g1_safe()
    if selected_runtime("wio") == "codex":
        raise RuntimeError(
            "WIO is hard-blocked from Codex. Unset HSB_RUNTIME_WIO=codex."
        )
    from hsb.agents.main_orchestrator import run_main_orchestrator

    print("dispatching one outer cycle in parallel mode ...")
    output = asyncio.run(run_main_orchestrator(mode="parallel"))
    print()
    print(f"mode: {output.mode}")
    print(f"dispatched: {len(output.dispatched)}")
    for d in output.dispatched:
        print(f"  {d.work_item_id}  claim={d.claim_status:<7s}  final={d.final_status}")
    print()
    print(f"cycle_summary: {output.cycle_summary}")

    _session["phase_6_ran"] = True
    _session["dispatched_task_ids"] = [d.work_item_id for d in output.dispatched]"""
        ),
    ),
```

### 1.3 Phases 7–12

- [ ] **Step 1.3: Append Phase 7–12 cell tuples, then close the list with `]`.**

Phase 7 (inspect one WIO — live, read-only):

```python
    (
        "markdown",
        "phase-7-md",
        md(
            """\
## Phase 7 — Inspect what one WIO did (live, read-only)

Pick one of the dispatched task IDs from Phase 6, render its Linear comments + GitHub PR + commit graph. Verify stacked-PR shape — task PR base must be `epic/LIN-...`, never `main`."""
        ),
    ),
    (
        "code",
        "phase-7",
        code(
            """\
if not (live_mode() and _session["phase_6_ran"]):
    print(gated("Phase 7 — Phase 6 must have run live first"))
elif not _session["dispatched_task_ids"]:
    print("Phase 7: nothing dispatched in Phase 6 — nothing to inspect")
else:
    assert_g1_safe()
    from hsb.agents.linear_agent import run_validated_linear_agent

    task_id = _session["dispatched_task_ids"][0]
    print(f"inspecting {task_id} ...")
    issue = asyncio.run(
        run_validated_linear_agent(
            operation="read",
            payload={"issueId": task_id},
        )
    )
    for ent in issue.linear_entities or []:
        if isinstance(ent, dict):
            print(f"  status: {ent.get('status')}")
            print(f"  PR url: {ent.get('pr_url') or ent.get('prUrl')}")

    pr_url = None
    for ent in issue.linear_entities or []:
        if isinstance(ent, dict):
            pr_url = ent.get("pr_url") or ent.get("prUrl")
            break
    if pr_url:
        print()
        print(f"--- gh pr view {pr_url} ---")
        result = subprocess.run(
            ["gh", "pr", "view", pr_url],
            capture_output=True, text=True, check=False,
        )
        print(result.stdout[:2000])
        print()
        print("Verify above: 'base' must be epic/LIN-... not main")"""
        ),
    ),
```

Phase 8 (drive next cycle — live):

```python
    (
        "markdown",
        "phase-8-md",
        md(
            """\
## Phase 8 — Drive the next cycle (live)

Re-runs `run_main_orchestrator(mode="parallel")`. As Stories accumulate enough QA-approved tasks, Global Orchestrator's `_detect_uat_ready_user_stories` fires and dispatches UAT inline. Click this cell once per outer cycle you want to run."""
        ),
    ),
    (
        "code",
        "phase-8",
        code(
            """\
if not (live_mode() and _session["phase_6_ran"]):
    print(gated("Phase 8 — Phase 6 must have run live first"))
else:
    assert_g1_safe()
    from hsb.agents.main_orchestrator import run_main_orchestrator

    output = asyncio.run(run_main_orchestrator(mode="parallel"))
    print(f"cycle: dispatched {len(output.dispatched)}, mode={output.mode}")
    for d in output.dispatched:
        print(f"  {d.work_item_id}  claim={d.claim_status:<7s}  final={d.final_status}")
    print(f"summary: {output.cycle_summary}")

    _session["phase_8_ran"] = True
    _session["dispatched_task_ids"] = [d.work_item_id for d in output.dispatched]"""
        ),
    ),
```

Phase 9 (UAT outcome / round-trip — live, read-only):

```python
    (
        "markdown",
        "phase-9-md",
        md(
            """\
## Phase 9 — UAT outcome and the round-trip (live, read-only)

UAT runs at User Story level when all child Tasks are QA-approved. Two paths:

- **approved** -> Story `uat_approved`, Story-level done
- **changes_required** -> fix subtasks created in Linear -> become new ready tasks -> next Phase 8 click picks them up

This is the round-trip. G6 caps UAT cycles at 3 with escalation. G10 enforces B1 coverage + B3 banned-token regex pre-persist."""
        ),
    ),
    (
        "code",
        "phase-9",
        code(
            """\
if not (live_mode() and _session["phase_8_ran"]):
    print(gated("Phase 9 — Phase 8 must have run live first"))
else:
    assert_g1_safe()
    from hsb.agents.linear_agent import run_validated_linear_agent

    team_id = os.environ.get("HSB_NOTEBOOK_LINEAR_TEAM_ID", "")
    snapshot = asyncio.run(
        run_validated_linear_agent(
            operation="read",
            payload={"teamId": team_id, "limit": 100},
        )
    )
    fix_subtasks = []
    uat_results = []
    for ent in snapshot.linear_entities or []:
        if not isinstance(ent, dict):
            continue
        title = ent.get("title", "")
        if "[FIX]" in title or "fix:" in title.lower():
            fix_subtasks.append(ent)
        if "uat" in (ent.get("type", "") or "").lower():
            uat_results.append(ent)

    print(f"fix subtasks present on board: {len(fix_subtasks)}")
    for s in fix_subtasks[:10]:
        print(f"  {s.get('id')}  {s.get('status'):<10s}  {s.get('title', '')[:80]}")
    print()
    if fix_subtasks:
        print("Round-trip detected: re-run Phase 8 to dispatch the fix subtasks.")
    else:
        print("No fix subtasks — UAT either passed or has not run yet.")"""
        ),
    ),
```

Phase 10 (until done — markdown + read-only inspection):

```python
    (
        "markdown",
        "phase-10-md",
        md(
            """\
## Phase 10 — Until done

Re-run Phase 8 as many times as you want. The notebook intentionally does **not** auto-iterate — each click of Phase 8 = one outer cycle. When `GlobalOrchestrator.get_ready_tasks()` returns empty, advance to the read-only cell below.

If you click this cell while ready tasks remain, it prints the still-ready queue and points you back to Phase 8. The system never merges to `main` — every EPIC PR merge is human-approved (no `gh pr merge` in any allow-list)."""
        ),
    ),
    (
        "code",
        "phase-10",
        code(
            """\
if not live_mode():
    print(gated("Phase 10 — set HSB_NOTEBOOK_RUN_LIVE=1"))
else:
    assert_g1_safe()
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    from hsb.agents.linear_agent import run_validated_linear_agent

    go = GlobalOrchestrator()
    ready = asyncio.run(go.get_ready_tasks()).ready_tasks
    if ready:
        print(f"still {len(ready)} ready task(s) — go back to Phase 8")
        for t in ready[:20]:
            print(f"  {t.id}  {getattr(t, 'title', '')[:80]}")
    else:
        team_id = os.environ.get("HSB_NOTEBOOK_LINEAR_TEAM_ID", "")
        snapshot = asyncio.run(
            run_validated_linear_agent(
                operation="read",
                payload={"teamId": team_id, "limit": 100},
            )
        )
        print("no ready tasks — done.")
        print()
        print("Final board state:")
        for ent in snapshot.linear_entities or []:
            if isinstance(ent, dict):
                print(f"  {ent.get('id'):<14s}  {ent.get('status'):<10s}  {ent.get('title', '')[:80]}")
        print()
        print("EPIC integration branch awaits human merge — system never merges to main.")"""
        ),
    ),
```

Phase 11a (Knowledge Store delta — live, read-only):

```python
    (
        "markdown",
        "phase-11a-md",
        md(
            """\
## Phase 11a — Knowledge Store grew (live, read-only)

Lists `knowledge/{architecture,qa,implementation,backlog,risk}/` and renders new entries. G9 `KnowledgeStorageInput.applicability` validator rejects "all tasks" / "n/a" / "tbd" / empty — confirm the rendered `applicability` field is concrete."""
        ),
    ),
    (
        "code",
        "phase-11a",
        code(
            """\
knowledge_root = ROOT / "knowledge"
if not knowledge_root.is_dir():
    print(f"no knowledge/ dir at {knowledge_root}")
else:
    print(f"knowledge/ at {knowledge_root}")
    for sub in sorted(knowledge_root.iterdir()):
        if sub.is_dir():
            entries = sorted(sub.glob("*.md"))
            print(f"  {sub.name}/  ({len(entries)} entr{'y' if len(entries) == 1 else 'ies'})")
            for entry in entries[:5]:
                head = entry.read_text().splitlines()[:8]
                applicability = next(
                    (line for line in head if line.lower().startswith("applicability")),
                    "(applicability: line not in head)",
                )
                print(f"    {entry.name}  -- {applicability}")"""
        ),
    ),
```

Phase 11b (Risk Agent skill 14 — live, ~$0.05):

```python
    (
        "markdown",
        "phase-11b-md",
        md(
            """\
## Phase 11b — Auto-improvement triggers (live, ~$0.05)

Risk Agent skill 14 — air-gapped haiku call. `allowed_tools=[]`, `mcp_servers=None`, `model=haiku`, `max_turns=3`, `max_budget_usd=0.05`. G4 4-layer RISK-04 defense in action."""
        ),
    ),
    (
        "code",
        "phase-11b",
        code(
            """\
if not live_mode():
    print(gated("Phase 11b — set HSB_NOTEBOOK_RUN_LIVE=1"))
else:
    assert_g1_safe()
    from hsb.agents.risk_agent import RiskAgent

    risk = RiskAgent()
    print("calling RiskAgent.detect_improvement_triggers() ...")
    triggers = asyncio.run(risk.detect_improvement_triggers())
    if not triggers:
        print("no auto-improvement triggers detected this run")
    else:
        for t in triggers:
            print(f"  - {t}")"""
        ),
    ),
```

Phase 12 (pointers — markdown only):

```python
    (
        "markdown",
        "phase-12-md",
        md(
            """\
## Phase 12 — Pointers

Where to go next:

| Resource | Use for |
|----------|---------|
| `notebooks/00_guardrails_audit.ipynb` | G1/G2/G3/G4/G9/RISK-04 invariant proofs |
| `notebooks/01_contracts_playground.ipynb` | Pydantic boundary fuzzing |
| `notebooks/02_risk_and_global_pure_logic.ipynb` | Risk score formula + ready-task filter |
| `notebooks/03_main_orchestrator_dispatch.ipynb` | Cascade vs parallel internals |
| `notebooks/04_linear_and_knowledge_readonly.ipynb` | Linear MCP + Knowledge probes |
| `notebooks/05_per_agent_smoke.ipynb` | Per-agent smoke on minimal fixtures |
| `notebooks/06_wio_full_loop.ipynb` | One WIO end-to-end |
| `README.md` §3 | The 11 agents |
| `README.md` §4 | Guardrails G1-G10 |
| `GET-STARTED.md` | Operator onboarding (~30 min) |
| `.planning/MILESTONE-UAT.md` | 24-step acceptance run |
| `hsb show-state` | Always-safe board peek |
| `hsb show-next-action` | Dry-run next decision |
| `python run_loop.py` | Repo-root continuous loop (CLIR-04) |"""
        ),
    ),
]
```

- [ ] **Step 1.4: Register `NB_07` in `main()`'s `targets` dict.**

Find the `targets = { ... }` dict in `main()` and add `"07_full_pipeline_story.ipynb": NB_07,` after the line for `06_wio_full_loop.ipynb`.

```python
    targets = {
        "00_guardrails_audit.ipynb": NB_00,
        "01_contracts_playground.ipynb": NB_01,
        "02_risk_and_global_pure_logic.ipynb": NB_02,
        "03_main_orchestrator_dispatch.ipynb": NB_03,
        "04_linear_and_knowledge_readonly.ipynb": NB_04,
        "05_per_agent_smoke.ipynb": NB_05,
        "06_wio_full_loop.ipynb": NB_06,
        "07_full_pipeline_story.ipynb": NB_07,
    }
```

- [ ] **Step 1.5: Run the build script to materialize the notebook.**

```bash
uv run python notebooks/_build_notebooks.py
```

Expected output:

```
wrote notebooks/00_guardrails_audit.ipynb  (...)
...
wrote notebooks/07_full_pipeline_story.ipynb  (~40 cells)
```

The other six notebooks should produce byte-identical output (their specs unchanged).

- [ ] **Step 1.6: Verify the new notebook exists and has cells.**

```bash
test -f notebooks/07_full_pipeline_story.ipynb && python -c "import json; d=json.load(open('notebooks/07_full_pipeline_story.ipynb')); print('cells:', len(d['cells']))"
```

Expected: prints `cells: ` followed by a number ~38–42.

---

## Task 2: Update `notebooks/README.md`

**Files:**
- Modify: `notebooks/README.md` (Tiers table)

- [ ] **Step 2.1: Add row 07 to the Tiers table.**

Find the Tiers table (line 12-21 of `notebooks/README.md`) and append this row after the `06_wio_full_loop.ipynb` row:

```markdown
| `07_full_pipeline_story.ipynb` | Full pipeline end-to-end: plan -> Backlog -> Linear -> Global+Risk -> Main parallel -> WIOs -> UAT round-trip -> Knowledge -> skill 14 | Variable, gated per-phase | Yes — gated on `HSB_NOTEBOOK_RUN_LIVE=1` plus per-phase env vars |
```

- [ ] **Step 2.2: Update the "Notebooks 04–06 read environment flags ..." paragraph to say "Notebooks 04–07".**

Find this line:

```markdown
Notebooks 04–06 read environment flags before doing anything that costs tokens
```

Replace with:

```markdown
Notebooks 04–07 read environment flags before doing anything that costs tokens
```

- [ ] **Step 2.3: Add `HSB_NOTEBOOK_PLAN_MD` row to the Environment table for Phase 1+ (already exists for notebook 05; just append 07 to the Notebook column).**

Find the row for `HSB_NOTEBOOK_PLAN_MD` in the Environment table:

```markdown
| `HSB_NOTEBOOK_PLAN_MD` | 05 | Path to a plan.md to drive a Backlog Agent live run |
```

Replace with:

```markdown
| `HSB_NOTEBOOK_PLAN_MD` | 05, 07 | Path to a plan.md to drive Backlog (Phase 2 of nb 07 / nb 05) |
```

Also update `HSB_NOTEBOOK_LINEAR_TEAM_ID` row:

```markdown
| `HSB_NOTEBOOK_LINEAR_TEAM_ID` | 04, 05 | Sandbox Linear team ID for read probes |
```

Becomes:

```markdown
| `HSB_NOTEBOOK_LINEAR_TEAM_ID` | 04, 05, 07 | Sandbox Linear team ID (read probes / nb 07 dispatch target) |
```

And update `HSB_NOTEBOOK_RUN_LIVE`:

```markdown
| `HSB_NOTEBOOK_RUN_LIVE` | 04, 05, 06 | Set to `1` to actually call SDK / Linear MCP |
```

Becomes:

```markdown
| `HSB_NOTEBOOK_RUN_LIVE` | 04, 05, 06, 07 | Set to `1` to actually call SDK / Linear MCP |
```

---

## Task 3: Smoke-test the new notebook

**Files:**
- Read: `notebooks/07_full_pipeline_story.ipynb`

The notebook must execute top-to-bottom in a fresh kernel **without** `HSB_NOTEBOOK_RUN_LIVE=1`. Every live cell should print a `gated(...)` banner and continue. This validates imports, syntax, and Python errors in the cell sources.

- [ ] **Step 3.1: Run nbconvert against the new notebook.**

```bash
unset HSB_NOTEBOOK_RUN_LIVE HSB_NOTEBOOK_PLAN_MD HSB_NOTEBOOK_LINEAR_TEAM_ID HSB_NOTEBOOK_WIO_TASK_ID
uv run jupyter nbconvert --to notebook --execute notebooks/07_full_pipeline_story.ipynb --output /tmp/07-executed.ipynb 2>&1 | tail -20
```

Expected: exit code 0, no `CellExecutionError` traceback, file `/tmp/07-executed.ipynb` present.

- [ ] **Step 3.2: If the smoke test fails, iterate on `_build_notebooks.py` and rerun the build + smoke test until green.**

Common failure modes:
- Import errors (missing module / wrong attribute name)
- Pydantic field-name mismatch (e.g., `applicability` vs `applicabilty`)
- F-string with double-quote inside (escape with single-quote outer)
- Bare `await` outside an async function (must be wrapped in `asyncio.run(...)`)

---

## Task 4: Commit, push, open PR

- [ ] **Step 4.1: Confirm working tree is clean except for the new files.**

```bash
git status -s
```

Expected: only `M  notebooks/_build_notebooks.py`, `M  notebooks/README.md`, `??  notebooks/07_full_pipeline_story.ipynb`.

- [ ] **Step 4.2: Stage and commit.**

```bash
git add notebooks/_build_notebooks.py notebooks/README.md notebooks/07_full_pipeline_story.ipynb
git commit -m "$(cat <<'EOF'
feat(notebooks): add 07 — full pipeline story end-to-end

Live, operator-paced walkthrough: plan.md -> Backlog -> Linear ->
Global+Risk -> Main parallel -> N x WIO -> UAT -> fix-subtask
round-trip -> Knowledge Store -> Risk skill 14 auto-improvement
triggers. Real Linear writes, real GitHub PRs, real SDK calls.

Gating: HSB_NOTEBOOK_RUN_LIVE=1 + per-phase env vars + kernel-session
state dict that prevents skipping markdown to expensive cells.

Spec: docs/superpowers/specs/2026-05-09-pipeline-story-notebook-design.md
Plan: docs/superpowers/plans/2026-05-09-pipeline-story-notebook.md
EOF
)"
```

- [ ] **Step 4.3: Push the current branch to origin.**

```bash
git push -u origin HEAD
```

- [ ] **Step 4.4: Open PR with no description.**

```bash
gh pr create --title "feat(notebooks): add 07 — full pipeline story end-to-end" --body ""
```

Capture the URL and report it back.

---

## Self-review pass

This plan covers each section of the spec:
- §1 Goal -> Task 1 (notebook content) + Task 2 (README row)
- §2 Non-goals -> Task 1 enforces (no fixtures, no auto-iteration in Phase 10)
- §4 Scope (in scope) -> Task 1, Task 2
- §5 Notebook structure 13 sections -> Task 1.1 (Setup + Phase 0) + 1.2 (1–6) + 1.3 (7–12)
- §6 Per-phase contract (markdown header + pre-flight + live cell, optional inspection) -> followed by every phase's cells in Task 1
- §7 Gating discipline -> `_session` dict + `assert_g1_safe()` + `live_mode()` + per-phase env-var checks; Phase 6+ asserts `_session["phase_2_ran"]`
- §8 Implementation approach (build via `_build_notebooks.py`, register in `targets`) -> Task 1.4, 1.5
- §9 Testing approach (nbconvert smoke test, no `tests/` changes) -> Task 3
- §10 Risks named with mitigations -> baked into the cell sources (R1 lets exceptions surface; R2 banner; R3 cost note in Phase 6 markdown; R4 explicit RuntimeError in Phase 6)
- §11 Acceptance criteria for the spec -> reviewed; this plan implements them
