# Phase 3: Work Item Orchestrator and Single-Cycle MVP — Research

**Researched:** 2026-05-05
**Domain:** Claude Agent SDK single-session orchestration, Typer CLI extension, rich terminal output, SKILL.md migration
**Confidence:** HIGH (all critical patterns verified against Context7 official SDK docs; library versions confirmed against PyPI registry; runtime environment probed directly)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Work Item Orchestrator Architecture**
- D-01: The Work Item Orchestrator is implemented as a single Claude Agent SDK session. At startup, Python reads all relevant skill files (`06-TASK-ORCHESTRATION`, `02-IMPLEMENTATION`, `03-QA-REVIEW`, `04-GIT-PR-MANAGEMENT`, `05-LINEAR-SYSTEM-OF-RECORD`) and injects their content into the system prompt. The agent drives the full lifecycle via sequential tool use within that one context window. No sub-agent spawning, no sub-subagent dispatch (WORC-02).
- D-02: Context budget validation is NOT a separate pre-flight step. The MVP benchmark cycle (a real Linear task against the hsb-test-fixture repo) IS the context validation. Successful completion validates the architecture; context pressure during the run signals need to trim skill content before Phase 4.

**Lifecycle Sequence**
- D-03: Phase 3 lifecycle is: Linear read → Builder → Git → QA → fix loop → done. The Intelligence step is skipped entirely in Phase 3. No stub, no placeholder. Phase 5 inserts Intelligence before Builder when it ships.

