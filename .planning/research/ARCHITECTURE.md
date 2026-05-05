# Architecture Patterns

**Domain:** Multi-agent AI engineering workflow system
**Researched:** 2026-05-05
**Overall confidence:** HIGH — grounded in official Claude Code / Agent SDK docs verified May 2026

---

## Recommended Architecture

The system is a state-machine-driven multi-agent pipeline. Linear is the single durable state store. Agents are Claude Code subagents defined as markdown files. The runtime loop is a Python/TypeScript CLI that calls the Agent SDK `query()` function in a cycle.

```
Human / CLI trigger
        │
        ▼
  Main Orchestrator (Agent SDK query() call)
        │
        ├─ invokes ──► Global Orchestrator subagent
        │                    │ returns ready work item list
        │
        ├─ Cascade: invokes one Work Item Orchestrator subagent
        └─ Parallel: invokes N Work Item Orchestrator subagents concurrently
                          (each in an isolated git worktree)
                               │
                         ┌─────┴──────┐
                         │            │
                   Intelligence     Builder
                   subagent         subagent
                         │            │
                         └─────┬──────┘
                               │
                            Git subagent
                               │
                            QA subagent
                               │
                         Linear Agent subagent
                               │
                         (optional) UAT subagent
                               │
                         Knowledge Store (filesystem)
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| CLI runtime loop | Entry point, cycle control, `query()` calls | Main Orchestrator, Linear (for cycle reports) |
| Main Orchestrator | Mode selection (cascade/parallel), dispatch, claiming | Global Orchestrator, Work Item Orchestrators, Linear Agent |
| Global Orchestrator | Read Linear state, detect phase, return prioritized ready-work list | Linear Agent (read), Risk Agent (optional) |
| Work Item Orchestrator | Drive single work item through full lifecycle (implement → PR → QA → fix → done) | Intelligence, Builder, Git, QA, Linear agents |
| Backlog Agent | Transform plan.md into EPIC/Story/Task hierarchy | Linear Agent |
| Linear Agent | All Linear MCP reads and writes — sole writer of operational state | Linear MCP (`mcp__claude_ai_Linear__*`) |
| Builder Agent | Implement scoped code changes for one task; no PR, no Linear mutation | Repository filesystem, shell tools |
| Git Agent | Branch creation, commits, stacked PR creation via GitHub CLI | Git CLI, GitHub CLI (`gh`) |
| QA Agent | Review PR diff against requirements, produce structured findings | GitHub PR API (read), repository (read) |
| UAT Agent | Validate User Stories from user-value perspective after QA approval | Linear Agent (read), optional test environment |
| Intelligence Agent | Enrich work items with context; read and write Knowledge Store | Knowledge Store (filesystem), repository (read) |
| Risk Agent | Quality scoring, adaptive prioritization, improvement triggers | Linear Agent (read), Knowledge Store (read) |
| Knowledge Store | File-based long-term intelligence (`knowledge/` directory) | Intelligence Agent (read/write) |

**Key boundary rule:** No agent writes to Linear directly. All Linear state mutations go through the Linear Agent. This keeps the MCP credential and write-path isolated to one component.

---

## Data Flow

### Backlog creation flow

```
plan.md (filesystem)
  → Backlog Agent (reads file, produces structured JSON)
  → Linear Agent (persists EPIC/Story/Task hierarchy via MCP)
  → Linear (durable state)
```

### Work execution flow (per work item)

```
Linear state (read by Work Item Orchestrator)
  → Intelligence Agent (enrichment report — no state mutation)
  → Builder Agent (local code changes — no PR, no Linear write)
  → Git Agent (branch + commits + PR creation via gh CLI)
  → Linear Agent (link PR to work item, set status = in_review)
  → QA Agent (review diff, produce findings — no direct writes)
  → Linear Agent (persist QA status, create fix subtasks if needed)
  → [fix loop if QA fails: Global Orchestrator picks up fix subtasks]
  → Linear Agent (mark done on QA approval)
```

### State flows one direction at each boundary:
- Agent outputs are structured JSON (contract payloads)
- Only the Linear Agent mutates Linear state
- Only the Git Agent mutates branches and PRs
- Only the Intelligence Agent mutates the Knowledge Store
- Orchestrators read state; they never implement, review, or commit

### Parallel execution data flow

```
Main Orchestrator claims Task A, Task B, Task C in Linear (atomic writes)
  → spawns 3 Work Item Orchestrators concurrently
    each in its own git worktree (isolation: worktree)
    each writes to its own branch (feature/LIN-X-slug)
    each reads and writes Linear independently via Linear Agent subagent instances
  → PR-A targets EPIC branch
  → PR-B targets EPIC branch (independent tasks)
  → PR-C targets PR-A (if C depends on A, determined at claim time)
  → conflict resolution: human responsibility at EPIC PR merge
