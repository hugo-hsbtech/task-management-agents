# Phase 2: Core Execution Agents - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers four independently functional execution agents — Backlog, Builder, Git, and QA — each verified in isolation before Phase 3 wires them together into an orchestrated lifecycle.

- **Backlog Agent**: Reads a user-provided plan.md (free-form markdown), generates EPIC → User Story → Task → Subtask hierarchy, persists to Linear with traceability metadata
- **Builder Agent**: Receives a Linear work item, implements only the scoped change, runs local validations, produces an output contract — no git or Linear writes
- **Git Agent**: Creates correctly named branches, opens stacked PRs (task PR targets EPIC branch), triggers REBASE_STACK cascade when sibling task PRs merge — all via manual `gh` CLI (no `gh stack`)
- **QA Agent**: Reviews PR diff against Linear issue, produces structured findings contract, writes to Linear directly (increment `qa_cycle_count`, create fix subtasks via Linear Agent)

No orchestration logic (Work Item Orchestrator, Global Orchestrator, Main Orchestrator). Those are Phase 3+.

</domain>

<decisions>
## Implementation Decisions

### Backlog Agent — plan.md Input

- **D-01:** Backlog Agent accepts **free-form markdown** as plan.md input. No required template or heading structure. The LLM running the skill parses the plan using language understanding — any reasonable markdown document (goals, deliverables, feature descriptions) is valid input.
- **D-02:** Plan file path is **user-specified at runtime** via `--plan <path>` argument. No hardcoded default. Operator must always provide the path. If omitted → FAIL (per existing MANDATORY INPUT constraint in `skills/01-BACKLOG-PLANNING.md`).
- **D-03:** Traceability (BKPK-05) is expressed as **section quotes embedded in Linear descriptions**. Each Linear issue description includes the relevant excerpt from plan.md that motivated it. Human-readable, no tooling required, works with free-form input.

### QA Agent — Linear Write Scope

- **D-04:** QA Agent has **full Linear write capability in Phase 2**. It internally calls the Linear Agent service (built in Phase 1) to:
  - Increment `qa_cycle_count` on the work item after each review (QAAG-04)
  - Create fix subtasks in Linear (max 5 per report) when `qa_status = changes_required` (QAAG-03)
  - No Linear writes are deferred to Phase 3 orchestrator
- **D-05:** The QA cycle cap logic — "when `qa_cycle_count >= 3`, approve with tech-debt annotation instead of requesting further fixes" — lives **inside the QA Agent SKILL.md**. The LLM reads `qa_cycle_count` from the input contract and switches behavior at the threshold. No Python enforcement layer.

### Git Agent — PR Stacking Strategy

- **D-06:** `gh stack` is **not used** in Phase 2 (or any phase). It is in private preview and introduces an unstable dependency. All PR operations use plain `gh` CLI commands.
- **D-07:** **All task PRs target the EPIC branch directly** (`--base <epic-branch>`). No chained task-to-task PR bases (Case 2 from `skills/04` is not implemented). This simplifies the stacking model: conflicts are resolved by the human at EPIC PR merge time.
- **D-08:** REBASE_STACK cascade (GITA-04) is implemented **manually**: enumerate sibling open task PRs via `gh pr list --base <epic-branch> --state open`, then `git rebase --onto <epic-branch>` for each. No dependency on private preview tooling.

### Testing Strategy

- **D-09:** All four Phase 2 agents are verified via **integration tests against real external services** — real Linear test workspace and real GitHub repo. No mocking of Linear MCP tools or `gh` CLI. Consistent with Phase 1's approach (per PITFALLS.md: mock/real divergence has burned the project before).
- **D-10:** Pydantic contract validation (input/output schema correctness) is tested with **unit tests** — fast, no external dependencies, complementary to the integration tests.
- **D-11:** Builder Agent integration tests run against a **dedicated real GitHub repo** (e.g., `hsb-test-fixture`) on a test branch. This repo contains a minimal Python package that Builder Agent can safely modify without affecting HSBTech's own codebase. Git Agent integration tests can target the same fixture repo.

### Claude's Discretion

- **SKILL.md migration**: Each Phase 2 agent (Backlog, Builder, Git, QA) should have its SKILL.md migrated to `.claude/skills/<name>/SKILL.md` during Phase 2, following the pattern established in Phase 1 for the Linear Agent.
- **`qa_cycle_count` read source**: Whether `qa_cycle_count` is read from the input contract (caller provides it) or fetched live from Linear before QA review begins — Claude decides based on what keeps the contract clean.
- **Test fixture repo setup**: Exact structure of the `hsb-test-fixture` repo (what the minimal Python package contains, branch naming, cleanup strategy) — Claude decides to minimize test setup overhead.
- **Builder validation detection**: How Builder Agent determines which local validations to run (e.g., detect pytest, ruff, mypy by checking for config files) — Claude decides the detection heuristic.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Agent Contracts and Architecture
- `agents/AGENT-CONTRACTS.md` — JSON schemas for all agent input/output contracts; pydantic models MUST match these exactly. Phase 2 agents: Backlog (§1), Implementation (§4), Git/PR Management (§5), QA Review (§6)
- `agents/AGENTS.md` — agent responsibilities and capability boundaries
- `runtime/RUNTIME-EXECUTION.md` — runtime execution model and session handling