**QA Fix Loop Behavior**
- D-04: When QA returns `changes_required`, the orchestrator exits after creating fix subtasks. Linear state is updated (`qa_status = changes_required`, task status signals blocked). Human re-triggers with `hsb run-next-step`. On next trigger, orchestrator reads fix subtasks from Linear, passes them to Builder as new scope, and loops: Builder → Git → QA again. Each fix cycle is its own orchestration cycle.
- D-05: QA cycle cap enforcement is layered: Layer 1 (QA Agent — Phase 2 D-05): at `qa_cycle_count >= 3`, QA Agent approves with tech-debt annotation rather than requesting further fixes. Layer 2 (Work Item Orchestrator — safety net): if `qa_cycle_count >= 3` AND `qa_status` is still `changes_required` (shouldn't happen normally), the orchestrator posts a structured Linear comment ("Max QA cycles reached. Escalating to human. Task status: blocked.") and exits. Never initiates a 4th fix cycle (WORC-03).

**CLI Interface**
- D-06: Phase 3 CLI commands extend the existing Typer CLI at `src/hsb/cli/main.py`. Three new subcommands: `hsb run-next-step`, `hsb show-state`, `hsb show-next-action`.
- D-07: `run_loop.py` is a thin wrapper script at the repo root that calls `hsb run-next-step` in a loop. Stops when no `todo`-status tasks remain in Linear or when operator interrupts with Ctrl+C. Each loop iteration is a standalone `asyncio.run()` invocation — no process-level state (CLIR-05).
- D-08: `show-state` output uses `rich` (already in Phase 1 dependencies). Table format: EPIC / Task / Status / QA Status / QA Cycle Count / PR Link.

### Claude's Discretion

- SKILL.md migration: The Work Item Orchestrator skill (`skills/06-TASK-ORCHESTRATION.md`) should be migrated to `.claude/skills/task-orchestration/SKILL.md` during Phase 3, following the pattern established in Phases 1 and 2.
- Skill injection order: Exact ordering of skill content in the system prompt (e.g., task-orchestration first as the "meta-skill" framing the others, or interleaved by lifecycle step) — Claude decides.
- `run_loop.py` stopping condition: Exact Linear query to detect "no ready tasks" (e.g., filter by `todo` status in the current EPIC's scope) — Claude decides based on what keeps the Linear MCP call minimal.
- WORC-05 output persistence: Exact structure of the lifecycle status summary posted as a Linear comment after each cycle — Claude decides, following the output contract in `agents/AGENT-CONTRACTS.md`.

### Deferred Ideas (OUT OF SCOPE)

- Global Orchestrator for ready-task detection — Phase 4; Phase 3 uses a direct Linear query in `run_loop.py`
- Parallel mode dispatch — Phase 4 (explicitly gated on validated cascade cycle from Phase 3)
- Intelligence Agent lifecycle step — Phase 5; Phase 3 lifecycle starts at Builder
- `gh stack` integration — not implemented in any phase (Phase 2 D-06, permanently deferred)
- Dry-run / simulation mode — out of scope per REQUIREMENTS.md
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WORC-01 | Work Item Orchestrator drives a single work item from `todo` to `done` through the full lifecycle | Single SDK session + `query()` with injected system prompt; Phase 2 agents called as SDK in-process tools |
| WORC-02 | Work Item Orchestrator embeds all lifecycle skill content inline (no sub-subagent dispatch) and executes each lifecycle step as sequential tool use within its own context window | `system_prompt` param on `ClaudeAgentOptions`; `create_sdk_mcp_server` + `@tool` for Phase 2 Python modules |
| WORC-03 | Work Item Orchestrator tracks `qa_cycle_count` and enforces `max_qa_cycles = 3` termination; escalates to human if hard limit is reached without approval | D-05 layered enforcement: QA Agent tech-debt annotation (primary) + orchestrator safety-net check (secondary) |
| WORC-04 | Every agent invocation by the Work Item Orchestrator passes the full Linear issue content as structured input — no reliance on conversation memory | Full Linear issue read fresh from MCP at each cycle start; passed as structured JSON in tool call arguments |
| WORC-05 | Work Item Orchestrator outputs a lifecycle status summary and persists it to Linear as a comment on the work item | `mcp__linear__create_comment` via Linear Agent service; JSON structure defined by AGENT-CONTRACTS.md §3 |
| CLIR-01 | Operator can trigger a single orchestration cycle with `run next step` from the command line | `hsb run-next-step` Typer subcommand wrapping `asyncio.run(run_orchestration_cycle(...))` |
| CLIR-02 | Operator can view the current system state (Linear phase, EPIC status, ready tasks) with `show current state` | `hsb show-state` Typer subcommand; rich Table with 5 columns; reads Linear state read-only |
| CLIR-03 | Operator can inspect the next recommended action without executing it with `show next action` | `hsb show-next-action` Typer subcommand; produces decision envelope JSON without side effects |
| CLIR-04 | Operator can run a continuous CLI loop (`python run_loop.py`) that repeats orchestration cycles until no ready tasks remain or operator interrupts | `run_loop.py` at repo root; `while True` loop calling `hsb run-next-step`; Linear `list_issues` query as termination condition |
| CLIR-05 | Each CLI command is a standalone `asyncio.run()` invocation — state lives in Linear, not in the CLI process | `asyncio.run(main_coroutine())` in each Typer command handler; no process-level cache or global state |
</phase_requirements>

---

## Summary

Phase 3 wires the Phase 2 execution agents into a complete orchestrated lifecycle and proves the architecture with a real end-to-end cycle. The central implementation concern is the single-session orchestrator: one `query()` call on `ClaudeAgentOptions` with all five skill files concatenated into the `system_prompt` string and four Python tool functions (wrapping the Phase 2 agent modules) registered via `create_sdk_mcp_server`. The orchestrator does not spawn sub-agents — it uses sequential tool calls within one context window to drive the full lifecycle.

The verified SDK pattern is `ClaudeAgentOptions(system_prompt=<full skill content>, mcp_servers={"agents": sdk_server})` where `sdk_server` is created with `create_sdk_mcp_server()` and exposes `@tool`-decorated async Python functions. These functions call into the Phase 2 agent Python modules (`builder_agent.py`, `git_agent.py`, `qa_agent.py`, `linear_agent.py`). This pattern is the authoritative way to expose Python functions as tools within a single SDK session — confirmed against Context7 official docs.

The CLI layer is a straightforward Typer extension: three new `@app.command()` functions added to the existing `src/hsb/cli/main.py`, each calling `asyncio.run()` over an async coroutine. The `run_loop.py` wrapper is a thin Python script at repo root, not a Typer app itself. The `show-state` command renders a rich `Table` with `Console().print(table)`.

Context budget is validated empirically through the MVP benchmark run — not by a preflight token count. Four skill files × ~2000 tokens each ≈ 8,000 tokens of system prompt overhead, which is well within Claude's context window. The real budget risk is not the system prompt but the accumulation of tool call outputs (PR diffs, Linear issue content) mid-session.

**Primary recommendation:** Build the orchestrator as a thin `work_item_orchestrator.py` in `src/hsb/agents/` that assembles the system prompt from skill files, creates the in-process MCP server with four tool wrappers, and runs a single `query()` call. The CLI commands are thin Typer wrappers over this function. Integration test: one real Linear task in hsb-test-fixture from `todo` to `done`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Lifecycle orchestration decision logic | API / Backend (Work Item Orchestrator) | — | LLM within single SDK session decides which lifecycle step to execute next based on Linear state read via tool call |
| Builder execution | API / Backend (builder_agent.py via SDK tool) | — | Orchestrator calls `run_builder` tool; builder_agent.py is invoked as in-process function, not sub-agent |
| Git/PR creation | API / Backend (git_agent.py via SDK tool) | — | Orchestrator calls `run_git` tool; git_agent.py executes `gh` CLI operations |
| QA review | API / Backend (qa_agent.py via SDK tool) | — | Orchestrator calls `run_qa` tool; qa_agent.py fetches PR diff and produces findings contract |
| Linear state reads | API / Backend (Linear Agent service) | — | Orchestrator reads Linear fresh at cycle start via `run_linear` tool wrapping linear_agent.py |
| Linear state writes | API / Backend (Linear Agent service) | — | All Linear writes (status update, comment, PR link) flow through linear_agent.py, never direct MCP |
| CLI command dispatch | CLI tier (Typer `src/hsb/cli/main.py`) | — | Three new `@app.command()` functions; no business logic at CLI tier |
| Continuous loop driver | CLI tier (run_loop.py at repo root) | — | Thin `while True` wrapper calling subprocess `hsb run-next-step`; loop termination via Linear query |
| State table display | CLI tier (rich Console/Table) | — | `show-state` formats Linear data; no writes, pure read-and-render |
| SKILL.md meta-skill for orchestration | API / Backend (system prompt injection) | — | `skills/06-TASK-ORCHESTRATION.md` content read at startup and injected inline; not auto-discovered via `.claude/skills/` |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `claude-agent-sdk` | 0.1.73 | Single-session orchestrator runtime; `query()`, `ClaudeAgentOptions`, `create_sdk_mcp_server`, `@tool` | Project-locked (STACK.md); verified latest on PyPI 2026-05-05 |
| `pydantic` | 2.13.3 | Input/output contract validation for Work Item Orchestration Contract (AGENT-CONTRACTS.md §3) | Project-locked (STACK.md); matches Phase 1/2 contracts |
| `typer` | 0.25.1 | CLI subcommand registration; extends existing `src/hsb/cli/main.py` | Project-locked (STACK.md); current PyPI 2026-05-05 |
| `rich` | 15.0.0 | `Table` + `Console` for `show-state` output | Project-locked (STACK.md); current PyPI 2026-05-05; 13.7.1 installed system-wide |
| `asyncio` (stdlib) | Python 3.12 built-in | `asyncio.run()` in each CLI command handler; no persistent process state | Project-locked (CLIR-05) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-dotenv` | 1.0+ | Load `ANTHROPIC_API_KEY` from `.env` for SDK | Required for SDK authentication in non-CI environments |
| `anyio` | bundled with claude-agent-sdk | Async event loop provider for `query()` | Used internally by SDK; also acceptable in place of `asyncio.run()` for test harnesses |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `create_sdk_mcp_server` + `@tool` for Phase 2 modules | `AgentDefinition` + sub-agent dispatch via `Task` tool | Sub-agents (AgentDefinition) spawn separate SDK sessions — violates D-01 (single session, no sub-subagent dispatch) |
| Single `query()` for the full lifecycle | `ClaudeSDKClient` multi-turn session | `ClaudeSDKClient` is for interactive bidirectional sessions; `query()` is the correct primitive for one autonomous lifecycle run |
| Inline `asyncio.run()` in CLI handlers | `anyio.run()` | Both work; `asyncio.run()` is stdlib and matches the project's CLIR-05 "standalone invocation" pattern |

**Installation:**

```bash
pip install "claude-agent-sdk==0.1.73" "pydantic>=2.13" "typer>=0.25" "rich>=15" "python-dotenv>=1"
```

**Version verification:** Confirmed against PyPI registry on 2026-05-05.
- `claude-agent-sdk`: 0.1.73 is current latest [VERIFIED: pip index versions]
- `typer`: 0.25.1 is current latest [VERIFIED: pip index versions]
- `rich`: 15.0.0 is current latest (13.7.1 installed system-wide) [VERIFIED: pip index versions]
- `pydantic`: 2.13.3 is current latest [VERIFIED: pip index versions]

---

## Architecture Patterns

### System Architecture Diagram

```
CLI trigger: hsb run-next-step
        |
        v
[Typer CLI — main.py]
 asyncio.run(run_orchestration_cycle(work_item_id))
        |
        v
[work_item_orchestrator.py]
 1. Read skill files → assemble system_prompt string
    (06-TASK-ORCHESTRATION + 02-IMPLEMENTATION +
     03-QA-REVIEW + 04-GIT-PR-MANAGEMENT +
     05-LINEAR-SYSTEM-OF-RECORD)
 2. Create in-process MCP server with @tool wrappers:
    - run_linear_op(operation, payload) → linear_agent.py
    - run_builder(work_item_id, issue_content) → builder_agent.py
    - run_git(work_item_id, impl_output) → git_agent.py
    - run_qa(work_item_id, pr_url, diff) → qa_agent.py
 3. query(prompt=<work_item_id + trigger>,
          options=ClaudeAgentOptions(
            system_prompt=<assembled skill content>,
            mcp_servers={"agents": sdk_server,
                         "linear": linear_mcp_remote},
            allowed_tools=["mcp__agents__run_linear_op",
                           "mcp__agents__run_builder",
                           "mcp__agents__run_git",
                           "mcp__agents__run_qa",
                           "mcp__linear__*"],
            permission_mode="acceptEdits",
            max_turns=30))
        |
        v
[Claude Agent (single session context window)]
  reads Linear state → decides lifecycle step →
  calls tool → receives result → calls next tool →
  ...until qa_approved or exit condition
        |
     tool calls
     |    |    |    |
     v    v    v    v
[linear] [builder] [git] [qa]
 Phase 2 agent Python modules
 (imported in-process via @tool wrappers)
        |
        v
[Linear MCP server — mcp-remote]
 mcp__linear__get_issue, update_issue,
 create_comment, create_issue
        |
        v
[Linear workspace — system of record]
  qa_status, qa_cycle_count, pr_link,
  lifecycle status comment persisted
```

**read-only parallel path:**
```
CLI: hsb show-state
        |
        v
[Typer CLI — main.py]
 asyncio.run(fetch_linear_state()) → rich Table render
        |
        v
[Linear MCP — list_issues, get_issue]
 read-only: EPIC + all child Tasks with status fields
```

**loop driver path:**
```
run_loop.py (repo root)
  while True:
    subprocess.run(["hsb", "run-next-step"])
    asyncio.run(check_ready_tasks())  → mcp__linear__list_issues
    if no todo tasks: break
    Ctrl+C: break
```

### Recommended Project Structure

```
src/hsb/
├── agents/
│   ├── linear_agent.py     # Phase 1 — used as tool implementation
│   ├── builder_agent.py    # Phase 2 — called by orchestrator via @tool
│   ├── git_agent.py        # Phase 2 — called by orchestrator via @tool
│   ├── qa_agent.py         # Phase 2 — called by orchestrator via @tool
│   └── work_item_orchestrator.py   # Phase 3 NEW
├── contracts/
│   ├── linear.py           # Phase 1
│   ├── builder.py          # Phase 2
│   ├── git.py              # Phase 2
│   ├── qa.py               # Phase 2
│   └── orchestrator.py     # Phase 3 NEW — WorkItemOrchInput, WorkItemOrchOutput
├── cli/
│   └── main.py             # Phase 1 — extend with 3 new subcommands
run_loop.py                 # Phase 3 NEW — repo root thin wrapper
.claude/skills/
└── task-orchestration/
    └── SKILL.md            # Phase 3 NEW — migrated from skills/06-TASK-ORCHESTRATION.md
```

### Pattern 1: Single-Session Orchestrator with Inline Skill Injection

**What:** Read all skill files at startup, concatenate into one `system_prompt` string, create an in-process MCP server exposing Phase 2 agent modules as tools, run a single `query()` call.

**When to use:** Always — this is the locked architecture (D-01).

**Example:**

```python
# Source: Context7 /anthropics/claude-agent-sdk-python — Custom Tools with SDK MCP Servers
# + ClaudeAgentOptions Configuration

import asyncio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions, create_sdk_mcp_server, tool
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

SKILL_FILES = [
    "skills/06-TASK-ORCHESTRATION.md",
    "skills/02-IMPLEMENTATION.md",
    "skills/03-QA-REVIEW.md",
    "skills/04-GIT-PR-MANAGEMENT.md",
    "skills/05-LINEAR-SYSTEM-OF-RECORD.md",
]

def assemble_system_prompt() -> str:
    parts = []
    for path in SKILL_FILES:
        content = Path(path).read_text()
        parts.append(f"# SKILL: {Path(path).stem}\n\n{content}")
    return "\n\n---\n\n".join(parts)

@tool("run_builder", "Execute the Builder Agent for a work item",
      {"work_item_id": str, "issue_content": dict})
async def run_builder_tool(args: dict) -> dict:
    from src.hsb.agents.builder_agent import run_builder_agent
    result = await run_builder_agent(args["work_item_id"], args["issue_content"])
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}

# ... similar @tool wrappers for run_git, run_qa, run_linear_op

async def run_orchestration_cycle(work_item_id: str) -> None:
    system_prompt = assemble_system_prompt()
    sdk_server = create_sdk_mcp_server(
        name="agents",
        version="1.0.0",
        tools=[run_builder_tool, run_git_tool, run_qa_tool, run_linear_tool],
    )
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        mcp_servers={
            "agents": sdk_server,
            "linear": {"command": "npx", "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"]},
        },
        allowed_tools=[
            "mcp__agents__run_builder",
            "mcp__agents__run_git",
            "mcp__agents__run_qa",
            "mcp__agents__run_linear_op",
            "mcp__linear__get_issue",
            "mcp__linear__list_issues",
            "mcp__linear__update_issue",
            "mcp__linear__create_comment",
        ],
        permission_mode="acceptEdits",
        max_turns=30,
    )
    async for message in query(
        prompt=f"Run the work item lifecycle for work item {work_item_id}. "
               f"Read its current Linear state first, then execute the next appropriate lifecycle step.",
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            print(f"Session complete. Cost: ${message.total_cost_usd:.4f}")
```

### Pattern 2: Typer Async Command Handler

**What:** Typer command handlers are synchronous; wrap async work with `asyncio.run()`.

**When to use:** All three new CLI subcommands.

**Example:**

```python
# Source: Context7 /fastapi/typer — Create Multi-Command CLI with typer.Typer()
# + stdlib asyncio.run() pattern (CLIR-05)

import asyncio
import typer
from src.hsb.agents.work_item_orchestrator import run_orchestration_cycle
from src.hsb.cli.state import fetch_linear_state_table

app = typer.Typer(name="hsb")  # existing app from Phase 1

@app.command("run-next-step")
def run_next_step(
    work_item_id: str = typer.Option(None, help="Linear work item ID (e.g. LIN-42). If omitted, selects next todo task.")
) -> None:
    """Trigger one orchestration cycle — a single work item progresses exactly one lifecycle step."""
    asyncio.run(run_orchestration_cycle(work_item_id))

@app.command("show-state")
def show_state() -> None:
    """Render current system state: EPICs, tasks, QA status, PR links."""
    asyncio.run(_render_state())

@app.command("show-next-action")
def show_next_action() -> None:
    """Display next recommended action without executing it."""
    asyncio.run(_render_next_action())
```

### Pattern 3: Rich Table for show-state

**What:** Instantiate `Table`, define 5 columns, add rows from Linear state, print via `Console`.

**When to use:** `hsb show-state` command (CLIR-02, D-08).

**Example:**

```python
# Source: Context7 /textualize/rich — Create and Print a Rich Table

from rich.console import Console
from rich.table import Table

def render_state_table(epics: list[dict]) -> None:
    console = Console()
    table = Table(title="HSBTech Work Item State", show_header=True, header_style="bold cyan")
    table.add_column("EPIC", style="bold", no_wrap=True)
    table.add_column("Task")
    table.add_column("Status", justify="center")
    table.add_column("QA Status", justify="center")
    table.add_column("QA Cycles", justify="right")
    table.add_column("PR Link")
    for epic in epics:
        for task in epic["tasks"]:
            table.add_row(
                epic["title"],
                task["title"],
                task["status"],
                task.get("qa_status", "—"),
                str(task.get("qa_cycle_count", 0)),
                task.get("pr_link", "—"),
            )
    console.print(table)
```

### Pattern 4: run_loop.py Thin Wrapper

**What:** A repo-root script that loops `hsb run-next-step` until no `todo` tasks remain.

**When to use:** CLIR-04 continuous loop mode.

**Example:**

```python
# Source: CONTEXT.md D-07 + CLIR-05 — each iteration is standalone asyncio.run()

import asyncio
import subprocess
import sys

async def has_ready_tasks() -> bool:
    """Query Linear for any todo-status tasks in scope. Returns False when loop should stop."""
    # Minimal Linear MCP call: list_issues filtered by status=todo
    # Exact query is Claude's discretion (CONTEXT.md) — kept minimal here
    from src.hsb.agents.linear_agent import check_ready_tasks
    return await check_ready_tasks()

def main() -> None:
    print("Starting HSBTech run loop. Press Ctrl+C to stop.")
    try:
        while True:
            if not asyncio.run(has_ready_tasks()):
                print("No ready tasks remaining. Loop complete.")
                break
            result = subprocess.run(["hsb", "run-next-step"], check=False)
            if result.returncode != 0:
                print(f"run-next-step failed (exit {result.returncode}). Stopping loop.")
                sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nLoop interrupted by operator.")

if __name__ == "__main__":
    main()
```

### Pattern 5: SKILL.md Migration for Task Orchestration

**What:** Add YAML frontmatter to the existing `skills/06-TASK-ORCHESTRATION.md` content and write to `.claude/skills/task-orchestration/SKILL.md`.

**When to use:** SKILL.md migration task (Claude's discretion, following Phase 1/2 pattern).

**Example frontmatter:**

```yaml
---
name: task-orchestration
description: "Work Item Orchestrator — drives a single task from todo to done through the full lifecycle (Linear read → Builder → Git → QA → fix loop → done). Only invoke when: operator triggers run-next-step on a specific work item. Side effects: updates Linear state, calls Builder/Git/QA agents."
disable-model-invocation: true
allowed-tools: "mcp__agents__run_builder mcp__agents__run_git mcp__agents__run_qa mcp__agents__run_linear_op mcp__linear__get_issue mcp__linear__update_issue mcp__linear__create_comment mcp__linear__list_issues"
---
```

Note: `disable-model-invocation: true` is mandatory because this skill has Linear write side effects (Pitfall 7 prevention). [CITED: .planning/research/PITFALLS.md Pitfall 7; .planning/research/STACK.md SKILL.md section]

### Anti-Patterns to Avoid

- **Sub-agent dispatch in Phase 3**: Do not use `AgentDefinition` or `agents={}` in `ClaudeAgentOptions`. This spawns separate SDK sessions, violating D-01 (single session, no sub-subagent dispatch). Use `create_sdk_mcp_server` + `@tool` instead.
- **Importing Phase 2 agent results from conversation history**: WORC-04 mandates that every agent invocation receives the full Linear issue content as explicit structured input. Never rely on the orchestrator's context window to carry state from one tool call to the next. Each `@tool` wrapper must receive complete structured input.
- **Async CLI handlers without asyncio.run()**: Typer command functions are synchronous. Do not mark them `async` — Typer does not support async command handlers natively. Wrap with `asyncio.run()` inside the synchronous function.
- **Direct Linear MCP calls in orchestrator without Linear Agent service**: All Linear writes must flow through `linear_agent.py` — not direct `mcp__linear__*` calls from the orchestrator. Consistent with the Phase 1/2 architecture.
- **Storing orchestration state in CLI process memory**: `run_loop.py` must treat each `hsb run-next-step` invocation as stateless. No shared memory, no state file at OS level. Linear is the entire state store (CLIR-05).
- **Concatenating skill files without section separators**: When assembling the system prompt, include clear section headers between skill files (e.g., `# SKILL: task-orchestration`). Without separators, the LLM cannot disambiguate which skill's constraints apply to which lifecycle step.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exposing Python functions as agent tools | Custom JSON-RPC server, custom tool dispatch loop | `create_sdk_mcp_server` + `@tool` decorator | SDK handles the MCP protocol, serialization, error propagation; in-process (no subprocess overhead) |
| Multi-turn orchestration loop | Manual `while True` + LLM API calls + tool dispatch | `query()` with `max_turns=N` | SDK implements the full agentic loop (tool use → result → next turn) internally |
| CLI argument parsing | argparse, custom sys.argv parsing | Typer `@app.command()` | Already in project dependencies; type-annotated; auto-generates `--help` |
| Terminal table formatting | ANSI escape codes, manual column alignment | `rich.table.Table` + `Console.print()` | Already in dependencies; handles column width, wrapping, color automatically |
| Context window monitoring | Token counting, manual budget checks | `await client.get_context_usage()` on `ClaudeSDKClient` | SDK provides `{'percentage': float, 'totalTokens': int, 'maxTokens': int}` — use this if context pressure observed during benchmark run |
| Session resumption across CLI invocations | Custom session file, pickle | `ResultMessage.session_id` + `ClaudeAgentOptions(resume=session_id)` | SDK natively supports session resumption; needed if Phase 4 wants to resume incomplete orchestration cycles |

**Key insight:** The Claude Agent SDK's in-process MCP server pattern (`create_sdk_mcp_server` + `@tool`) is the correct and only supported way to expose Python functions as tools within a single SDK session without spawning sub-agents. Do not implement a custom tool dispatch mechanism.

---

## Runtime State Inventory

> Phase 3 is primarily new code and migrations. Not a rename/refactor phase. This section is abbreviated to the migration component only.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no Linear state or databases exist yet (Phases 1/2 not yet implemented) | None |
| Live service config | None — no deployed workflows | None |
| OS-registered state | None | None |
| Secrets/env vars | `ANTHROPIC_API_KEY` required by claude-agent-sdk; `LINEAR_API_KEY` or OAuth token for Linear MCP | No rename — new vars needed in `.env` for first-time setup |
| Build artifacts / installed packages | None — no pyproject.toml or pip install yet (Phases 1/2 not implemented) | Phase 3 adds `run_loop.py` at repo root; pyproject.toml entrypoints from Phase 1/2 must include `hsb = src.hsb.cli.main:app` for `hsb run-next-step` to work |

**Nothing found in categories 1-4:** Verified by git status — no Python code, no `.venv`, no pyproject.toml exists yet. Phases 1 and 2 are pre-implementation. Phase 3 ships after both predecessors complete.

---

## Common Pitfalls

### Pitfall 1: Sub-agent Dispatch Accidentally Triggered

**What goes wrong:** The orchestrator system prompt includes language like "delegate to the Builder Agent" which, if `AgentDefinition` agents are registered, causes the SDK to spawn a sub-agent (separate SDK session) rather than calling the in-process `@tool` wrapper.

**Why it happens:** `ClaudeAgentOptions` supports both `agents={}` (sub-agent definitions) and `mcp_servers={}` (in-process tools). If both are registered, the LLM may choose either path. The system prompt language in the SKILL.md files uses delegation terminology.

**How to avoid:** Do NOT register any `agents={}` in `ClaudeAgentOptions`. Register only `mcp_servers` (the in-process SDK server). The `allowed_tools` list should contain `mcp__agents__*` entries, not `Task` (which triggers sub-agent dispatch). [VERIFIED: Context7 /anthropics/claude-agent-sdk-python — AgentDefinition docs]

**Warning signs:** Log shows `Using: Task(...)` tool call instead of `Using: mcp__agents__run_builder(...)`.

### Pitfall 2: Stateful orchestration across CLIR-05 boundary

**What goes wrong:** Developer stores `work_item_id` or `qa_cycle_count` as a Python global or class attribute between `asyncio.run()` invocations. On the next `hsb run-next-step` call (new process), the state is gone. Orchestrator re-reads stale Linear state or misses QA cycle history.

**Why it happens:** `asyncio.run()` creates a new event loop each invocation; no Python process memory persists between CLI invocations.

**How to avoid:** All state between cycles lives in Linear. The orchestrator reads `qa_cycle_count` from the Linear issue at the start of every `run_orchestration_cycle()` call. Never cache it in Python. [CITED: CONTEXT.md D-07, CLIR-05; PITFALLS.md Pitfall 4 (stale state)]

**Warning signs:** `qa_cycle_count` in Linear disagrees with the value used in orchestrator decisions.

### Pitfall 3: Context Window Accumulation from Large PR Diffs

**What goes wrong:** During the MVP benchmark run, the QA agent tool call returns a large PR diff (e.g., 5,000 tokens). After two QA cycles, the context window is heavy with prior tool outputs. The system prompt skill content (8,000 tokens) plus tool output history pushes the session toward its limit. The orchestrator starts missing original requirements from the beginning of the context.

**Why it happens:** The `query()` function accumulates all tool call results in the context window. Unlike conversation history (which can be compacted), tool results are dense and not automatically summarized.

**How to avoid:**
- Monitor context usage during the benchmark run: check `ResultMessage` for session stats, or use `client.get_context_usage()` if switching to `ClaudeSDKClient`.
- If pressure is observed: pass only the tool output summary (e.g., `QAFindings.summary` field) back rather than the full diff.
- D-02 is explicit: the benchmark run IS the context validation. If context pressure occurs, it is the signal to trim — not a reason to add complexity before the test. [CITED: CONTEXT.md D-02; PITFALLS.md Pitfall 5]

**Warning signs:** Context usage percentage exceeds 60% before QA step. Agent responses omit references to acceptance criteria stated in the original Linear issue.

### Pitfall 4: Tool Result Serialization Mismatch

**What goes wrong:** The `@tool` wrapper for `run_builder` returns a Pydantic model object directly. The SDK's MCP layer cannot serialize it; tool call silently fails or throws an error the orchestrator misinterprets.

**Why it happens:** The `@tool` return type must be `{"content": [{"type": "text", "text": <string>}]}`. Pydantic models, dicts, and other Python objects are not directly serializable by the MCP layer.

**How to avoid:** All `@tool` wrapper functions must return `{"content": [{"type": "text", "text": model.model_dump_json()}]}`. Validate this in unit tests before integration. [VERIFIED: Context7 /anthropics/claude-agent-sdk-python — @tool decorator and create_sdk_mcp_server docs]

**Warning signs:** Tool call returns an empty result or `is_error: True` in the SDK output stream.

### Pitfall 5: run_loop.py Infinite Loop on Error

**What goes wrong:** `hsb run-next-step` fails (non-zero exit code) but `run_loop.py` continues the loop, repeatedly triggering failed cycles.

**Why it happens:** If `subprocess.run()` is called without checking `returncode`, a failed orchestration cycle looks the same as a successful one to the loop driver.

**How to avoid:** Check `result.returncode != 0` after each `subprocess.run()` call in `run_loop.py`. On non-zero exit, stop the loop and surface the error. [ASSUMED — standard subprocess error handling pattern]

### Pitfall 6: Missing mcp-remote / npx Not Available at Runtime

**What goes wrong:** `ClaudeAgentOptions(mcp_servers={"linear": {"command": "npx", "args": ["-y", "mcp-remote", "..."]}} )` fails silently because `npx` is not available or network is restricted.

**Why it happens:** The Linear MCP server requires `npx -y mcp-remote` to launch. If Node.js/npm is not installed, or if the machine is air-gapped, the MCP server fails to start.

**How to avoid:** Include an environment pre-flight in `run_orchestration_cycle()`: attempt a simple `mcp__linear__list_teams` call before the orchestrator loop. If it fails, raise a clear error with install instructions rather than letting the orchestrator run without Linear access. [ASSUMED — standard defensive coding; not verified against SDK docs]

---

## Code Examples

Verified patterns from official sources:

### @tool Decorator with In-Process MCP Server

```python
# Source: Context7 /anthropics/claude-agent-sdk-python — create_sdk_mcp_server
from typing import Any
from claude_agent_sdk import create_sdk_mcp_server, tool

@tool("run_builder", "Execute the Builder Agent for a work item",
      {"work_item_id": str, "issue_content": str})
async def run_builder_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.hsb.agents.builder_agent import run_builder_agent
    result = await run_builder_agent(args["work_item_id"], args["issue_content"])
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}

sdk_server = create_sdk_mcp_server(
    name="agents",
    version="1.0.0",
    tools=[run_builder_tool],
)
```

### query() with system_prompt and in-process MCP server

```python
# Source: Context7 /anthropics/claude-agent-sdk-python — ClaudeAgentOptions Configuration
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

async def run_orchestration_cycle(work_item_id: str) -> None:
    options = ClaudeAgentOptions(
        system_prompt=assemble_system_prompt(),   # all 5 skill files concatenated
        mcp_servers={
            "agents": sdk_server,                 # in-process tools
            "linear": {"command": "npx", "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"]},
        },
        allowed_tools=[
            "mcp__agents__run_builder",
            "mcp__agents__run_git",
            "mcp__agents__run_qa",
            "mcp__agents__run_linear_op",
            "mcp__linear__get_issue",
            "mcp__linear__list_issues",
            "mcp__linear__update_issue",
            "mcp__linear__create_comment",
        ],
        permission_mode="acceptEdits",
        max_turns=30,
    )
    async for message in query(prompt=f"Process work item {work_item_id}", options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            print(f"Cost: ${message.total_cost_usd:.4f}")
```

### Rich Table for show-state (5 columns per D-08)

```python
# Source: Context7 /textualize/rich — Create and Print a Rich Table
from rich.console import Console
from rich.table import Table

def render_state_table(linear_state: dict) -> None:
    console = Console()
    table = Table(title="Work Item State", show_header=True, header_style="bold cyan")
    table.add_column("EPIC", style="bold")
    table.add_column("Task")
    table.add_column("Status", justify="center")
    table.add_column("QA Status", justify="center")
    table.add_column("QA Cycles", justify="right")
    table.add_column("PR Link")
    for epic in linear_state.get("epics", []):
        for task in epic.get("tasks", []):
            table.add_row(
                epic["title"],
                task["title"],
                task.get("status", "—"),
                task.get("qa_status", "—"),
                str(task.get("qa_cycle_count", 0)),
                task.get("pr_link", "—"),
            )
    console.print(table)
```

### CLIR-05 Pattern: asyncio.run() in Typer command

```python
# Source: Context7 /fastapi/typer — Create Multi-Command CLI with typer.Typer()
# + CLIR-05 requirement: standalone asyncio.run() per invocation
import asyncio
import typer

app = typer.Typer()  # existing app, extended

@app.command("run-next-step")
def run_next_step(
    work_item_id: str = typer.Option(None, help="LIN-XX id; auto-selects if omitted")
) -> None:
    """Trigger one orchestration cycle."""
    asyncio.run(run_orchestration_cycle(work_item_id))
```

### Work Item Orchestration Contract (Pydantic)

```python
# Source: agents/AGENT-CONTRACTS.md §3 — Work Item Orchestration Contract
from pydantic import BaseModel
from typing import Literal, Optional

class WorkItemOrchInput(BaseModel):
    work_item: dict                   # id, type, status, dependencies
    epic_context: dict
    linear_state: dict

class WorkItemOrchOutput(BaseModel):
    work_item_id: str
    lifecycle_status: Literal[
        "implementation_ready", "pr_ready", "qa_ready",
        "fix_required", "done", "escalated_to_human"
    ]
    next_skill: Optional[Literal[
        "implementation", "git_pr_management",
        "qa_review", "linear_system_of_record"
    ]] = None
    handoff_payload: dict
    lifecycle_summary: str            # WORC-05: persisted to Linear as comment
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ClaudeCodeOptions` configuration class | `ClaudeAgentOptions` | claude-agent-sdk 0.1.x (migrated from Claude Code SDK < 0.1.0) | Breaking rename; project uses `ClaudeAgentOptions` throughout |
| External subprocess MCP servers for Python tools | `create_sdk_mcp_server` + `@tool` in-process | claude-agent-sdk 0.1.x | No subprocess overhead; simpler deployment; all tool logic in same Python process |
| Sub-agent dispatch via `Task` tool for all delegation | In-process `@tool` wrappers for co-located Python modules | claude-agent-sdk 0.1.x | Sub-agents correct for truly isolated contexts; in-process tools correct for orchestrator calling same-process modules (Phase 3 pattern) |
| `anyio.run()` for SDK event loop | `asyncio.run()` acceptable (anyio bundled by SDK) | N/A | Either works; `asyncio.run()` preferred for stdlib simplicity and CLIR-05 pattern clarity |

**Deprecated/outdated:**
- `claude-code-sdk` package: Replaced by `claude-agent-sdk`; `ClaudeCodeOptions` renamed to `ClaudeAgentOptions`. Do not use `claude-code-sdk` — it is the pre-0.1.0 package name.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `run_loop.py` calls `hsb run-next-step` via `subprocess.run()` rather than importing the Python function directly | Architecture Patterns / Pattern 4 | If subprocess approach is too slow or clunky, direct import with `asyncio.run()` is equivalent and cleaner; easy to swap |
| A2 | Returning `model.model_dump_json()` as a text string in `@tool` return value is the correct serialization pattern | Pattern 1 / Don't Hand-Roll | If SDK expects a different return structure, tool calls will silently fail; mitigated by unit test on @tool wrappers before integration |
| A3 | `run_loop.py` exit condition uses `mcp__linear__list_issues` filtered by `status=todo`; exact filter field name matches Linear MCP API | Pattern 4 | If Linear's status field name or enum value differs, the termination check will either always exit or never exit; probed by first integration test run |
| A4 | Environment has `npx` available (Node.js installed) for the Linear MCP transport | Environment Availability | If `npx` not available, Linear MCP fails silently; mitigated by pre-flight check in orchestrator startup |
| A5 | Pitfall 5 (run_loop.py infinite loop on error) prevention via `returncode` check is the correct approach | Common Pitfalls | Standard Python pattern; very low risk of being wrong |
| A6 | Pitfall 6 (missing mcp-remote) prevention via pre-flight call is the correct approach | Common Pitfalls | Defensive pattern; no known SDK docs about startup health checks for MCP servers |

**If this table is empty:** Not applicable — six assumptions identified; see above.

---

## Open Questions

1. **`work_item_id` selection when `--work-item-id` is omitted from `hsb run-next-step`**
   - What we know: CONTEXT.md D-06 says the command "triggers one orchestration cycle; a single work item progresses exactly one lifecycle step." The stopping condition in `run_loop.py` is "no `todo`-status tasks."
   - What's unclear: When the operator runs `hsb run-next-step` without an explicit work item ID, how does the orchestrator select which task to process? It needs a "pick next ready task" heuristic. In Phase 4, the Global Orchestrator handles this. In Phase 3, a direct Linear query must fill this role.
   - Recommendation: The orchestrator queries `mcp__linear__list_issues` for tasks with `status=todo` and no unresolved dependencies, picks the first one (or the one with the lowest ID), and proceeds. This mirrors the minimal Linear query Claude is given discretion over (CONTEXT.md).

2. **`max_turns` value for the orchestrator session**
   - What we know: `ClaudeAgentOptions` supports `max_turns`. The lifecycle has roughly 10-15 tool calls in a happy path (read state + claim → builder → git → qa → update state → comment). Fix cycles add 5-10 more calls each.
   - What's unclear: The right `max_turns` ceiling that prevents runaway without cutting a legitimate long QA fix cycle short.
   - Recommendation: `max_turns=30` is a safe starting value for the MVP benchmark run. Adjust based on observed turn counts. Flag in `ResultMessage` if `max_turns` was hit (vs. natural completion).

3. **Pydantic contract location for `WorkItemOrchOutput`**
   - What we know: AGENT-CONTRACTS.md §3 defines the Work Item Orchestration Contract. Phase 1/2 put contracts in `src/hsb/contracts/`.
   - What's unclear: Whether the orchestrator contract needs a new file `src/hsb/contracts/orchestrator.py` or whether it extends the existing files.
   - Recommendation: New file `src/hsb/contracts/orchestrator.py` — consistent with the one-file-per-agent pattern established in Phases 1/2.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | claude-agent-sdk, all agents | ✓ | 3.12.3 | — |
| `gh` CLI | git_agent.py (Phase 2) | ✓ | 2.89.0 | — |
| `git` CLI | git_agent.py (Phase 2) | ✓ | 2.43.0 | — |
| `npx` / Node.js | Linear MCP transport (`mcp-remote`) | Not verified | — | Use `LINEAR_API_KEY` env var with direct API auth if npx unavailable |
| Linear MCP endpoint | All Linear operations | ✓ (live) | current | Confirmed: `https://mcp.linear.app/mcp` returns auth error (not 404) |
| `claude-agent-sdk` 0.1.73 | Work Item Orchestrator | Not installed | 0.1.73 on PyPI | Install required: `pip install claude-agent-sdk==0.1.73` |
| `pydantic` 2.x | Contracts | Not installed | 2.13.3 on PyPI | Install required: `pip install "pydantic>=2.13"` |
| `typer` 0.25.x | CLI commands | Not installed | 0.25.1 on PyPI | Install required (or via pyproject.toml) |
| `rich` 15.x | show-state table | 13.7.1 installed system-wide | 15.0.0 on PyPI | Either works; pin 15.0.0 in pyproject.toml |
| `hsb-test-fixture` repo | Integration test (MVP benchmark) | Assumed exists per Phase 2 D-11 | — | Must be created in Phase 2; Phase 3 depends on it |

**Missing dependencies with no fallback:**
- None blocking. All missing packages are installable via pip. `hsb-test-fixture` repo is a Phase 2 deliverable.

**Missing dependencies with fallback:**
- `npx` / Node.js: If not available, use `LINEAR_API_KEY` environment variable with the Linear MCP auth header for headless operation. (STACK.md: "For headless/CI use, pass `Authorization: Bearer <api_key>` directly.")

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (not yet installed — Wave 0 gap) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (established in Phase 1) |
| Quick run command | `pytest tests/test_orchestrator.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WORC-01 | Orchestrator drives task from `todo` to `done` via full lifecycle | integration | `pytest tests/integration/test_orchestrator_e2e.py::test_full_lifecycle -x` | ❌ Wave 0 |
| WORC-02 | All skill content embedded inline; no sub-agent dispatch | unit | `pytest tests/unit/test_orchestrator.py::test_no_subagent_dispatch -x` | ❌ Wave 0 |
| WORC-03 | `qa_cycle_count >= 3` escalates to human; no 4th QA cycle | unit | `pytest tests/unit/test_orchestrator.py::test_qa_cycle_cap -x` | ❌ Wave 0 |
| WORC-04 | Every agent invocation receives full Linear issue content | unit | `pytest tests/unit/test_orchestrator.py::test_full_context_in_tool_calls -x` | ❌ Wave 0 |
| WORC-05 | Lifecycle summary persisted to Linear as comment | integration | `pytest tests/integration/test_orchestrator_e2e.py::test_lifecycle_comment -x` | ❌ Wave 0 |
| CLIR-01 | `hsb run-next-step` triggers one lifecycle step | integration | `pytest tests/integration/test_cli.py::test_run_next_step -x` | ❌ Wave 0 |
| CLIR-02 | `hsb show-state` renders rich table without executing | unit | `pytest tests/unit/test_cli.py::test_show_state_renders -x` | ❌ Wave 0 |
| CLIR-03 | `hsb show-next-action` shows decision without side effects | unit | `pytest tests/unit/test_cli.py::test_show_next_action_no_side_effects -x` | ❌ Wave 0 |
| CLIR-04 | `run_loop.py` repeats until no ready tasks | integration | `pytest tests/integration/test_run_loop.py::test_loop_terminates -x` | ❌ Wave 0 |
| CLIR-05 | CLI command is standalone `asyncio.run()` with no process-level state | unit | `pytest tests/unit/test_cli.py::test_no_process_state -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/ -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_orchestrator.py` — unit tests for WORC-02, WORC-03, WORC-04
- [ ] `tests/unit/test_cli.py` — unit tests for CLIR-02, CLIR-03, CLIR-05
- [ ] `tests/integration/test_orchestrator_e2e.py` — integration test for WORC-01, WORC-05 (requires real Linear + hsb-test-fixture)
- [ ] `tests/integration/test_cli.py` — integration test for CLIR-01
- [ ] `tests/integration/test_run_loop.py` — integration test for CLIR-04
- [ ] `src/hsb/contracts/orchestrator.py` — Pydantic models for Work Item Orchestration Contract
- [ ] `src/hsb/agents/work_item_orchestrator.py` — orchestrator implementation (main deliverable)
- [ ] `run_loop.py` — repo root wrapper script
- [ ] `.claude/skills/task-orchestration/SKILL.md` — SKILL.md migration

---

## Security Domain

> `security_enforcement` key absent from `.planning/config.json` — treating as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user-facing auth — API key authentication handled by SDK and Linear MCP |
| V3 Session Management | no | Each CLI invocation is stateless (CLIR-05); no session tokens stored between calls |
| V4 Access Control | no | Single-operator local CLI; no multi-user access control required |
| V5 Input Validation | yes | pydantic 2.x validates all agent input/output contracts; `WorkItemOrchInput` validates `work_item_id` format |
| V6 Cryptography | no | No key management in orchestrator; `ANTHROPIC_API_KEY` and `LINEAR_API_KEY` from env vars (not hard-coded) |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via Linear issue content | Tampering | Linear issue content passed as structured JSON (not raw user string embedded in prompt); Pydantic validation rejects unexpected fields |
| Credential leakage in logs | Information Disclosure | Do not log `ANTHROPIC_API_KEY` or `LINEAR_API_KEY`; use python-dotenv to load from `.env`; `.env` in `.gitignore` |
| Runaway tool calls exhausting budget | Denial of Service | `max_turns=30` hard ceiling on `ClaudeAgentOptions`; `max_budget_usd` optional additional guard |
| QA cycle escalation bypass | Elevation of Privilege | Layered enforcement: QA Agent SKILL.md (Layer 1) + orchestrator safety net check (Layer 2, D-05); both independently prevent 4th QA cycle |

---

## Sources

### Primary (HIGH confidence)

- Context7 `/anthropics/claude-agent-sdk-python` — `query()` function, `ClaudeAgentOptions`, `create_sdk_mcp_server`, `@tool` decorator, `ClaudeSDKClient`, hooks, session management
- Context7 `/textualize/rich` — `Table`, `add_column`, `add_row`, `Console.print()`
- Context7 `/fastapi/typer` — `@app.command()`, `typer.Option`, multi-command app structure
- PyPI registry — claude-agent-sdk 0.1.73, typer 0.25.1, rich 15.0.0, pydantic 2.13.3 [VERIFIED: pip index versions, 2026-05-05]
- `.planning/research/STACK.md` — Phase 1 technology research; exact tool names, SDK patterns, Linear MCP setup
- `.planning/research/PITFALLS.md` — Critical failure modes; Pitfall 5 (context exhaustion), Pitfall 7 (skill auto-invocation)
- `agents/AGENT-CONTRACTS.md` — Work Item Orchestration Contract §3 (input/output schema)
- `runtime/RUNTIME-EXECUTION.md` — "one action per Work Item Orchestrator" golden rule
- `skills/06-TASK-ORCHESTRATION.md` — behavioral spec for orchestrator SKILL.md

### Secondary (MEDIUM confidence)

- Context7 `/anthropics/claude-agent-sdk-demos` — demo orchestrator patterns (research-agent parallel spawn pattern; inverse of Phase 3 sequential pattern)
- Linear MCP endpoint probe: `curl -s https://mcp.linear.app/mcp` returns auth error (not 404) — confirms endpoint is live

### Tertiary (LOW confidence)

- None — all critical claims are verified against primary sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI registry on 2026-05-05
- Architecture patterns: HIGH — `query()`, `ClaudeAgentOptions`, `create_sdk_mcp_server`, `@tool` all verified against Context7 official SDK docs
- Pitfalls: HIGH — derived from project PITFALLS.md (prior research) and SDK docs verification; A1-A6 in Assumptions Log are the only unverified claims
- CLI patterns: HIGH — Typer subcommand and rich Table patterns verified against Context7 official library docs
- Integration test strategy: MEDIUM — follows Phase 2 D-09 pattern (real services, no mocking); specific test file names are pre-implementation proposals

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (claude-agent-sdk is active development; re-verify version before Phase 3 begins if > 2 weeks elapse)