```

---

## Skill / Agent / Contract Relationship in Claude Code

### How skills map to Claude Code subagents

The `skills/` directory in this project contains operational procedures written as markdown. These are NOT Claude Code `SKILL.md` files (which live in `.claude/skills/`). They are the **system prompt content** that gets injected into subagent definitions.

**Implementation pattern:**

Each agent is a Claude Code subagent defined as a markdown file in `.claude/agents/`. The agent's frontmatter declares its tool access and model. The agent's body (system prompt) includes or references the relevant skill markdown.

```markdown
---
name: builder-agent
description: Implements scoped code changes for a task. Use when a work item is in_progress and needs implementation.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

[contents of skills/02-IMPLEMENTATION.md injected here]
```

**Contract enforcement:** The system prompt instructs the agent to expect a JSON contract envelope as input and to return a JSON contract envelope as output. The calling orchestrator validates the output structure before proceeding.

### Three implementation approaches for skills + agents

| Approach | Mechanism | Best for |
|----------|-----------|----------|
| Filesystem subagents (`.claude/agents/`) | Markdown files with YAML frontmatter; body = system prompt | Static agents used every project cycle |
| Programmatic subagents (Agent SDK `agents:` param) | `AgentDefinition` objects in `query()` call; prompt field = skill content read from file at runtime | Dynamic agents where prompt is assembled at invocation time |
| CLI flag subagents (`--agents` JSON) | Session-scoped; no file needed | Testing or one-off execution |

**Recommended for this system:** Filesystem-based agents (`.claude/agents/`) with skill content embedded in the body. Skill files remain in `skills/` as the authoritative source; the build process or setup script inlines them into agent files. This keeps skills tool-agnostic (Codex compatible) while giving Claude Code native subagent invocation.

### Constraint: subagents cannot spawn subagents

Claude Code subagents cannot invoke the `Agent` tool themselves. The orchestration hierarchy (Main → Work Item → specialized agent) must be flattened or handled differently:

**Solution:** Use agent teams or sequential invocation. The Main Orchestrator runs as the primary Claude Code session (not a subagent). It spawns Work Item Orchestrators as subagents. Work Item Orchestrators invoke specialized agents sequentially within their own context window — they do not spawn further subagents. Instead, each step is a direct `claude -p "..."` subprocess call with `--agent builder-agent` or equivalent, or the Work Item Orchestrator's prompt includes the skill content for each step inline.

**Practical pattern for Work Item Orchestrator:**

```
Work Item Orchestrator (subagent of Main Orchestrator)
  runs as a multi-turn agent with:
    - skill content for all sub-steps embedded in its system prompt
    - permission to use Linear MCP, Bash (for gh CLI, git), Read, Write, Edit
    - single work item ID as initial prompt
  executes each lifecycle step in sequence:
    1. read Linear state via MCP tools directly
    2. invoke builder logic (inline, not via sub-subagent)
    3. invoke git logic (via Bash + gh CLI)
    4. invoke QA logic (read PR diff via gh CLI, analyze inline)
    5. write results to Linear via MCP tools directly
```

This is the most viable pattern given the no-sub-subagent constraint.

---

## CLI Runtime Loop Implementation

### Structure

The CLI runtime loop is a Python script (`run_loop.py` or equivalent) that:

1. Reads execution mode (cascade/parallel) from config or user prompt
2. Calls `query()` with the Main Orchestrator's system prompt and current Linear state summary as input
3. The Main Orchestrator (running as primary session, not subagent) invokes the Agent tool to spawn Work Item Orchestrator subagents
4. Collects results
5. Reports cycle summary to Linear
6. Waits for human `run next step` command (manual mode) or loops automatically (CLI loop mode)

### Manual assisted mode (MVP)

```python
# Pseudocode
while True:
    user_input = input("run next step / show state / quit: ")
    if user_input == "run next step":
        result = query(
            prompt="Run one orchestration cycle. Read Linear state. Identify next action. Execute it. Report result.",
            options=ClaudeAgentOptions(
                agents={"work-item-orchestrator": work_item_orchestrator_def},
                allowed_tools=["Agent", "mcp__claude_ai_Linear__*", "Bash", "Read"]
            )
        )
        print_cycle_summary(result)
