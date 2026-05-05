# Phase 3: Work Item Orchestrator and Single-Cycle MVP - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers one complete controlled cycle: a single Task moving from `todo` to `done` through the full lifecycle — Linear read → Builder → Git → QA → fix loop — via a CLI trigger. This is the MVP gate.

- **Work Item Orchestrator**: A single Claude Agent SDK session that embeds all lifecycle skill content inline and drives one task through its full lifecycle using sequential tool use within one context window. No sub-subagent dispatch.
- **CLI runtime**: Typer extensions (`hsb run-next-step`, `hsb show-state`, `hsb show-next-action`) plus a `run_loop.py` wrapper. Cascade mode only — one work item at a time.
- **MVP validation**: One successful end-to-end cycle (real Linear task, real hsb-test-fixture repo) proves the architecture and validates the context budget simultaneously.

No Global Orchestrator, no parallel dispatch, no Intelligence Agent. Those are Phase 4+ scope.

</domain>

<decisions>
## Implementation Decisions

### Work Item Orchestrator Architecture

- **D-01:** The Work Item Orchestrator is implemented as a **single Claude Agent SDK session**. At startup, Python reads all relevant skill files (`06-TASK-ORCHESTRATION`, `02-IMPLEMENTATION`, `03-QA-REVIEW`, `04-GIT-PR-MANAGEMENT`, `05-LINEAR-SYSTEM-OF-RECORD`) and injects their content into the system prompt. The agent then drives the full lifecycle via sequential tool use within that one context window. No sub-agent spawning, no sub-subagent dispatch (WORC-02).
- **D-02:** Context budget validation is NOT a separate pre-flight step. The MVP benchmark cycle (a real Linear task against the hsb-test-fixture repo) IS the context validation. If the full cycle completes without hitting context limits, the architecture is validated. If not, that's the signal to trim skill content before Phase 4.

### Lifecycle Sequence

- **D-03:** Phase 3 lifecycle is: **Linear read → Builder → Git → QA → fix loop → done**. The Intelligence step (from `skills/10-KNOWLEDGE-CONTEXT-ENRICHMENT.md`) is **skipped entirely** in Phase 3. No stub, no placeholder. Phase 5 inserts Intelligence before Builder when it ships. This keeps Phase 3 minimal and avoids stub code Phase 5 must remove.

### QA Fix Loop Behavior

