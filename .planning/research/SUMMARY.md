# Project Research Summary

**Project:** HSBTech AI Engineering Workflow
**Domain:** Multi-agent AI engineering orchestration
**Researched:** 2026-05-05
**Confidence:** HIGH

## Executive Summary

HSBTech is a state-machine-driven multi-agent pipeline that converts a `plan.md` file into a fully executed, QA-reviewed, human-mergeable set of GitHub PRs. The system is built on the Claude Agent SDK (Python), uses Linear as its sole durable state store, coordinates work through a three-level orchestration hierarchy (Main → Global → Work Item), and delivers code artifacts as stacked PRs via the GitHub CLI. All merges to `main` are manual; every agent action is traceable via Linear comments. The defining design constraints are: one action per Work Item Orchestrator cycle, no agent writes to Linear except through the Linear Agent, and subagents cannot spawn subagents — the Work Item Orchestrator embeds all specialized logic inline rather than dispatching further sub-subagents.

The recommended approach is to build bottom-up following the four-layer dependency order from ARCHITECTURE.md: foundation (Linear Agent + contract schemas) → core execution agents (Backlog, Builder, Git, QA) → orchestration (Work Item Orchestrator, Global Orchestrator) → runtime entry point (CLI loop, Main Orchestrator). Enhancement agents (Intelligence, UAT, Risk) are deliberately deferred past the MVP cycle. MVP target is one complete controlled cycle: 1 EPIC → 2-3 Tasks → Implementation → PR → QA → Fix → Done, running in cascade (sequential) mode before parallel mode is enabled.

The top risks are QA loop runaway (fix subtasks breeding more fix subtasks without a hard cycle cap), double-claiming in parallel mode (Linear MCP offers no compare-and-swap, requiring an optimistic lock with re-read verification), and stacked PR base drift (merged PRs cause cascading rebase needs for all sibling task PRs). All three must be designed into the system from the first cycle — they cannot be bolted on after the fact. A fourth architectural constraint is the sub-subagent limit: the Work Item Orchestrator cannot dispatch Builder, QA, and Git as independent subagents; all lifecycle steps must run inline in the orchestrator's own context window. This is confirmed in official Claude Code docs and drives the entire agent embedding strategy.

---

## Key Findings

### Recommended Stack

The Claude Agent SDK (Python, 0.1.73+) is the correct and only orchestration runtime. Do not use LangChain, LangGraph, CrewAI, or the bare Anthropic client SDK — these either require manual tool loops or add abstraction that conflicts with the SKILL.md format. Parallel dispatch uses `asyncio.gather()` with one coroutine per Work Item Orchestrator; no queue infrastructure is needed for MVP. Session IDs are persisted to `.claude/session_cache.json` for resume across CLI invocations.

Linear integration is via the official Linear MCP server (hosted, OAuth 2.1 or API key). All community alternatives are superseded and must not be used. Agent skills are defined as `.claude/agents/<name>.md` files (filesystem-based subagents) with YAML frontmatter. The existing `skills/` markdown files serve as authoritative content embedded in agent body sections; they are not themselves auto-discovery SKILL.md files.

**Core technologies:**
- **Claude Agent SDK (Python 0.1.73+):** Agent loop, subagent dispatch, MCP support — the only correct orchestration runtime
- **Linear Official MCP Server:** All Linear state reads/writes; first-party, OAuth 2.1, supersedes all community alternatives
- **GitHub CLI (`gh` 2.x+):** Branch creation, PR creation, stacked PR targeting via `--base`; `gh stack` for rebase cascade when available (private preview)
- **Python 3.12 + asyncio:** Runtime for CLI loop; `asyncio.gather()` for parallel Work Item Orchestrator dispatch
- **Filesystem agents (`.claude/agents/`):** Agent definitions as markdown with YAML frontmatter; runtime-agnostic and Codex-compatible
- **Flat markdown knowledge store (`knowledge/`):** Git-native, no vector DB, directly readable by agents; vector search deferred to Phase 3+
- **pydantic 2.x:** JSON contract validation for all agent input/output envelopes
- **typer 0.12+ + rich 13.x:** CLI loop interface with type-annotated commands and formatted terminal output