### Phase 2 Skill Specs (behavior source of truth)
- `skills/01-BACKLOG-PLANNING.md` — Backlog Agent behavioral spec; SKILL.md migrated to `.claude/skills/backlog-planning/SKILL.md`
- `skills/02-IMPLEMENTATION.md` — Builder Agent behavioral spec; SKILL.md migrated to `.claude/skills/implementation/SKILL.md`
- `skills/03-QA-REVIEW.md` — QA Agent behavioral spec; SKILL.md migrated to `.claude/skills/qa-review/SKILL.md`
- `skills/04-GIT-PR-MANAGEMENT.md` — Git Agent behavioral spec; SKILL.md migrated to `.claude/skills/git-pr-management/SKILL.md`

### Phase 1 Foundation (Phase 2 depends on these being built)
- `agents/AGENT-CONTRACTS.md` §2 — Linear System of Record contract (QA Agent calls this)
- `.planning/research/STACK.md` — exact tool names, library versions, SDK patterns; use verbatim
- `.planning/research/PITFALLS.md` — critical failure modes Phase 2 must not introduce (especially Pitfall 1: double-claim, Pitfall 2: QA runaway, Pitfall 4: stale state)
- `.planning/phases/01-foundation-and-linear-integration/01-CONTEXT.md` — Phase 1 decisions (Python layout, pydantic structure, SKILL.md migration pattern, Linear Agent service interface)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `skills/01-BACKLOG-PLANNING.md` through `skills/04-GIT-PR-MANAGEMENT.md`: Complete behavioral specs ready to migrate as SKILL.md files. Content is migration-ready — add YAML frontmatter (`name`, `description`, `allowed-tools`) and commit to `.claude/skills/<name>/SKILL.md`.
- `agents/AGENT-CONTRACTS.md`: Phase 2 agent contracts (§1, §4, §5, §6) fully define pydantic input/output models for Backlog, Builder, Git, QA. Do not invent fields.

### Established Patterns (from Phase 1)
- Python package layout: `src/hsb/agents/`, `src/hsb/contracts/`, `src/hsb/cli/` — Phase 2 adds `backlog_agent.py`, `builder_agent.py`, `git_agent.py`, `qa_agent.py` to `src/hsb/agents/`
- Pydantic contracts: one file per agent in `src/hsb/contracts/` (e.g., `backlog.py`, `builder.py`, `git.py`, `qa.py`)
- SKILL.md frontmatter pattern: established by Phase 1 Linear skill — follow same structure
- Linear Agent service interface: `src/hsb/agents/linear_agent.py` — QA Agent calls this directly to write `qa_cycle_count` and create fix subtasks

### Integration Points
- Phase 2 agents connect to Phase 1's Linear Agent service (Python import, not MCP directly)
- QA Agent requires Phase 1 Linear Agent to be operational before its integration tests can run
- Git Agent requires a real GitHub repo (`hsb-test-fixture`) and `gh` CLI authenticated
- All agents are invocable as standalone CLI commands (extend `src/hsb/cli/main.py` with per-agent subcommands)

</code_context>

<specifics>
## Specific Ideas

- Branch naming: `feature/LIN-{id}-{slug}` (from GITA-01 and skills/04) — exact format, no variation
- PR title format: `[LIN-{id}] {short description}` (from skills/04) — must include Linear issue ID
- Max fix subtasks: exactly 5 per QA report — hard cap, not a guideline (QAAG-03)
- `qa_cycle_count` cap: exactly 3 cycles — at count 3, approve with tech-debt annotation, never request a 4th fix cycle (QAAG-04)
- QA Agent must NEVER create PRs or modify code — only reads diff and writes to Linear (QAAG-05)
- Builder Agent must NEVER create branches, commit code, or write to Linear — only produces implementation output contract (BLDR-04)

</specifics>

<deferred>
## Deferred Ideas

- `gh stack` integration — not implemented in any phase; manual `gh pr create --base` is the production strategy
- Chained task-to-task PR bases (skills/04 Case 2) — not implemented in Phase 2; all tasks target EPIC branch. If task dependency ordering is needed, revisit in Phase 4+ when parallel orchestration requires explicit ordering
- Simulation/dry-run mode for agents — explicitly out of scope per REQUIREMENTS.md
- Builder Agent validation auto-detection beyond basic heuristics — Phase 5 Intelligence Agent is better positioned to enrich this

</deferred>

---

*Phase: 02-core-execution-agents*
*Context gathered: 2026-05-05*
