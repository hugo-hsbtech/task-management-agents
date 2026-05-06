# Roadmap: HSBTech AI Engineering Workflow

## Overview

This roadmap builds the HSBTech multi-agent delivery pipeline bottom-up, following strict dependency order. Phase 1 establishes the Linear integration and contract layer that every other agent depends on. Phase 2 builds the four core execution agents independently before wiring them together. Phase 3 is the MVP gate — proving one complete controlled cycle from Task todo to done. Phase 4 adds the orchestration hierarchy and unlocks parallel execution only after the cascade cycle is validated. Phase 5 rounds out the system with enhancement agents that add intelligence, UAT validation, and risk-aware prioritization on top of a proven delivery loop.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation and Linear Integration** - Establish the verified Linear MCP connection, pydantic contract layer, and Knowledge Store that every agent depends on
- [ ] **Phase 2: Core Execution Agents** - Build Backlog, Builder, Git, and QA agents independently with correct PR stacking and QA termination logic
- [ ] **Phase 3: Work Item Orchestrator and Single-Cycle MVP** - Wire the execution agents into a complete lifecycle and prove one full end-to-end cycle in cascade mode
- [ ] **Phase 4: Global + Main Orchestrators and Parallel Mode** - Add prioritized work-item selection, cascade/parallel dispatch, and worktree isolation
- [ ] **Phase 5: Enhancement Agents** - Add Intelligence, UAT, and Risk agents on top of the validated delivery loop

## Phase Details

### Phase 1: Foundation and Linear Integration
**Goal**: The Linear Agent works correctly and every agent contract is validated — the durable foundation every other phase depends on
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, LINR-01, LINR-02, LINR-03, LINR-04, LINR-05
**Success Criteria** (what must be TRUE):
  1. Operator can create an EPIC, User Story, Task, and Subtask in Linear with correct parent linkage via the Linear Agent CLI
  2. Operator can update issue status, qa_status, uat_status, and assigned_orchestrator fields via the Linear Agent and verify the change in Linear
  3. Operator can add a structured comment and link a PR URL to a Linear issue via the Linear Agent
  4. All Linear write operations retry on failure with exponential backoff and log updatedAt before and after each mutation
  5. Every agent input/output object passes pydantic validation against AGENT-CONTRACTS.md schemas, and the Knowledge Store directory exists with all category subdirectories
**Plans**: 5 plans
Plans:
- [x] 01-01-PLAN.md — Project scaffold (pyproject.toml, .mcp.json, knowledge/ tree, Linear SKILL.md migration) — FOUND-02, FOUND-04
- [x] 01-02-PLAN.md — Pydantic contract models mirroring AGENT-CONTRACTS.md + schema-drift tests — FOUND-03
- [x] 01-03-PLAN.md — Claude Agent SDK lifecycle hooks (retry/backoff, audit log, PreCompact, list filter) + tests — LINR-05 (hooks)
- [ ] 01-04-PLAN.md — Linear Agent service: run_linear_agent + run_validated_linear_agent (validation retry layer) — LINR-05 (system prompt)
- [ ] 01-05-PLAN.md — Typer CLI (create-issue, update-issue, add-comment, link-pr) + integration tests + human checkpoint — FOUND-01, LINR-01, LINR-02, LINR-03, LINR-04

### Phase 2: Core Execution Agents
**Goal**: The four execution agents — Backlog, Builder, Git, QA — are each independently functional and produce correct, verifiable output before any orchestrator wires them together
**Depends on**: Phase 1
**Requirements**: BKPK-01, BKPK-02, BKPK-03, BKPK-04, BKPK-05, BLDR-01, BLDR-02, BLDR-03, BLDR-04, GITA-01, GITA-02, GITA-03, GITA-04, GITA-05, QAAG-01, QAAG-02, QAAG-03, QAAG-04, QAAG-05
**Success Criteria** (what must be TRUE):
  1. Operator can run the Backlog Agent against a plan.md and see a full EPIC → User Story → Task → Subtask hierarchy persisted to Linear with traceability metadata
  2. Builder Agent receives a work item ID, implements only the scoped change, runs local validations, and produces an output contract — without touching git or Linear directly
  3. Git Agent creates a correctly named branch, opens a PR with the task PR targeting the EPIC branch and the EPIC PR targeting main, and triggers REBASE_STACK when a sibling task PR merges
  4. QA Agent produces a structured findings contract (approved or changes_required) with severity, blocking flag, evidence, and suggested fix subtask for each finding — and never exceeds 5 fix subtasks per report
  5. QA Agent increments qa_cycle_count and approves with tech-debt annotation when qa_cycle_count reaches 3, rather than requesting further fixes
