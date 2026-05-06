# Requirements: HSBTech AI Engineering Workflow

**Defined:** 2026-05-05
**Core Value:** A developer can provide a plan file and have AI agents coordinate the full implementation lifecycle — from backlog creation to QA-approved PRs — while Linear tracks every state transition and the human approves every merge.

## v1 Requirements

### Foundation

- [ ] **FOUND-01**: System provides a verified MCP connection to the official Linear server using API key or OAuth 2.1 auth
- [ ] **FOUND-02**: Python project scaffold is established with Claude Agent SDK (0.1.73+), pydantic 2.x, typer, and rich as core dependencies
- [ ] **FOUND-03**: Every agent input and output is validated against a pydantic schema matching the AGENT-CONTRACTS.md specification
- [ ] **FOUND-04**: Knowledge Store directory exists at `knowledge/` with category subdirectories (architecture, qa, implementation, backlog, risk) and a flat markdown+YAML-frontmatter format

### Linear Agent

- [ ] **LINR-01**: Operator can create an EPIC, User Story, Task, or Subtask in Linear with correct parent linkage via the Linear Agent
- [ ] **LINR-02**: Operator can update a work item's status, `qa_status`, `uat_status`, and `assigned_orchestrator` fields via the Linear Agent
- [ ] **LINR-03**: Operator can add a structured comment to a Linear issue (decision, QA finding, implementation note) via the Linear Agent
- [ ] **LINR-04**: Operator can link a GitHub PR URL to a Linear work item via the Linear Agent
- [ ] **LINR-05**: All Linear write operations include exponential backoff retry and log the `updatedAt` value before and after each mutation for optimistic-lock verification

### Backlog Agent

- [x] **BKPK-01
**: Backlog Agent reads a `plan.md` file and produces a structured backlog proposal (EPICs → User Stories → Tasks → Subtasks) traceable to the plan
- [x] **BKPK-02
**: Every EPIC produced by the Backlog Agent is persisted to Linear with title, description, and traceability reference to `plan.md`
- [x] **BKPK-03
**: Every User Story produced is persisted to Linear as a child of its EPIC with acceptance criteria
- [x] **BKPK-04
**: Every Task produced is persisted to Linear as a child of either a User Story or directly of an EPIC
- [x] **BKPK-05
**: Backlog Agent outputs traceability metadata mapping each work item back to its section in `plan.md`

### Builder Agent

- [x] **BLDR-01
**: Builder Agent receives a work item ID, reads the full Linear issue via the Linear Agent, and implements only the scoped change described by the issue
- [x] **BLDR-02
**: Builder Agent runs available local validations (build, lint, typecheck, tests) after implementation and reports results
- [x] **BLDR-03
**: Builder Agent produces an implementation output contract including files changed, validation results, decisions, assumptions, and QA notes
- [x] **BLDR-04
**: Builder Agent does not create branches, commit code, or write to Linear directly

### Git Agent

- [x] **GITA-01
**: Git Agent creates a branch named `feature/LIN-{id}-{slug}` for every task-level work item
- [x] **GITA-02
**: Git Agent determines the correct PR base: task PR targets the EPIC branch; EPIC branch PR targets `main`; fix PR targets the original task PR
- [x] **GITA-03
**: Git Agent creates a GitHub PR with the Linear issue ID in the title, UAT instructions in the body when applicable, and correct `--base` targeting
- [x] **GITA-04
**: Git Agent triggers a rebase cascade (`REBASE_STACK`) for all open sibling task PRs when a task PR is merged into the EPIC branch
- [x] **GITA-05
**: Git Agent never merges any PR into `main`

### QA Agent

- [x] **QAAG-01
**: QA Agent receives a PR diff and the full Linear issue and produces a structured findings contract with `approved` or `changes_required` status
- [x] **QAAG-02
**: Every QA finding includes: severity, category, blocking/non-blocking flag, evidence (file + location), expected vs actual behavior, and a suggested fix subtask
- [x] **QAAG-03
**: QA Agent creates a maximum of 5 fix subtasks per QA report via the Linear Agent
- [x] **QAAG-04
**: QA Agent increments `qa_cycle_count` on the work item; when `qa_cycle_count >= 3` the QA Agent approves with tech-debt annotation rather than requiring further fixes
- [x] **QAAG-05
**: QA Agent never modifies code or creates PRs directly

### Work Item Orchestrator