```

### CLI loop mode

Same structure but cycles automatically. Human inspects Linear between cycles. The `max_turns` parameter on the Main Orchestrator query controls runaway protection.

### Parallel mode

When Main Orchestrator returns a list of ready items, the CLI runtime calls `query()` once with a prompt that instructs parallel dispatch. The Main Orchestrator uses the `Agent` tool multiple times — Claude Code handles actual concurrency at the Agent tool level. Each subagent gets `isolation: worktree` to prevent file conflicts.

---

## Linear MCP State Structure for Multi-Agent Access

### Linear as the coordination bus

Linear is the only shared mutable state between concurrent agents. This makes correct state structure critical for parallel safety.

### Required fields on every work item

```json
{
  "work_item_id": "LIN-123",
  "type": "task",
  "status": "todo | in_progress | blocked | in_review | done",
  "qa_status": "not_required | pending | approved | changes_required",
  "uat_status": "not_required | pending | approved | changes_required",
  "parent_id": "LIN-100",
  "epic_id": "LIN-100",
  "dependencies": ["LIN-101"],
  "pr_links": ["https://github.com/..."],
  "assigned_orchestrator": "work_item_orchestrator_instance_id",
  "branch_name": "feature/LIN-123-slug"
}
```

`assigned_orchestrator` and `branch_name` are the two fields that enable parallel safety — they are written atomically at claim time before any work begins.

### Claim protocol (parallel mode safety)

```
1. Read task status from Linear
2. If status != "todo" → ABORT (claimed by another orchestrator)
3. Write: status = "in_progress", assigned_orchestrator = <this_instance>
4. Re-read to confirm write succeeded with correct assigned_orchestrator
5. Only then begin work
```

This is an optimistic lock. Linear MCP does not provide compare-and-swap, so the re-read confirmation is required. Race condition probability is low in practice because Global Orchestrator runs before dispatch and provides a pre-filtered list.

### Linear as memory

Agents store all intermediate results as Linear comments on the relevant issue, not in local files or agent context. After a Builder Agent finishes, it writes implementation notes to a Linear comment on the task before the Git Agent is invoked. This ensures any subsequent agent starts from Linear state, not ephemeral context.

---

## Stacked PR / Branch Naming Strategy

### Branch naming

```
EPIC branch:    epic/LIN-100-feature-name
Task branches:  feature/LIN-123-short-slug
Fix branches:   fix/LIN-456-fix-slug
```

Branch names are deterministic from the Linear issue ID. Git Agent derives the slug from the issue title, normalizes to lowercase with hyphens, truncates to 40 characters.

### PR stacking rules

```
main
  └── epic/LIN-100-feature-name (EPIC branch — manual merge only)
        ├── feature/LIN-123-task-one → PR targets epic branch
        ├── feature/LIN-124-task-two → PR targets epic branch (independent)
        └── feature/LIN-125-task-three → PR targets feature/LIN-123 (depends on LIN-123)