**Plans**: 5 plans
Plans:
- [ ] 02-01-PLAN.md — Wave 0 test scaffolds + per-agent CLI module skeletons + hsb-test-fixture checkpoint (covers all 19 requirement IDs as test stubs)
- [ ] 02-02-PLAN.md — Backlog Agent: contracts + agent + SKILL.md + CLI + integration tests — BKPK-01..05
- [ ] 02-03-PLAN.md — Builder Agent: contracts + agent + SKILL.md + CLI + integration tests — BLDR-01..04
- [ ] 02-04-PLAN.md — Git Agent: contracts + agent + SKILL.md + CLI (create-pr, rebase-stack) + integration tests — GITA-01..05
- [ ] 02-05-PLAN.md — QA Agent: contracts (with IMMUTABLE cycle cap validator) + agent + SKILL.md + CLI + integration tests — QAAG-01..05

### Phase 3: Work Item Orchestrator and Single-Cycle MVP
**Goal**: One complete controlled cycle — a single Task moving from todo to done through Intelligence → Builder → Git → QA → fix loop — runs successfully in cascade mode via CLI trigger
**Depends on**: Phase 2
**Requirements**: WORC-01, WORC-02, WORC-03, WORC-04, WORC-05, CLIR-01, CLIR-02, CLIR-03, CLIR-04, CLIR-05
**Success Criteria** (what must be TRUE):
  1. Operator runs `run next step` from the CLI and a single work item progresses exactly one lifecycle step (no runaway automation)
  2. Work Item Orchestrator drives a Task from todo to done through the full lifecycle with all lifecycle skill content embedded inline — no sub-subagent dispatch
  3. When qa_cycle_count reaches 3 without QA approval, the orchestrator escalates to human rather than initiating a fourth QA cycle
  4. Every agent invocation during the cycle receives the full Linear issue content as explicit structured input — no reliance on conversation memory
  5. Operator can view current system state and next recommended action from the CLI without triggering execution; the CLI loop repeats cycles autonomously until no ready tasks remain
**Plans**: 4 plans
Plans:
- [ ] 03-01-PLAN.md — Foundation: pydantic contracts + Wave 0 test stubs + task-orchestration SKILL.md migration — covers all 10 requirement IDs as test stubs
- [ ] 03-02-PLAN.md — Work Item Orchestrator implementation: single SDK session + skill injection + four @tool wrappers + QA cycle cap safety net — WORC-01..05
- [ ] 03-03-PLAN.md — CLI extensions (run-next-step, show-state, show-next-action) + run_loop.py thin wrapper — CLIR-01..05
- [ ] 03-04-PLAN.md — Integration tests + MVP benchmark cycle (real Linear + hsb-test-fixture) + human GO/NO-GO checkpoint — WORC-01, WORC-05, CLIR-01, CLIR-04