### Expected Features

**Must have (table stakes):**
- Work item hierarchy (EPIC → User Story → Task) persisted to Linear — structural foundation, all other agents depend on it
- Linear as sole system of record — all agent state transitions must appear as Linear comments; no hidden state
- Automated task → branch → stacked PR pipeline — core value; without this it is a chatbot, not a delivery system
- Stacked PR targeting (task PR targets EPIC branch; EPIC PR targets `main`) — correct from first PR creation, cannot be retrofitted
- QA agent review of every PR diff — non-negotiable gate; structured findings with blocking/non-blocking distinction
- Fix subtask generation from QA findings — closes the loop; hard cap at 5 subtasks per QA report
- Human approval gate — no auto-merge to `main` under any circumstances
- Structured agent contracts (JSON I/O schemas) — required for debuggable multi-agent handoffs; defined in `AGENT-CONTRACTS.md`
- CLI trigger mode (`run next step`) — manual assisted mode must exist before any automated loop
- Dependency awareness — Global Orchestrator must check `blocked-by` links before dispatch

**Should have (differentiators):**
- Three-level orchestration hierarchy (Main/Global/Work Item) — separates mode selection, readiness detection, and lifecycle management
- One-action-per-cycle constraint — trust-building feature; makes each tick observable and reversible
- UAT Agent — validates User Stories from user-acceptance perspective after QA approval
- Intelligence Agent + Knowledge Store — accumulates QA insights and architectural decisions across cycles
- Parallel execution mode — concurrent Work Item Orchestrators in isolated git worktrees
- Risk Agent — quality scoring and adaptive prioritization input to Global Orchestrator

**Defer (v2+):**
- Event-driven triggers (webhooks) — adds infra complexity before core loop is proven
- Real-time observability dashboards — Linear comments provide sufficient audit trail for v1
- ML-based risk prediction — requires training data that does not exist yet
- Multi-project knowledge sharing — not warranted at MVP scale
- Semantic search on Knowledge Store — flat directory + Glob/Grep is sufficient for MVP

### Architecture Approach

The system follows strict unidirectional data flow: CLI trigger → Main Orchestrator → Work Item Orchestrator → sequential inline steps (Intelligence → Builder → Git → QA → Linear). Linear is the only shared mutable state between concurrent agents. No agent writes to Linear directly except the Linear Agent; no agent mutates git except the Git Agent; no agent mutates the Knowledge Store except the Intelligence Agent. The critical sub-subagent constraint means the Work Item Orchestrator must embed all specialized skill content in its own system prompt and execute each lifecycle step as sequential tool use within its own context window — not by spawning further subagents.

**Major components:**
1. **Linear Agent** — sole writer of operational state; wraps all `mcp__linear__*` calls with contract validation
2. **Work Item Orchestrator** — drives one work item from `todo` to `done`; runs as multi-turn subagent with all lifecycle skill content embedded inline
3. **Global Orchestrator** — reads Linear state, detects EPIC phase, returns prioritized ready-work list respecting dependency graph
4. **Main Orchestrator** — entry point; selects cascade vs. parallel mode; claims tasks via optimistic-lock protocol before dispatch
5. **Builder Agent** — implements scoped code changes; no PR creation, no Linear writes
6. **Git Agent** — branch creation, commits, stacked PR targeting; reads `dependencies` and `branch_name` from Linear to compute correct PR base
7. **QA Agent** — reviews PR diff against requirements; produces structured findings contract; never merges
8. **CLI runtime loop (`run_loop.py`)** — thin Python script; each command is a standalone `asyncio.run()` call; state lives in Linear, not the process
9. **Knowledge Store (`knowledge/`)** — filesystem-based; date-sorted entries per category; no infrastructure dependencies

### Critical Pitfalls