```

**Base branch decision logic (Git Agent):**
1. No declared dependency on another task → base = EPIC branch
2. Declared dependency on task N → base = task N's branch (read from Linear `branch_name` field)
3. Fix subtask → base = the original task's PR branch (read from Linear `pr_links`)

### Parallel mode branch safety

Each parallel Work Item Orchestrator:
1. Reads EPIC branch HEAD at claim time
2. Creates its task branch from that HEAD
3. Registers the branch name in Linear before first commit
4. Never accesses another orchestrator's working tree

Conflicts are surfaced at EPIC PR merge time and resolved by the human. Agents report detected conflicts as Linear blockers and stop.

---

## Suggested Build Order

Dependencies drive the order. Components with no upstream dependencies go first; components that consume others go later.

### Layer 1 — Foundation (no dependencies)

**Build these first:**

1. **Linear Agent** (skills/05-LINEAR-SYSTEM-OF-RECORD.md → `.claude/agents/linear-agent.md`)
   - All other agents depend on this for state read/write
   - Simplest agent: wraps MCP tool calls with contract validation
   - Test: create/read/update a test issue in Linear

2. **Contract schemas and envelope validation**
   - JSON schemas for all input/output contracts (from AGENT-CONTRACTS.md)
   - Shared validation library used by all agents
   - Test: validate sample payloads against schemas

3. **Knowledge Store directory structure** (`knowledge/` hierarchy)
   - Filesystem layout: `knowledge/architecture/`, `knowledge/qa/`, `knowledge/patterns/`
   - No agent logic yet — just the storage contract
   - Test: write and read a sample knowledge entry

### Layer 2 — Core execution agents (depend on Layer 1)

4. **Backlog Agent** (skills/01-BACKLOG-PLANNING.md → `.claude/agents/backlog-agent.md`)
   - Depends on: Linear Agent
   - Test: feed `docs/plan.md`, confirm EPIC/Story/Task hierarchy appears in Linear

5. **Builder Agent** (skills/02-IMPLEMENTATION.md → `.claude/agents/builder-agent.md`)
   - Depends on: repository filesystem access, contract schemas
   - Test: provide a trivial implementation task, confirm files change, contract output is valid

6. **Git Agent** (skills/04-GIT-PR-MANAGEMENT.md → `.claude/agents/git-agent.md`)
   - Depends on: Builder Agent output, Linear Agent (for branch registration)
   - Test: create a branch from EPIC, open a stacked PR, confirm base is correct

7. **QA Agent** (skills/03-QA-REVIEW.md → `.claude/agents/qa-agent.md`)
   - Depends on: Git Agent (PR must exist), Linear Agent (for issue context)
   - Test: point at a real PR diff, confirm findings contract output is valid

### Layer 3 — Orchestration (depend on Layer 2)

8. **Work Item Orchestrator** (skills/06-TASK-ORCHESTRATION.md → `.claude/agents/work-item-orchestrator.md`)
   - Depends on: all Layer 2 agents
   - Contains lifecycle decision logic + sequential invocation of Layer 2 agents
   - Test: run one full Task lifecycle from `todo` → `done` with a real issue

9. **Global Orchestrator** (skills/07-GLOBAL-ORCHESTRATION.md → `.claude/agents/global-orchestrator.md`)
   - Depends on: Linear Agent, Work Item Orchestrator
   - Test: confirm it correctly identifies ready tasks, respects dependency graph, signals blocked states

### Layer 4 — Runtime and entry point (depend on Layer 3)

10. **CLI runtime loop** (`run_loop.py` or `runtime/main.ts`)
    - Depends on: Main Orchestrator, Global Orchestrator, Agent SDK
    - Implements: manual mode → CLI loop mode progression
    - Test: run full MVP cycle (`run next step` × N) against a seeded Linear project

11. **Main Orchestrator** (skills/00-MAIN-ORCHESTRATOR.md → `.claude/agents/main-orchestrator.md`)
    - Depends on: Global Orchestrator, Work Item Orchestrator
    - Implements: cascade and parallel dispatch with claiming
    - Test: cascade mode first (one task at a time), then parallel mode with 2 independent tasks

### Layer 5 — Enhancement agents (depend on Layers 1-4 but don't block MVP)

12. **Intelligence Agent** (skills/10 + 11 → `.claude/agents/intelligence-agent.md`)
    - Depends on: Knowledge Store, Builder/QA agent handoffs
    - Test: enrich a task with knowledge context, confirm Builder uses it

13. **UAT Agent** (skills/08-UAT-VALIDATION.md → `.claude/agents/uat-agent.md`)
    - Depends on: QA Agent approval, Linear Agent
    - Test: validate a User Story after QA approval

14. **Risk Agent** (skills/12 + 13 + 14 → `.claude/agents/risk-agent.md`)
    - Depends on: Linear Agent, Intelligence Agent, observability data
    - Test: produce quality scores and a prioritized queue from sample QA history

### Build order summary table

| Order | Component | Depends On | Blocks MVP? |
|-------|-----------|-----------|-------------|
| 1 | Linear Agent | nothing | YES |
| 2 | Contract schemas | nothing | YES |
| 3 | Knowledge Store layout | nothing | no |
| 4 | Backlog Agent | Linear Agent | YES |
| 5 | Builder Agent | contracts | YES |
| 6 | Git Agent | Builder, Linear Agent | YES |
| 7 | QA Agent | Git Agent, Linear Agent | YES |
| 8 | Work Item Orchestrator | Builder, Git, QA, Linear agents | YES |
| 9 | Global Orchestrator | Linear Agent, Work Item Orchestrator | YES |
| 10 | CLI runtime loop | Global Orchestrator, Agent SDK | YES |
| 11 | Main Orchestrator | Global Orchestrator, Work Item Orchestrator | YES (parallel mode) |
| 12 | Intelligence Agent | Knowledge Store, Builder | no |
| 13 | UAT Agent | QA Agent, Linear Agent | no |
| 14 | Risk Agent | Linear Agent, Intelligence Agent | no |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Agents writing Linear state directly
**What:** Builder, QA, or Git agents call Linear MCP tools without going through the Linear Agent
**Why bad:** Bypasses contract validation, creates hidden write paths, makes state audit impossible
**Instead:** All MCP calls route through the Linear Agent contract

### Anti-Pattern 2: Subagents spawning subagents
**What:** Work Item Orchestrator attempts to use the `Agent` tool to spawn Builder, Git, and QA as sub-subagents
**Why bad:** Claude Code explicitly prohibits this — subagents cannot spawn subagents
**Instead:** Work Item Orchestrator runs as a multi-turn agent with all skill content embedded inline; specialized logic runs within its own context window sequentially

### Anti-Pattern 3: State in agent context only
**What:** Builder Agent stores implementation notes in its context window and passes them to Git Agent via the contract without persisting to Linear first
**Why bad:** If the cycle fails between Builder and Git, the notes are lost; subsequent agents start blind
**Instead:** Every significant intermediate result is written to Linear as a comment before the next agent is invoked

### Anti-Pattern 4: EPIC-wide implementation in one orchestrator cycle
**What:** Work Item Orchestrator tries to implement, PR, and QA all three tasks of an EPIC in one pass
**Why bad:** Violates the one-action-per-cycle rule; creates untraceable side effects; oversized agent context
**Instead:** Each cycle handles one lifecycle step for one work item

### Anti-Pattern 5: Parallel agents sharing a working tree
**What:** Two Work Item Orchestrators both check out changes in the main repository working directory
**Why bad:** File conflicts; non-deterministic outcomes; silent overwrites
**Instead:** Each parallel orchestrator operates in its own git worktree (`isolation: worktree` in agent frontmatter)

### Anti-Pattern 6: Hardcoded branch base logic
**What:** Git Agent always targets the EPIC branch regardless of declared task dependencies
**Why bad:** Breaks the stacked PR chain; PRs can't be merged in order; dependency graph is ignored
**Instead:** Git Agent reads `dependencies` and `branch_name` from Linear state to determine the correct base

---

## Scalability Considerations

| Concern | Cascade mode (1 task/cycle) | Parallel mode (N tasks/cycle) |
|---------|----------------------------|-------------------------------|
| Linear write contention | None (sequential) | Low — each task has unique ID; claims are independent writes |
| Git working tree conflicts | None | Eliminated by worktree isolation |
| Context window per agent | Small (one task in scope) | Small (each orchestrator is isolated) |
| PR review burden | One PR per cycle | N PRs per cycle — human reviews N PRs before next EPIC dispatch |
| Fix loop amplification | Linear — one task creates max 5 fix subtasks | Multiplicative — N tasks could each create up to 5 fix subtasks (max 5N) |
| MVP safety | High — easy to inspect and stop | Lower — requires claiming logic to be correct |

**Recommendation:** Start with cascade mode. Add parallel mode after the full cascade cycle is validated end-to-end.

---

## Sources

- [Claude Code subagents documentation](https://code.claude.com/docs/en/sub-agents) — HIGH confidence (official docs, May 2026)
- [Claude Agent SDK subagents](https://code.claude.com/docs/en/agent-sdk/subagents) — HIGH confidence (official docs, May 2026)
- [Claude Agent SDK skills](https://code.claude.com/docs/en/agent-sdk/skills) — HIGH confidence (official docs, May 2026)
- [Claude Code worktrees](https://code.claude.com/docs/en/worktrees) — HIGH confidence (official docs, May 2026)
- [agents/AGENTS.md](../agents/AGENTS.md) — PRIMARY SOURCE (project spec)
- [agents/AGENT-CONTRACTS.md](../agents/AGENT-CONTRACTS.md) — PRIMARY SOURCE (project spec)
- [runtime/RUNTIME-EXECUTION.md](../runtime/RUNTIME-EXECUTION.md) — PRIMARY SOURCE (project spec)
- [skills/06-TASK-ORCHESTRATION.md](../skills/06-TASK-ORCHESTRATION.md) — PRIMARY SOURCE (project spec)
- [skills/07-GLOBAL-ORCHESTRATION.md](../skills/07-GLOBAL-ORCHESTRATION.md) — PRIMARY SOURCE (project spec)
