# Phase 4: Global + Main Orchestrators and Parallel Mode - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 delivers the two orchestrators above the Work Item Orchestrator — completing the three-level hierarchy:

- **Global Orchestrator**: Pure Python service that reads Linear state, filters ready non-blocked tasks, detects empty backlog and EPIC completion, returns a prioritized task list
- **Main Orchestrator**: Pure Python dispatch controller that accepts cascade or parallel mode, calls Global Orchestrator, claims tasks via optimistic lock, and dispatches Work Item Orchestrators
- **Parallel mode**: Each WIO runs in an isolated git worktree (created by Python `git worktree add`), spawned as a subprocess, coordinated via `asyncio.gather()`
- **CLI upgrade**: `hsb run` entry point (cascade default, `--parallel` flag); `hsb run-next-step` retained for single-task debugging

No Intelligence, UAT, or Risk agents. Those are Phase 5.

</domain>

<decisions>
## Implementation Decisions

### Orchestrator Architecture

- **D-01:** Global Orchestrator is a **pure Python class** (`src/hsb/agents/global_orchestrator.py`). No Claude Agent SDK session. Calls Linear Agent service (Phase 1) to fetch work items, applies deterministic filtering and sorting, returns structured output. No LLM involved.
- **D-02:** Main Orchestrator is a **pure Python class** (`src/hsb/agents/main_orchestrator.py`). No Claude Agent SDK session. Handles mode selection, claiming loop, and WIO dispatch. The Work Item Orchestrator (Phase 3) remains the only Agent SDK session in the stack — it is the only component that needs LLM reasoning.
- **D-03:** Global Orchestrator output contract: `{"ready_tasks": [...ordered by priority...], "is_backlog_empty": bool, "is_epic_ready": bool}`. Matches GORD-01 through GORD-04 requirements.

### Parallel Claiming — Optimistic Lock

- **D-04:** Task claiming uses **`status + updatedAt` optimistic locking** via Linear MCP tools (OAuth2 authenticated). No API keys, no custom Linear fields, no raw GraphQL calls. Protocol per MORD-03:
  1. Capture pre-write `updatedAt` timestamp from the work item
  2. Write `status = in_progress` via Linear Agent
  3. Re-read the work item
  4. Verify `updatedAt` changed (our write landed) and `assigned_orchestrator`-equivalent state is consistent
  5. If verification fails (concurrent write detected) → skip this task, move to next
- **D-05:** Claiming happens **sequentially** in the Main Orchestrator claiming loop (one claim at a time) before parallel dispatch begins. The parallel part is dispatch, not claiming. This eliminates the inter-claim race window described in Pitfall 1 for single-process runs.
- **D-06:** A configurable delay between claims (default: 200ms) is added to the claiming loop to further reduce collision risk if two `hsb run --parallel` processes are ever started simultaneously.

### Worktree Isolation

- **D-07:** In parallel mode, the Main Orchestrator runs **`git worktree add .worktrees/LIN-{id} feature/LIN-{id}-{slug}`** for each claimed task before dispatch (MORD-04). Worktrees are created in `.worktrees/` at the repo root.
- **D-08:** Each WIO is spawned as a **Python subprocess** — a separate process running the WIO Agent SDK session in its assigned worktree. Main Orchestrator uses `asyncio.gather()` to coordinate all subprocesses and collect their results.
- **D-09:** Worktrees are cleaned up after each WIO subprocess completes (`git worktree remove .worktrees/LIN-{id}`). Cleanup runs regardless of WIO success or failure to prevent worktree accumulation.

### CLI Design

- **D-10:** `hsb run` is the new Phase 4 entry point. Added to `src/hsb/cli/main.py` as a new Typer subcommand alongside existing commands. Default mode is **cascade**. Parallel mode requires explicit `--parallel` flag. Parallel never activates by accident.
- **D-11:** `hsb run-next-step` (Phase 3) is **retained unchanged** as the single-task debug path. It bypasses Global Orchestrator and goes directly to one WIO cycle — useful for testing individual tasks and validating WIO behavior without the full hierarchy.
- **D-12:** `run_loop.py` (Phase 3 thin wrapper at repo root) is updated to call `hsb run` instead of `hsb run-next-step`. Loop termination remains: stop when no `ready_tasks` returned by Global Orchestrator.
- **D-13:** `hsb run --parallel` requires the Phase 3 MVP cascade cycle to have been validated first (gated per STATE.md note). The planner should add a runtime guard or documentation note reinforcing this sequencing.

### Cycle Summary Persistence

- **D-14:** After all dispatched orchestrators complete, Main Orchestrator calls Linear Agent to post a structured cycle summary comment on the EPIC (MORD-05). Format follows the output contract in `agents/AGENT-CONTRACTS.md`.

### Claude's Discretion