1. **QA loop runaway** — Fix subtasks breed more fix subtasks indefinitely. Prevention: add `qa_cycle_count` to every Linear work item; enforce `max_qa_cycles = 3` hard limit; distinguish blocking from non-blocking findings; approve with tech-debt annotation when only non-blocking findings remain. Must be in the QA Agent skill spec before any automated QA execution.

2. **Double-claiming in parallel mode** — Two orchestrators both read `todo`, both write `in_progress`, second write silently wins, both implement the same task. Prevention: after writing `in_progress`, immediately re-read and confirm `assigned_orchestrator` matches this instance; abort if not. Linear MCP has no compare-and-swap — this optimistic lock is the only mitigation. Must be validated before Parallel Mode is enabled.

3. **Stacked PR base branch drift** — PR A merges into EPIC branch; PR B's base SHA is now stale; merge conflicts appear even when files are disjoint. Prevention: after every PR merge into the EPIC branch, trigger `REBASE_STACK` — rebase all remaining open task PRs targeting that EPIC branch and force-push. Must be designed into Git Agent before any parallel task execution.

4. **Sub-subagent constraint violation** — Work Item Orchestrator attempts to use the `Agent` tool to dispatch Builder, Git, QA as independent subagents. Claude Code explicitly prohibits this. Prevention: Work Item Orchestrator runs as a multi-turn agent with all skill content embedded inline; each lifecycle step executes as sequential tool use within its own context window.

5. **Context window exhaustion mid-lifecycle** — Builder accumulates context across QA cycles; auto-compaction loses original requirements; subsequent implementation diverges silently. Prevention: treat every agent invocation as stateless; pass full Linear issue content as explicit structured input on every invocation; use `context: fork` for Builder and QA to run them in isolated contexts.

---

## Implications for Roadmap

Based on the four-layer dependency order from ARCHITECTURE.md and phase warnings from PITFALLS.md, five phases are recommended.

### Phase 1: Foundation and Linear Integration
**Rationale:** Every other agent depends on Linear read/write working correctly and on typed contract envelopes. Build and validate these before any agent logic. Lowest-risk, highest-dependency layer.
**Delivers:** Linear Agent (create/update/comment/link), JSON contract schemas with pydantic validation, Knowledge Store directory structure, verified MCP connection to Linear.
**Addresses:** "Linear as system of record" and "Structured agent contracts" table-stakes features.
**Avoids:** Pitfall 4 (Linear state drift) — pre-flight `updatedAt` validation baked in from day one; Pitfall 6 (rate limit partial state) — exponential backoff and creation-order checkpoints implemented before any batch operations.

### Phase 2: Core Execution Agents (Backlog → Builder → Git → QA)
**Rationale:** These four agents form the minimum pipeline. Each is independently testable before the orchestrator wires them together. Build in dependency order: Backlog depends on Linear Agent; Builder depends on contracts; Git depends on Builder output and Linear Agent; QA depends on Git and Linear Agent.
**Delivers:** Backlog Agent (plan.md → EPIC/Story/Task hierarchy), Builder Agent (scoped implementation), Git Agent (stacked PR creation with correct `--base` logic), QA Agent (structured findings with blocking/non-blocking distinction).
**Addresses:** Automated task-to-branch-to-PR pipeline; QA gate; stacked PR targeting.
**Avoids:** Pitfall 3 (PR base drift) — Git Agent base-branch decision logic and `REBASE_STACK` trigger designed here; Pitfall 13 (fix subtask PR targeting) — `target_pr` field in fix contract enforced from first QA cycle.
**Research flag:** Git Agent stacked PR logic and `gh stack` availability warrant a phase-level deep-dive — `gh stack` is in private preview; manual `gh pr create --base` fallback must be production-ready.