### Phase 4: Global + Main Orchestrators and Parallel Mode
**Goal**: The full three-level orchestration hierarchy works in cascade mode, then parallel mode with optimistic claiming and worktree isolation passes a two-task concurrent test
**Depends on**: Phase 3
**Requirements**: GORD-01, GORD-02, GORD-03, GORD-04, MORD-01, MORD-02, MORD-03, MORD-04, MORD-05
**Success Criteria** (what must be TRUE):
  1. Global Orchestrator returns a prioritized list of all non-blocked todo-status work items and correctly excludes any task whose blocking dependency is not done
  2. Global Orchestrator detects an empty backlog and signals is_backlog_empty; detects all EPIC children done and signals EPIC ready for manual merge
  3. Main Orchestrator runs two Work Item Orchestrators in cascade mode sequentially and persists a cycle summary to Linear after both complete
  4. In parallel mode, each Work Item Orchestrator claims its task with the optimistic-lock protocol (write in_progress, re-read, verify assigned_orchestrator) and runs in an isolated git worktree
  5. No task is double-claimed during a parallel run with two concurrent orchestrators targeting the same ready-task list
**Plans**: 4 plans
Plans:
- [ ] 04-01-PLAN.md — Foundation: pydantic contracts + Wave 0 test stubs (GORD-01..04, MORD-01..05) + SKILL.md migrations + .gitignore
- [ ] 04-02-PLAN.md — Global Orchestrator: pure Python class implementation + GORD-01..04 unit tests
- [ ] 04-03-PLAN.md — Main Orchestrator: pure Python dispatch controller + optimistic-lock claiming + worktree lifecycle + asyncio.gather + MORD-01..04 unit tests
- [ ] 04-04-PLAN.md — CLI integration (hsb run + --parallel) + run_loop.py update + integration tests + two-task parallel acceptance gate (human checkpoint)

### Phase 5: Enhancement Agents
**Goal**: Intelligence, UAT, and Risk agents are active on top of the validated delivery loop — enriching work items before implementation, validating User Stories after QA, and feeding risk-aware prioritization to the Global Orchestrator
**Depends on**: Phase 4
**Requirements**: UATA-01, UATA-02, UATA-03, UATA-04, INTL-01, INTL-02, INTL-03, INTL-04, RISK-01, RISK-02, RISK-03, RISK-04
**Success Criteria** (what must be TRUE):
  1. Intelligence Agent retrieves relevant knowledge entries from the Knowledge Store before Builder execution and produces an enrichment report visible in the work item comment
  2. Intelligence Agent writes a new knowledge entry with all required fields (title, type, context, evidence, insight, recommendation, applicability, date) when a QA finding or implementation pattern meets minimum-evidence criteria
  3. UAT Agent validates a User Story from user-acceptance perspective after all related task PRs are QA-approved, producing scenario results with pass/fail per acceptance criterion — without reviewing low-level code or creating PRs
  4. Risk Agent produces a quality score and risk level for each work item and a prioritized queue with reason per item, consumed by Global Orchestrator for ordering
  5. Risk Agent detects repeated QA failure patterns and surfaces improvement trigger suggestions — without creating Linear work items unless explicitly delegated through the Linear Agent
**Plans**: 4 plans
Plans:
- [ ] 05-01-PLAN.md — Intelligence Agent (WIO inline extension): skills 10+11 injection + Step 1 enrichment + Step 5 storage + KnowledgeStorageInput contract — INTL-01..04
- [ ] 05-02-PLAN.md — Risk Agent (pure Python class + isolated skill 14 SDK call): RiskAgent + risk.py contracts + _sdk_options.py G2 factory + 3 SKILL.md migrations + Hypothesis tests — RISK-01..04
- [ ] 05-03-PLAN.md — UAT Agent (standalone Pattern B SDK session): run_uat_and_validate + uat.py contracts + skill 08 SKILL.md + UATA-04 structural enforcement — UATA-01..04
- [ ] 05-04-PLAN.md — Global Orchestrator wiring (Wave 2): Risk priority insertion + UAT detection/dispatch + G6 cycle cap + G10 pre-persist validation + human checkpoint — UATA-01, UATA-03

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation and Linear Integration | 0/5 | Not started | - |
| 2. Core Execution Agents | 0/5 | Not started | - |
| 3. Work Item Orchestrator and Single-Cycle MVP | 0/4 | Not started | - |
| 4. Global + Main Orchestrators and Parallel Mode | 0/4 | Not started | - |
| 5. Enhancement Agents | 0/4 | Not started | - |