- [ ] **WORC-01**: Work Item Orchestrator drives a single work item from `todo` to `done` through the full lifecycle: Intelligence → Builder → Git → QA → fix loop → done
- [ ] **WORC-02**: Work Item Orchestrator embeds all lifecycle skill content inline (no sub-subagent dispatch) and executes each lifecycle step as sequential tool use within its own context window
- [ ] **WORC-03**: Work Item Orchestrator tracks `qa_cycle_count` and enforces `max_qa_cycles = 3` termination; escalates to human if hard limit is reached without approval
- [ ] **WORC-04**: Every agent invocation by the Work Item Orchestrator passes the full Linear issue content as structured input — no reliance on conversation memory
- [ ] **WORC-05**: Work Item Orchestrator outputs a lifecycle status summary and persists it to Linear as a comment on the work item

### Global Orchestrator

- [ ] **GORD-01**: Global Orchestrator reads current Linear project state and returns a prioritized list of all non-blocked, `todo`-status work items
- [ ] **GORD-02**: Global Orchestrator respects Linear `blocked-by` dependency links — a work item is not returned as ready if any blocking dependency is not `done`
- [ ] **GORD-03**: Global Orchestrator detects when no backlog exists and signals `is_backlog_empty` to trigger backlog creation
- [ ] **GORD-04**: Global Orchestrator signals when all child items of an EPIC are `done` and the EPIC is ready for manual merge

### Main Orchestrator

- [ ] **MORD-01**: Main Orchestrator accepts an execution mode (`cascade` or `parallel`) and dispatches Work Item Orchestrators accordingly
- [ ] **MORD-02**: In cascade mode, Main Orchestrator executes one Work Item Orchestrator at a time and waits for completion before proceeding
- [ ] **MORD-03**: In parallel mode, Main Orchestrator claims each ready task in Linear (write `in_progress`, re-read to verify `assigned_orchestrator` matches) before dispatch — skips unclaimed tasks
- [ ] **MORD-04**: In parallel mode, each Work Item Orchestrator runs in an isolated git worktree (`isolation: worktree`)
- [ ] **MORD-05**: Main Orchestrator persists a cycle summary to Linear via the Linear Agent after all dispatched orchestrators complete

### CLI Runtime

- [ ] **CLIR-01**: Operator can trigger a single orchestration cycle with `run next step` from the command line
- [ ] **CLIR-02**: Operator can view the current system state (Linear phase, EPIC status, ready tasks) with `show current state`
- [ ] **CLIR-03**: Operator can inspect the next recommended action without executing it with `show next action`
- [ ] **CLIR-04**: Operator can run a continuous CLI loop (`python run_loop.py`) that repeats orchestration cycles until no ready tasks remain or operator interrupts
- [ ] **CLIR-05**: Each CLI command is a standalone `asyncio.run()` invocation — state lives in Linear, not in the CLI process

### UAT Agent

- [ ] **UATA-01**: UAT Agent validates a User Story from user-acceptance perspective after all related task PRs are QA-approved
- [ ] **UATA-02**: UAT Agent produces UAT scenarios derived from acceptance criteria with expected vs actual behavior and pass/fail result per scenario
- [ ] **UATA-03**: UAT Agent creates UAT fix subtasks via the Linear Agent when UAT status is `changes_required`
- [ ] **UATA-04**: UAT Agent operates only on User Story scope — it does not review low-level code or create PRs

### Intelligence Agent

- [ ] **INTL-01**: Intelligence Agent retrieves relevant knowledge entries from the Knowledge Store (via Glob + Grep over `knowledge/`) and produces an enrichment report before Builder execution
- [ ] **INTL-02**: Intelligence Agent persists a new knowledge entry to the Knowledge Store when a QA finding, implementation pattern, or architectural decision meets minimum-evidence criteria
- [ ] **INTL-03**: Every knowledge entry written by the Intelligence Agent includes: title, type, context, evidence (Linear issue + PR + files), insight, recommendation, applicability, and date
- [ ] **INTL-04**: Intelligence Agent does not mutate Linear operational state directly

### Risk Agent

- [ ] **RISK-01**: Risk Agent calculates a quality score and risk level (`low`/`medium`/`high`) for each work item using QA findings history and rework index
- [ ] **RISK-02**: Risk Agent produces a prioritized work item queue with score and reason for each item
- [ ] **RISK-03**: Risk Agent detects repeated QA failure patterns and produces improvement trigger suggestions with suggested Linear work items
- [ ] **RISK-04**: Risk Agent does not execute improvements or create Linear work items without explicit delegation through the Linear Agent

## v2 Requirements

### Event-Driven Triggers

- **EVNT-01**: System triggers an orchestration cycle when a Linear issue status changes via webhook
- **EVNT-02**: System triggers an orchestration cycle when a GitHub PR is opened or merged via webhook
- **EVNT-03**: Webhook events are queued and deduplicated before triggering execution

### Observability