### Phase 3: Work Item Orchestrator and Single-Cycle MVP
**Rationale:** Wire the Layer 2 agents into a complete lifecycle. Validate one full cycle (Task: `todo` → `done`) before adding orchestration above it. This is the MVP completion gate.
**Delivers:** Work Item Orchestrator (inline skill embedding, sequential lifecycle steps, `qa_cycle_count` termination logic), one complete end-to-end cycle in cascade mode, `run next step` CLI trigger.
**Addresses:** Work Item lifecycle management; CLI trigger mode; one-action-per-cycle constraint; fix subtask loop closure.
**Avoids:** Pitfall 2 (QA runaway) — `max_qa_cycles = 3` enforced in orchestrator skill spec; Pitfall 5 (context exhaustion) — stateless input contract with full Linear issue re-injection on each cycle; Pitfall 4 (sub-subagent violation) — inline embedding pattern validated here.
**Research flag:** Work Item Orchestrator inline skill embedding is architecturally novel and highest implementation risk — validate context budget against real task sizes before committing to this pattern.

### Phase 4: Global Orchestrator, Main Orchestrator, and Parallel Mode
**Rationale:** Parallel mode multiplies every bug in claiming and state-drift logic. Validate Global and Main Orchestrators in cascade mode first, then test claiming atomicity before enabling parallel dispatch.
**Delivers:** Global Orchestrator (prioritized ready-work list, dependency checking), Main Orchestrator (cascade/parallel dispatch), optimistic claiming protocol with re-read verification, git worktree isolation per parallel orchestrator, full parallel cycle test with 2 independent tasks.
**Addresses:** Parallel execution mode; dependency awareness; three-level orchestration hierarchy.
**Avoids:** Pitfall 1 (double-claiming) — claim-verify-proceed loop with `assigned_orchestrator` re-read confirmation; Pitfall 4 (stale state) — `updatedAt` optimistic lock on every pre-action read; parallel working-tree conflicts — `isolation: worktree` in agent frontmatter.
**Research flag:** Claiming atomicity in Linear MCP under concurrent writes is not documented — requires integration test against live Linear before parallel mode ships.

### Phase 5: Enhancement Agents (Intelligence, UAT, Risk)
**Rationale:** These agents add value but do not block the core delivery cycle. Intelligence and UAT are highest-value additions; Risk Agent is highest-complexity and lowest-urgency.
**Delivers:** Intelligence Agent (task enrichment from knowledge store, pattern persistence), UAT Agent (user-story validation gate with explicit scope boundary in input contract), Risk Agent (heuristic quality scores, adaptive prioritization input to Global Orchestrator).
**Addresses:** Persistent knowledge store; UAT validation loop; risk and adaptive prioritization differentiators.
**Avoids:** Pitfall 8 (UAT scope creep) — `scope_boundary` field and `acceptance_criterion_id` reference required in UAT input contract; Pitfall 9 (QA hallucinated findings) — Knowledge Store `architecture/` entries loaded by QA before generating findings; Pitfall 12 (knowledge pollution) — evidence fields required on every knowledge entry write.

### Phase Ordering Rationale

- Bottom-up dependency order is non-negotiable. Linear Agent is a dependency for 11 of 14 components — proving it correct first eliminates the largest source of systemic risk.
- Validate single-item cascade before parallel. Parallel mode multiplies every bug in claiming and state-drift logic. A complete cascade cycle is the only reliable proof that the base is correct.
- Enhancement agents last. Intelligence, UAT, and Risk add value on top of a working delivery loop. Building them before the loop is proven wastes effort and creates debugging noise.
- QA loop termination conditions must precede automated QA. The `max_qa_cycles` counter and blocking/non-blocking distinction cannot be retrofitted without changing the Linear state schema and QA contract simultaneously.

### Research Flags

Phases needing deeper research during planning:
- **Phase 2 (Git Agent):** `gh stack` private preview status — verify availability; document manual `gh pr create --base` fallback as the production path
- **Phase 3 (Work Item Orchestrator):** Inline skill embedding is architecturally novel — validate context budget against realistic task sizes before committing
- **Phase 4 (Claiming atomicity):** Linear MCP write ordering under concurrent access is undocumented — integration test required before parallel mode is enabled

