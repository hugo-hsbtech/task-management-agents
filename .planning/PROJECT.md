# HSBTech AI Engineering Workflow

## What This Is

HSBTech is an AI-powered engineering delivery system that takes a documented plan and executes it through a structured multi-agent pipeline. Specialized agents (Backlog, Builder, QA, UAT, Git, Orchestrators) coordinate to implement, review, and deliver work — with Linear as the operational system of record and GitHub as the code delivery surface. The human retains full control: every merge is manual, every agent action is traceable.

## Core Value

A developer can provide a plan file and have AI agents coordinate the full implementation lifecycle — from backlog creation to QA-approved PRs — while Linear tracks every state transition and the human approves every merge.

## Requirements

### Validated

(None fully validated yet — Phases 1+2 complete in code with 55 passing unit tests; live MCP/GitHub integration suites pending operator-driven runs)

### Active

- [x] Backlog Planning skill — transforms `plan.md` into EPIC/User Story/Task/Subtask hierarchy and persists to Linear *(Phase 2 complete; integration pending live run)*
- [ ] Linear Agent — reads and writes operational state in Linear via MCP (create, update, link, comment)
- [x] Builder Agent — implements scoped code changes from task specifications and acceptance criteria *(Phase 2 complete; integration pending live run)*
- [x] Git Agent — creates branches, commits changes, and opens correctly targeted stacked PRs *(Phase 2 complete; integration pending live run)*
- [x] QA Agent — reviews PR diffs against requirements and produces structured findings with fix subtasks *(Phase 2 complete; integration pending live run)*
- [ ] Work Item Orchestrator — drives one work item through its full lifecycle (implement → PR → QA → fix loop → done)
- [ ] Global Orchestrator — reads Linear state, identifies all ready non-blocked tasks, returns prioritized list
- [ ] Main Orchestrator — entry point that selects execution mode (cascade/parallel) and dispatches to Work Item Orchestrators
- [ ] Agent Contracts — JSON-structured input/output interfaces connecting all agents
- [ ] Runtime CLI loop — manual-assisted trigger mode with `run next step` commands
- [ ] UAT Agent — validates User Stories from user-acceptance perspective after QA approval
- [ ] Intelligence Agent — enriches work items with codebase context and persists reusable knowledge
- [ ] Risk Agent — quality scoring, risk analysis, and adaptive prioritization input to Global Orchestrator
- [ ] Knowledge Store — persistent file-based store for reusable patterns, QA insights, and architectural decisions

### Out of Scope

- Event-driven triggers (Linear/GitHub webhooks) — future enhancement; MVP uses manual and CLI loop modes
- Real-time observability dashboards — documented as future scope
- Multi-project intelligence / cross-project knowledge — future scope
- Simulation/dry-run mode — future scope
- Automatic merges to main — intentionally excluded; all EPIC PRs require manual approval
- Advanced ML-based risk prediction — future scope

## Context

- All 15 skill documents exist as markdown specs in `skills/` (00-MAIN-ORCHESTRATOR through 14-AUTO-IMPROVEMENT-TRIGGERS)
- Agent contracts are fully defined in `agents/AGENT-CONTRACTS.md` — JSON schemas for all inputs/outputs
- Agent responsibilities are defined in `agents/AGENTS.md`
- Runtime execution model is documented in `runtime/RUNTIME-EXECUTION.md`
- The MVP target is one complete controlled cycle: 1 EPIC → 2-3 Tasks → Implementation → PR → QA → Fix → Done
- Must support Claude Code and Codex as runtimes (tool-agnostic agent design)
- Linear MCP is the integration surface for state management (`mcp__claude_ai_Linear__*`)
- GitHub CLI (`gh`) is the integration surface for PR management
- Stacked PR strategy: task PRs target the EPIC branch; EPIC PR targets `main` (manual merge only)

## Constraints

- **Safety**: No agent may merge into `main` — EPIC PR merge is always manual
- **Scope**: One action per Work Item Orchestrator cycle — prevents runaway automation
- **State**: All durable operational state must go to Linear; reusable intelligence goes to Knowledge Store
- **Runtime**: Agents must be tool-agnostic (no hard dependency on Claude Code vs. Codex)
- **QA**: Every PR must pass QA before the work item can be marked done — QA cannot be skipped
- **Dependency**: Every UAT cycle requires prior QA approval on related PRs

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Linear as system of record | Single source of truth prevents hidden state across agent boundaries | — Pending |
| Stacked PR strategy | Task PRs → EPIC PR → manual merge keeps merge surface small and traceable | — Pending |
| Skills as markdown specs | Runtime-agnostic; works with Claude Code, Codex, and future runtimes | — Pending |
| Three-level orchestration hierarchy | Main → Global → Work Item separates mode selection, readiness detection, and lifecycle management | — Pending |
| MVP = manual assisted mode | Start controlled; CLI loop and event-driven are phase 2+ | — Pending |
| Max 5 fix subtasks per QA report | Prevents backlog explosion from a single noisy review | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-06 after Phase 02 completion (4 execution agents — Backlog/Builder/Git/QA — wired with two-layer capability boundaries; 55 unit tests passing; integration suites pending operator-driven live runs)*
