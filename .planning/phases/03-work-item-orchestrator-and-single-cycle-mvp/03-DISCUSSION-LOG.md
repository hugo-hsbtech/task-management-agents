# Phase 3: Work Item Orchestrator and Single-Cycle MVP - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 03-work-item-orchestrator-and-single-cycle-mvp
**Areas discussed:** Orchestrator architecture, Intelligence stub in Phase 3, QA fix loop behavior, CLI interface shape

---

## Orchestrator Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Single SDK agent session | One Claude Agent SDK session; Python reads all skill files at startup and injects them into system prompt; agent drives full lifecycle via sequential tool use in one context window | ✓ |
| Python orchestrator calling agent modules | A Python function calls each Phase 2 agent Python module sequentially as function calls; each Phase 2 agent has its own SDK session when invoked | |
| Skill injection per step | One SDK session, but inject only the relevant skill at each lifecycle step to minimize context pressure | |

**User's choice:** Single SDK agent session

---

### Orchestrator Architecture — Context Budget Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Benchmark test with real task | Run orchestrator against a real Linear task in hsb-test-fixture, log tokens per turn; successful completion validates the architecture | ✓ |
| Token count estimate pre-flight | Python pre-flight check counts assembled system prompt tokens (tiktoken); rejects if above threshold (e.g., 80K) | |
| Claude's discretion | Let the planner figure out the validation approach | |

**User's choice:** Benchmark test with real task — the MVP cycle IS the context validation

---

## Intelligence Stub in Phase 3

| Option | Description | Selected |
|--------|-------------|----------|
| Skip it — go Builder-first | Phase 3 lifecycle: Linear read → Builder → Git → QA → fix loop. No Intelligence step. Phase 5 inserts Intelligence before Builder when it ships. | ✓ |
| No-op stub in lifecycle | Include an Intelligence step that immediately returns an empty enrichment; Phase 5 replaces the stub | |
| Log-only stub | Include an Intelligence step that logs "Intelligence Agent not yet available — skipping enrichment" and passes raw issue to Builder | |

**User's choice:** Skip it entirely — Builder-first lifecycle in Phase 3

---

## QA Fix Loop Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Exit and wait for re-trigger | After QA creates fix subtasks, orchestrator exits. Human runs `run next step` again. Next cycle reads fix subtasks from Linear, loops: Builder → Git → QA. | ✓ |
| Auto-loop within the same session | Orchestrator does not exit on QA failure; immediately loops back within the same SDK session until QA approves or cycle cap is hit | |

**User's choice:** Exit and wait for re-trigger — each fix cycle is its own orchestration cycle

---

### QA Fix Loop — Escalation at Cycle 3

| Option | Description | Selected |
|--------|-------------|----------|
| Comment on Linear + exit with explicit message | Orchestrator posts structured Linear comment ("Max QA cycles reached. Escalating to human.") and exits when hard limit hit | ✓ |
| QA Agent handles it (already decided) | Phase 2 D-05: QA Agent approves with tech-debt annotation at cycle 3; orchestrator processes as normal approval | |

**User's choice:** Comment on Linear + exit — as a hard-limit safety net layered on top of QA Agent's tech-debt approval (which is the normal path)

**Notes:** The two options are not mutually exclusive. QA Agent approves with tech-debt annotation at cycle 3 (Phase 2 D-05, normal path). The orchestrator's hard-limit check is a safety net: if `qa_cycle_count >= 3` AND still `changes_required` (shouldn't happen normally), post Linear comment + exit.

---

## CLI Interface Shape

### Integration approach

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing Typer CLI | Add orchestrator subcommands to `src/hsb/cli/main.py`; `run_loop.py` is a thin wrapper; one CLI entry point | ✓ |
| Standalone scripts | Separate scripts at repo root: `run_next_step.py`, `show_state.py`, `run_loop.py` | |

**User's choice:** Extend existing Typer CLI — `hsb run-next-step`, `hsb show-state`, `hsb show-next-action`

### `show current state` output format

| Option | Description | Selected |
|--------|-------------|----------|
| Rich table: EPIC → Task status | Formatted table: EPIC name, each Task with status, qa_status, qa_cycle_count, PR link; uses `rich` (already in dependencies) | ✓ |
| Plain text summary | Human-readable text block; no formatting library required | |
| JSON output | Raw JSON of Linear state; pipeable but not human-friendly | |

**User's choice:** Rich table

### `run_loop.py` stopping condition

| Option | Description | Selected |
|--------|-------------|----------|
| No ready tasks remaining | Loop stops when no `todo`-status tasks remain in Linear (or Ctrl+C interrupt) | ✓ |
| Single task reaches done | Loop stops as soon as the first task reaches `done` | |

**User's choice:** No ready tasks remaining — generalizes beyond single-task MVP

---

## Claude's Discretion

- Skill injection order in system prompt (task-orchestration first as meta-skill framer, or interleaved by lifecycle step)
- Exact Linear query in `run_loop.py` to detect "no ready tasks" (minimal MCP call)
- WORC-05 lifecycle status summary structure posted as Linear comment after each cycle

## Deferred Ideas

- Global Orchestrator for ready-task detection — Phase 4
- Parallel mode — Phase 4 (gated on validated cascade cycle from Phase 3)
- Intelligence Agent lifecycle step — Phase 5
- `gh stack` integration — permanently deferred (Phase 2 D-06)