Phases with standard patterns (skip research-phase):
- **Phase 1 (Linear Agent + contracts):** Linear MCP is official and well-documented; pydantic contract validation is a standard pattern
- **Phase 5 (Enhancement agents):** Follow the same agent-embedding pattern established in Phase 3; UAT and Intelligence patterns are well-documented

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All critical choices verified against official docs (Claude Agent SDK PyPI, Linear MCP changelog, GitHub CLI). Only `gh stack` availability is MEDIUM — private preview. |
| Features | HIGH | Grounded in project spec (`AGENTS.md`, `AGENT-CONTRACTS.md`) plus 2025-2026 agentic workflow literature. |
| Architecture | HIGH | Official Claude Code sub-agents docs confirm sub-subagent constraint; worktree isolation confirmed; component boundaries match project spec. |
| Pitfalls | MEDIUM-HIGH | Critical pitfalls (QA runaway, double-claiming, PR drift, context exhaustion) HIGH confidence from multiple sources. Moderate pitfalls draw from community sources at MEDIUM confidence. |

**Overall confidence:** HIGH

### Gaps to Address

- **`gh stack` availability:** Private preview as of April 2026. Plan `gh pr create --base` as the production path in Phase 2. Revisit `gh stack` at Phase 4 for rebase cascade automation.
- **Linear MCP tool enumeration:** Official docs do not publish the full tool list. Validate `update_issue` field names (especially custom fields like `assigned_orchestrator`, `qa_cycle_count`) against the actual MCP server during Phase 1.
- **Linear write ordering under concurrent access:** No documented guarantee. The optimistic-lock pattern is the recommended mitigation but requires integration testing before Phase 4 parallel mode ships.
- **Work Item Orchestrator context budget:** Inline embedding of Builder + Git + QA skill content in a single subagent context is novel. Real task sizes must be benchmarked against the 25,000-token re-attach budget during Phase 3 to confirm viability.
- **Custom Linear fields:** `assigned_orchestrator`, `qa_cycle_count`, `branch_name` may need to be stored as Linear custom fields or encoded in description/comments. Verify Linear custom field support via MCP during Phase 1.

---

## Sources

### Primary (HIGH confidence)
- [Claude Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview) — version, APIs, subagent dispatch
- [Claude Code sub-agents docs](https://code.claude.com/docs/en/sub-agents) — sub-subagent constraint confirmed, worktree isolation
- [Claude Code Skills documentation](https://code.claude.com/docs/en/skills) — SKILL.md frontmatter spec
- [Linear MCP server docs](https://linear.app/docs/mcp) — official setup, OAuth 2.1, API key auth
- [Linear MCP changelog](https://linear.app/changelog/2025-05-01-mcp) — launch date May 2025
- [Linear API Rate Limiting](https://linear.app/developers/rate-limiting) — 2,500 req/hr, 10,000-point query complexity cap
- [GitHub Stacked PRs (gh-stack)](https://github.github.com/gh-stack/) — official extension docs
- `agents/AGENTS.md`, `agents/AGENT-CONTRACTS.md`, `runtime/RUNTIME-EXECUTION.md`, `skills/` — PRIMARY project specifications

### Secondary (MEDIUM confidence)
- [GitHub InfoQ announcement](https://www.infoq.com/news/2026/04/github-stacked-prs/) — `gh stack` private preview status April 2026
- [Codex CLI Skills](https://developers.openai.com/codex/skills) — `.agents/skills/` path for Codex portability
- [Stacked PR workflow and conflict patterns](https://www.davepacheco.net/blog/2025/stacked-prs-on-github/) — base branch drift mechanics
- [AI Agent QA infinite loop prevention](https://www.fixbrokenaiapps.com/blog/ai-agents-infinite-loops) — `max_qa_cycles` pattern
- [Context window degradation](https://factory.ai/news/context-window-problem) — auto-compaction behavior

---
*Research completed: 2026-05-05*
*Ready for roadmap: yes*