- **D-04:** When QA returns `changes_required`, the orchestrator **exits after creating fix subtasks**. Linear state is updated (`qa_status = changes_required`, task status signals blocked). The human re-triggers with `hsb run-next-step`. On the next trigger, the orchestrator reads the fix subtasks from Linear, passes them to Builder as the new scope, and loops: Builder → Git → QA again. Each fix cycle is its own orchestration cycle.
- **D-05:** QA cycle cap enforcement is **layered**:
  - Layer 1 (QA Agent — Phase 2 D-05): At `qa_cycle_count >= 3`, QA Agent approves with tech-debt annotation rather than requesting further fixes. This is the normal termination path.
  - Layer 2 (Work Item Orchestrator — safety net): If `qa_cycle_count >= 3` AND `qa_status` is still `changes_required` (shouldn't happen normally), the orchestrator posts a structured Linear comment ("Max QA cycles reached. Escalating to human. Task status: blocked.") and exits. Never initiates a 4th fix cycle (WORC-03).

### CLI Interface

- **D-06:** Phase 3 CLI commands **extend the existing Typer CLI** at `src/hsb/cli/main.py`. Three new subcommands added:
  - `hsb run-next-step` — trigger one orchestration cycle; a single work item progresses exactly one lifecycle step
  - `hsb show-state` — render a `rich` table: EPIC name, each Task with status, `qa_status`, `qa_cycle_count`, PR link
  - `hsb show-next-action` — display the next recommended action without executing it
- **D-07:** `run_loop.py` is a **thin wrapper script** at the repo root that calls `hsb run-next-step` in a loop. Stops when no `todo`-status tasks remain in Linear (queried directly, without the Global Orchestrator which is Phase 4 scope) or when the operator interrupts with Ctrl+C. Each loop iteration is a standalone `asyncio.run()` invocation — no process-level state (CLIR-05).
- **D-08:** `show-state` output uses `rich` (already in Phase 1 dependencies). Table format: EPIC / Task / Status / QA Status / QA Cycle Count / PR Link.

### Claude's Discretion

- **SKILL.md migration**: The Work Item Orchestrator skill (`skills/06-TASK-ORCHESTRATION.md`) should be migrated to `.claude/skills/task-orchestration/SKILL.md` during Phase 3, following the pattern established in Phases 1 and 2.
- **Skill injection order**: Exact ordering of skill content in the system prompt (e.g., task-orchestration first as the "meta-skill" framing the others, or interleaved by lifecycle step) — Claude decides.
- **`run next step` stopping condition in run_loop.py**: Exact Linear query to detect "no ready tasks" (e.g., filter by `todo` status in the current EPIC's scope) — Claude decides based on what keeps the Linear MCP call minimal.
- **WORC-05 output persistence**: Exact structure of the lifecycle status summary posted as a Linear comment after each cycle — Claude decides, following the output contract in `agents/AGENT-CONTRACTS.md`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Work Item Orchestrator Spec
- `skills/06-TASK-ORCHESTRATION.md` — Work Item Orchestrator behavioral spec; SKILL.md migrated to `.claude/skills/task-orchestration/SKILL.md` during Phase 3
- `runtime/RUNTIME-EXECUTION.md` — runtime execution model; the "one action per Work Item Orchestrator cycle" golden rule is enforced here

### Agent Contracts and Architecture
- `agents/AGENT-CONTRACTS.md` — JSON schemas for all agent contracts; Phase 3 orchestrator output contract is the Work Item Orchestration section (§3 or equivalent)
- `agents/AGENTS.md` — agent responsibilities and capability boundaries

### Phase 2 Skill Specs (Phase 3 orchestrator embeds these)
- `skills/02-IMPLEMENTATION.md` — Builder Agent behavioral spec (embedded inline in orchestrator system prompt)
- `skills/03-QA-REVIEW.md` — QA Agent behavioral spec (embedded inline; cycle cap behavior defined here)
- `skills/04-GIT-PR-MANAGEMENT.md` — Git Agent behavioral spec (embedded inline)
- `skills/05-LINEAR-SYSTEM-OF-RECORD.md` — Linear Agent behavioral spec (embedded inline)

### Phase 1 + 2 Context (Phase 3 depends on these being built)
- `.planning/phases/01-foundation-and-linear-integration/01-CONTEXT.md` — Python layout, pydantic structure, SKILL.md migration pattern, Linear Agent service interface
- `.planning/phases/02-core-execution-agents/02-CONTEXT.md` — Phase 2 decisions: no `gh stack`, integration test strategy, QA cycle cap in QA Agent SKILL.md, hsb-test-fixture repo
- `.planning/research/STACK.md` — exact tool names, library versions, SDK patterns
- `.planning/research/PITFALLS.md` — critical failure modes (especially Pitfall 1: double-claim, Pitfall 2: QA runaway, Pitfall 4: stale state)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `skills/06-TASK-ORCHESTRATION.md`: Work Item Orchestrator behavioral spec — migrate as SKILL.md and use as the primary orchestrator skill in system prompt injection
- `skills/02-IMPLEMENTATION.md`, `skills/03-QA-REVIEW.md`, `skills/04-GIT-PR-MANAGEMENT.md`, `skills/05-LINEAR-SYSTEM-OF-RECORD.md`: All four Phase 2 skill specs are injection-ready — their content forms the bulk of the orchestrator's system prompt
- `src/hsb/cli/main.py` (Phase 1 output): Existing Typer CLI — extend with three new subcommands, not a separate entrypoint
- `src/hsb/agents/linear_agent.py` (Phase 1 output): Linear Agent service — called by the orchestrator for all Linear writes (status updates, comments, cycle summary)

### Established Patterns (from Phases 1 and 2)
- Python package layout: `src/hsb/agents/`, `src/hsb/contracts/`, `src/hsb/cli/` — Phase 3 adds `work_item_orchestrator.py` to `src/hsb/agents/`
- Integration tests use real external services (real Linear test workspace, real `hsb-test-fixture` GitHub repo) — no mocking
- SKILL.md migration pattern: add YAML frontmatter (`name`, `description`, `allowed-tools`) to existing skill content, commit to `.claude/skills/<name>/SKILL.md`

### Integration Points
- Phase 3 orchestrator calls Phase 2 agent Python modules (`builder_agent.py`, `git_agent.py`, `qa_agent.py`) as tool implementations within the single SDK session
- `hsb run-next-step` replaces Phase 1's standalone Linear Agent verification CLI as the primary operator interaction point
- `run_loop.py` at repo root wraps `hsb run-next-step`; Linear query (not Global Orchestrator) determines loop termination

</code_context>

<specifics>
## Specific Ideas

- The single-session orchestrator architecture means all skill content is in one system prompt. If the combined prompt is large, the planner should consider a "skill index" approach (brief summaries with on-demand full reads) — but only if the benchmark run shows context pressure.
- `hsb show-state` renders a `rich` table: EPIC / Task name / Status / QA Status / QA Cycles / PR Link. Five columns, consistent with the Linear state model fields from `skills/06-TASK-ORCHESTRATION.md`.
- The `run_loop.py` `asyncio.run()` per iteration means each trigger is stateless from the process perspective — Linear is the entire state store between iterations (CLIR-05 compliance).
- Branch naming (from Phase 2): `feature/LIN-{id}-{slug}` — orchestrator passes this format to the Git Agent as part of the handoff payload.

</specifics>

<deferred>
## Deferred Ideas

- Global Orchestrator for ready-task detection — Phase 4; Phase 3 uses a direct Linear query in `run_loop.py`
- Parallel mode dispatch — Phase 4 (explicitly gated on validated cascade cycle from Phase 3)
- Intelligence Agent lifecycle step — Phase 5; Phase 3 lifecycle starts at Builder
- `gh stack` integration — not implemented in any phase (Phase 2 D-06, permanently deferred)
- Dry-run / simulation mode — out of scope per REQUIREMENTS.md

</deferred>

---

*Phase: 03-work-item-orchestrator-and-single-cycle-mvp*
*Context gathered: 2026-05-05*