- **OBSV-01**: System generates an operational dashboard showing EPIC progress, task statuses, QA pass rates, and cycle time
- **OBSV-02**: System produces historical trend analysis (rework rate, fix subtask rate, QA cycle count distribution)
- **OBSV-03**: System tracks SLA per EPIC based on estimated vs actual completion

### Advanced Intelligence

- **ADVL-01**: Intelligence Agent supports semantic search over Knowledge Store entries
- **ADVL-02**: Intelligence Agent clusters related patterns across multiple projects
- **ADVL-03**: Risk Agent uses ML-based scoring once sufficient QA history exists (minimum 50 cycles)

### Multi-Project Support

- **MLTI-01**: System supports multiple concurrent Linear projects with isolated state
- **MLTI-02**: Knowledge Store entries are tagged by project and can be shared across projects when applicable

## Out of Scope

| Feature | Reason |
|---------|--------|
| Automatic merges to `main` | Safety constraint — EPIC PR merge must always be manual; no exceptions |
| Linear as optional / replaceable state store | Linear is the system of record; abstracting it away defeats the architecture |
| LangChain / LangGraph / CrewAI orchestration | Conflicts with SKILL.md format; adds abstraction that doesn't compose with Claude Agent SDK |
| Agent Teams (Claude Code experimental) | Known limitations on session resumption; explicitly not for production parallel dispatch |
| ML-based risk scoring in v1 | Requires training data that doesn't exist until after many QA cycles |
| Real-time dashboards | Linear comments provide sufficient audit trail for v1; dashboard is observability overhead |
| Multi-project knowledge sharing | Not warranted at MVP scale; requires metadata schema beyond MVP scope |

## Traceability

Populated during roadmap creation by the roadmapper agent.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Pending |
| FOUND-02 | Phase 1 | Pending |
| FOUND-03 | Phase 1 | Pending |
| FOUND-04 | Phase 1 | Pending |
| LINR-01 | Phase 1 | Pending |
| LINR-02 | Phase 1 | Pending |
| LINR-03 | Phase 1 | Pending |
| LINR-04 | Phase 1 | Pending |
| LINR-05 | Phase 1 | Pending |
| BKPK-01 | Phase 2 | Pending |
| BKPK-02 | Phase 2 | Pending |
| BKPK-03 | Phase 2 | Pending |
| BKPK-04 | Phase 2 | Pending |
| BKPK-05 | Phase 2 | Pending |
| BLDR-01 | Phase 2 | Pending |
| BLDR-02 | Phase 2 | Pending |
| BLDR-03 | Phase 2 | Pending |
| BLDR-04 | Phase 2 | Pending |
| GITA-01 | Phase 2 | Pending |
| GITA-02 | Phase 2 | Pending |
| GITA-03 | Phase 2 | Pending |
| GITA-04 | Phase 2 | Pending |
| GITA-05 | Phase 2 | Pending |
| QAAG-01 | Phase 2 | Pending |
| QAAG-02 | Phase 2 | Pending |
| QAAG-03 | Phase 2 | Pending |
| QAAG-04 | Phase 2 | Pending |
| QAAG-05 | Phase 2 | Pending |
| WORC-01 | Phase 3 | Pending |
| WORC-02 | Phase 3 | Pending |
| WORC-03 | Phase 3 | Pending |
| WORC-04 | Phase 3 | Pending |
| WORC-05 | Phase 3 | Pending |
| CLIR-01 | Phase 3 | Pending |
| CLIR-02 | Phase 3 | Pending |
| CLIR-03 | Phase 3 | Pending |
| CLIR-04 | Phase 3 | Pending |
| CLIR-05 | Phase 3 | Pending |
| GORD-01 | Phase 4 | Pending |
| GORD-02 | Phase 4 | Pending |
| GORD-03 | Phase 4 | Pending |
| GORD-04 | Phase 4 | Pending |
| MORD-01 | Phase 4 | Pending |
| MORD-02 | Phase 4 | Pending |
| MORD-03 | Phase 4 | Pending |
| MORD-04 | Phase 4 | Pending |
| MORD-05 | Phase 4 | Pending |
| UATA-01 | Phase 5 | Pending |
| UATA-02 | Phase 5 | Pending |
| UATA-03 | Phase 5 | Pending |
| UATA-04 | Phase 5 | Pending |
| INTL-01 | Phase 5 | Pending |
| INTL-02 | Phase 5 | Pending |
| INTL-03 | Phase 5 | Pending |
| INTL-04 | Phase 5 | Pending |
| RISK-01 | Phase 5 | Pending |
| RISK-02 | Phase 5 | Pending |
| RISK-03 | Phase 5 | Pending |
| RISK-04 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 57 total
- Mapped to phases: 57 (roadmap complete)
- Unmapped: 0

---
*Requirements defined: 2026-05-05*
*Last updated: 2026-05-05 after roadmap creation*