- **SKILL.md migration**: `skills/07-GLOBAL-ORCHESTRATION.md` and `skills/00-MAIN-ORCHESTRATOR.md` should be migrated to `.claude/skills/` during Phase 4 for consistency, even though these are pure Python (the skills serve as human-readable spec reference).
- **Worktree path strategy**: Whether `.worktrees/` is gitignored or tracked — Claude decides. Likely gitignored to avoid committing temporary worktree metadata.
- **Subprocess WIO interface**: Exact mechanism for passing WIO inputs to the subprocess (env vars, JSON file, stdin) and collecting outputs — Claude decides based on what keeps the contract clean with the existing pydantic schemas.
- **Global Orchestrator priority ordering**: Exact sort key for the ready-task list (Linear priority field, creation date, or dependency depth) — Claude decides based on what the Linear MCP tools expose.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Orchestrator Skill Specs (behavior source of truth)
- `skills/00-MAIN-ORCHESTRATOR.md` — Main Orchestrator behavioral spec; mode selection, claiming loop, dispatch logic
- `skills/07-GLOBAL-ORCHESTRATION.md` — Global Orchestrator behavioral spec; state evaluation order, task identification logic, delegation map

### Agent Contracts and Architecture
- `agents/AGENT-CONTRACTS.md` — JSON schemas for all agent contracts; Phase 4 adds Main Orchestrator cycle summary output contract (MORD-05)
- `agents/AGENTS.md` — agent responsibilities and capability boundaries
- `runtime/RUNTIME-EXECUTION.md` — runtime execution model; "one action per Work Item Orchestrator" golden rule; parallel mode semantics

### Critical Failure Mode References
- `.planning/research/PITFALLS.md` — Pitfall 1 (double-claim / non-atomic claiming), Pitfall 4 (stale state), Pitfall 5 (context exhaustion) are the highest-risk pitfalls for Phase 4
- `.planning/research/STACK.md` — exact tool names, library versions, SDK patterns; use verbatim

### Prior Phase Context (Phase 4 depends on these being built)
- `.planning/phases/01-foundation-and-linear-integration/01-CONTEXT.md` — Python layout, OAuth2 auth, Linear Agent service interface
- `.planning/phases/02-core-execution-agents/02-CONTEXT.md` — no `gh stack`, integration test strategy, QA cycle cap
- `.planning/phases/03-work-item-orchestrator-and-single-cycle-mvp/03-CONTEXT.md` — WIO architecture (single Agent SDK session, inline skill injection), CLI baseline (`hsb run-next-step`), cascade-first gate

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from prior phases)
- `src/hsb/agents/linear_agent.py` (Phase 1): Linear Agent service — called by Global and Main Orchestrators for all Linear reads/writes via OAuth2 MCP
- `src/hsb/agents/work_item_orchestrator.py` (Phase 3): WIO Agent SDK session — dispatched by Main Orchestrator; interface must be stable before Phase 4 wraps it
- `src/hsb/cli/main.py` (Phases 1–3): Existing Typer CLI — Phase 4 adds `hsb run` subcommand alongside existing commands
- `run_loop.py` (Phase 3): Repo-root wrapper — updated to call `hsb run` in Phase 4
- `skills/00-MAIN-ORCHESTRATOR.md` + `skills/07-GLOBAL-ORCHESTRATION.md`: Behavioral specs ready to migrate as SKILL.md files

### Established Patterns (from Phases 1–3)
- Python package layout: `src/hsb/agents/` — Phase 4 adds `global_orchestrator.py`, `main_orchestrator.py`
- Pydantic contracts: one file per agent in `src/hsb/contracts/` — Phase 4 adds `global_orchestrator.py`, `main_orchestrator.py` contracts
- Integration tests use real Linear test workspace and real `hsb-test-fixture` GitHub repo — no mocking
- OAuth2 only: all Linear integration goes through `mcp-remote` OAuth2 flow — no API keys anywhere

### Integration Points
- Main Orchestrator calls Global Orchestrator (Python import, same process)
- Main Orchestrator calls Linear Agent (Python import) for claiming writes and cycle summary
- Main Orchestrator spawns WIO subprocesses (one per claimed task in parallel mode)
- `git worktree add / remove` shell commands called from Python via `subprocess` module
- `.worktrees/` directory at repo root — gitignored, managed entirely by Main Orchestrator

</code_context>

<specifics>
## Specific Ideas

- Claiming delay: 200ms between claims in the parallel claiming loop (configurable, default 200ms) — reduces collision window without meaningfully impacting throughput for MVP 2-task test
- `hsb run` output: same `rich` formatting as `hsb show-state` — operator can see what was dispatched and what completed
- Worktree naming: `.worktrees/LIN-{id}` — matches the branch name prefix so the relationship is obvious at a glance
- The two-task concurrent parallel test (Phase 4 Success Criterion 5) is the acceptance gate for parallel mode — must demonstrate zero double-claiming before parallel is considered shipped

</specifics>

<deferred>
## Deferred Ideas

- Custom Linear field for `assigned_orchestrator` — would require raw GraphQL API call (needs API key or token outside OAuth2 MCP layer); deferred permanently per architectural constraint (no API keys)
- Multi-process parallel dispatch (two `hsb run --parallel` processes simultaneously) — `status + updatedAt` optimistic lock is best-effort for this case; proper distributed locking deferred to future scope
- Event-driven mode (Linear/GitHub webhooks triggering cycles) — v2 scope per REQUIREMENTS.md
- `gh stack` integration — permanently deferred per Phase 2 D-06

</deferred>

---

*Phase: 04-global-main-orchestrators-and-parallel-mode*
*Context gathered: 2026-05-06*
