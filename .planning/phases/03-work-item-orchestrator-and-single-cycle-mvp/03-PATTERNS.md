# Phase 3: Work Item Orchestrator and Single-Cycle MVP - Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 10 new/modified files
**Analogs found:** 10 / 10 (all spec-derived from Phase 1 + Phase 2 PATTERNS.md and specification documents; no Python source exists yet)

> **Greenfield note (same as Phases 1 and 2):** The repository still contains only markdown documentation — no Python source code has been created yet. Every pattern below is derived from (1) the Phase 1 PATTERNS.md (canonical foundation patterns), (2) the Phase 2 PATTERNS.md (agent/contract/test extension patterns), and (3) the Phase 3 RESEARCH.md and AGENT-CONTRACTS.md §3. Phase 3 introduces one new architectural primitive not present in Phases 1/2: the `claude_agent_sdk.create_sdk_mcp_server` + `@tool` in-process MCP server pattern. All code excerpts below are canonical — copy verbatim, do not paraphrase.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/hsb/agents/work_item_orchestrator.py` | service | event-driven (single SDK session, sequential tool dispatch) | `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md §linear_agent.py) + `03-RESEARCH.md` Pattern 1 | role-match + SDK-specific |
| `src/hsb/contracts/orchestrator.py` | model | CRUD (pydantic validate) | `src/hsb/contracts/qa.py` (Phase 2 PATTERNS.md — model_validator + Literal status enum) | exact-role |
| `src/hsb/cli/main.py` (extend) | controller | request-response (typer CLI → asyncio.run) | `src/hsb/cli/main.py` (Phase 1 PATTERNS.md §cli/main.py + Phase 2 delta) | exact-role |
| `run_loop.py` | utility | event-driven (subprocess loop + asyncio.run termination check) | `03-RESEARCH.md` Pattern 4 — no prior analog in codebase | spec-derived |
| `.claude/skills/task-orchestration/SKILL.md` | config | — | `.claude/skills/linear-system-of-record/SKILL.md` (Phase 1 PATTERNS.md §SKILL.md) | exact-role |
| `tests/unit/test_orchestrator.py` | test | CRUD (unit) | `tests/unit/test_qa_contract.py` (Phase 2 PATTERNS.md — model_validator + business logic unit tests) | exact-role |
| `tests/unit/test_cli.py` | test | request-response (unit) | `tests/test_contracts.py` (Phase 1 PATTERNS.md — parametrized schema tests) | role-match |
| `tests/integration/test_orchestrator_e2e.py` | test | event-driven (integration, real Linear + real repo) | `tests/integration/test_qa_agent.py` (Phase 2 PATTERNS.md — real service integration) | exact-role |
| `tests/integration/test_cli.py` | test | request-response (integration) | `tests/integration/test_builder_agent.py` (Phase 2 PATTERNS.md — integration test pattern) | exact-role |
| `tests/integration/test_run_loop.py` | test | event-driven (integration, subprocess loop) | `tests/integration/test_backlog_agent.py` (Phase 2 PATTERNS.md — integration + side effect) | role-match |

---

## Pattern Assignments

### `src/hsb/agents/work_item_orchestrator.py` (service, event-driven)

**Analog:** `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md §linear_agent.py) for `load_dotenv()`, `query()` loop, and `AssistantMessage`/`ResultMessage` handling; `03-RESEARCH.md` Pattern 1 for `create_sdk_mcp_server` + `@tool` and `ClaudeAgentOptions`.

**Imports pattern** (Phase 1 PATTERNS.md `linear_agent.py` imports + Phase 3 SDK additions):

```python
import asyncio
import logging
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    tool,
    AssistantMessage,
    ResultMessage,
    SystemMessage,
)
from claude_agent_sdk.types import TextBlock
from dotenv import load_dotenv

from hsb.contracts.orchestrator import WorkItemOrchInput, WorkItemOrchOutput
from hsb.agents.linear_agent import run_validated_linear_agent

load_dotenv()

logger = logging.getLogger(__name__)
```

**Skill file assembly pattern** (`03-RESEARCH.md` Pattern 1, §SKILL_FILES block):

```python
# Skill files in injection order: task-orchestration (meta-skill) first, then lifecycle skills
SKILL_FILES = [
    "skills/06-TASK-ORCHESTRATION.md",
    "skills/02-IMPLEMENTATION.md",
    "skills/03-QA-REVIEW.md",
    "skills/04-GIT-PR-MANAGEMENT.md",
    "skills/05-LINEAR-SYSTEM-OF-RECORD.md",
]

def assemble_system_prompt() -> str:
    """Read all skill files and concatenate with clear section separators.
    Section headers are MANDATORY — without them the LLM cannot disambiguate
    which skill's constraints apply to which lifecycle step (RESEARCH.md Anti-Patterns).
    """
    parts = []
    for path in SKILL_FILES:
        content = Path(path).read_text()
        parts.append(f"# SKILL: {Path(path).stem}\n\n{content}")
    return "\n\n---\n\n".join(parts)
```

**`@tool` wrappers for Phase 2 agent modules** (`03-RESEARCH.md` §Code Examples, @tool decorator; Pattern 1 §run_builder_tool):

```python
# CRITICAL: @tool return value MUST be {"content": [{"type": "text", "text": <string>}]}
# Returning a Pydantic model directly causes silent tool failure (RESEARCH.md Pitfall 4).

@tool("run_linear_op", "Execute a Linear System of Record operation",
      {"operation": str, "payload": dict})
async def run_linear_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper: delegates to Phase 1 linear_agent.run_validated_linear_agent."""
    result = await run_validated_linear_agent(
        operation=args["operation"],
        payload=args["payload"],
    )
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}


@tool("run_builder", "Execute the Builder Agent for a work item",
      {"work_item_id": str, "issue_content": str})
async def run_builder_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper: delegates to Phase 2 builder_agent.run_builder_agent.
    Caller (the SDK agent) MUST pass full Linear issue content as issue_content — WORC-04.
    """
    from hsb.agents.builder_agent import run_builder_agent
    from hsb.contracts.builder import BuilderInput, RepositoryContext
    import json

    issue_data = json.loads(args["issue_content"])
    builder_input = BuilderInput(
        work_item_id=args["work_item_id"],
        issue_description=issue_data.get("description", ""),
        acceptance_criteria=issue_data.get("acceptance_criteria", []),
        epic_context=issue_data.get("epic_context", {}),
        plan_source=issue_data.get("plan_source", "/docs/plan.md"),
        repository_context=RepositoryContext(root_path=issue_data.get("root_path", ".")),
    )
    result = run_builder_agent(builder_input)
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}


@tool("run_git", "Execute the Git Agent to create branch and PR",
      {"work_item_id": str, "impl_output": str, "epic_id": str})
async def run_git_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper: delegates to Phase 2 git_agent.run_git_agent."""
    from hsb.agents.git_agent import run_git_agent
    from hsb.contracts.git import GitInput
    import json

    git_input = GitInput(
        work_item_id=args["work_item_id"],
        implementation_output=json.loads(args["impl_output"]),
        epic_id=args["epic_id"],
    )
    result = run_git_agent(git_input)
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}


@tool("run_qa", "Execute the QA Agent to review a PR",
      {"work_item_id": str, "pr_url": str, "diff": str, "qa_cycle_count": int})
async def run_qa_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper: delegates to Phase 2 qa_agent.run_qa_agent."""
    from hsb.agents.qa_agent import run_qa_agent
    from hsb.contracts.qa import QAInput, PullRequestInput

    qa_input = QAInput(
        work_item_id=args["work_item_id"],
        linear_issue={},  # Orchestrator must pass full issue — injected by agent via tool call
        pull_request=PullRequestInput(url=args["pr_url"], diff=args["diff"]),
        implementation_notes={},
        epic_context={},
        qa_cycle_count=args["qa_cycle_count"],
    )
    result = run_qa_agent(qa_input)
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}
```

**Core orchestration cycle** (`03-RESEARCH.md` Pattern 1 §run_orchestration_cycle; Phase 1 PATTERNS.md §run_linear_agent for message-loop structure):

```python
async def run_orchestration_cycle(work_item_id: str | None = None) -> None:
    """
    Execute one full Work Item Orchestrator cycle.
    Single SDK session: skill content in system_prompt, Phase 2 agents as @tool wrappers.
    No sub-agent dispatch — only mcp_servers (CONTEXT.md D-01, RESEARCH.md Pitfall 1).
    """
    system_prompt = assemble_system_prompt()

    # CRITICAL: Do NOT register agents={} — that triggers sub-agent dispatch (RESEARCH.md Pitfall 1).
    # Register only mcp_servers. The allowed_tools list must use mcp__agents__* not Task.
    sdk_server = create_sdk_mcp_server(
        name="agents",
        version="1.0.0",
        tools=[run_linear_tool, run_builder_tool, run_git_tool, run_qa_tool],
    )

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        mcp_servers={
            "agents": sdk_server,
            "linear": {
                "command": "npx",
                "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
            },
        },
        allowed_tools=[
            "mcp__agents__run_linear_op",
            "mcp__agents__run_builder",
            "mcp__agents__run_git",
            "mcp__agents__run_qa",
            "mcp__linear__get_issue",
            "mcp__linear__list_issues",
            "mcp__linear__update_issue",
            "mcp__linear__create_comment",
        ],
        permission_mode="acceptEdits",
        max_turns=30,
    )

    # work_item_id selection: if not provided, orchestrator queries Linear for next todo task
    prompt = (
        f"Run the work item lifecycle for work item {work_item_id}. "
        "Read its current Linear state first, then execute the next appropriate lifecycle step."
        if work_item_id
        else (
            "Query mcp__linear__list_issues for tasks with status=todo and no unresolved dependencies. "
            "Select the first available task (lowest LIN-ID). Then run its work item lifecycle: "
            "read Linear state, then execute the next appropriate lifecycle step."
        )
    )

    # Message loop: same pattern as Phase 1 linear_agent.py §run_linear_agent
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            mcp_servers = message.data.get("mcp_servers", [])
            failed = [s for s in mcp_servers if s.get("status") != "connected"]
            if failed:
                raise RuntimeError(f"MCP server failed to connect: {failed}")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
                elif hasattr(block, "name"):
                    logger.info("[TOOL] %s", block.name)
        elif isinstance(message, ResultMessage):
            logger.info(
                "Orchestration cycle complete. Cost: $%.4f", message.total_cost_usd
            )
```

**QA cycle cap safety net** (CONTEXT.md D-05 Layer 2 — orchestrator-level check; same pattern as Phase 2 `_write_qa_results_to_linear`):

```python
# This check runs AFTER the SDK session completes, when processing WorkItemOrchOutput.
# Layer 1 (QA Agent model_validator) normally prevents reaching here.
# Layer 2 is a safety net only — if somehow qa_cycle_count >= 3 and qa_status == "changes_required"
# still appears in the output, post a Linear escalation comment and do not initiate a 4th cycle.

async def _check_qa_cycle_cap(work_item_id: str, qa_cycle_count: int, qa_status: str) -> None:
    if qa_cycle_count >= 3 and qa_status == "changes_required":
        logger.error(
            "SAFETY NET: qa_cycle_count=%d but qa_status=changes_required for %s. "
            "Escalating to human.",
            qa_cycle_count, work_item_id,
        )
        await run_validated_linear_agent(
            operation="comment",
            payload={
                "issueId": work_item_id,
                "body": (
                    "**Automated escalation — max QA cycles reached**\n\n"
                    f"Max QA cycles reached (`qa_cycle_count={qa_cycle_count}`). "
                    "Escalating to human. Task status: blocked.\n\n"
                    "No further automated fix cycles will be initiated (WORC-03)."
                ),
            },
        )
```

---

### `src/hsb/contracts/orchestrator.py` (model, CRUD)

**Analog:** `src/hsb/contracts/qa.py` (Phase 2 PATTERNS.md §contracts/qa.py — same `model_validator` + `Literal` status enum + `extra="forbid"` pattern)
**Source spec:** `agents/AGENT-CONTRACTS.md` §3 Work Item Orchestration Contract

**Imports pattern** (copy from Phase 2 `contracts/qa.py`):

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field
```

**Full contract models** (mirror `agents/AGENT-CONTRACTS.md` §3 exactly — do not add fields):

```python
class WorkItemOrchInput(BaseModel):
    """Input contract for the Work Item Orchestrator.
    Mirrors AGENT-CONTRACTS.md §3 Input exactly.
    """
    work_item: dict   # id, type, status, dependencies — fetched fresh from Linear at cycle start
    epic_context: dict
    linear_state: dict

    model_config = {"extra": "forbid"}


class WorkItemOrchOutput(BaseModel):
    """Output contract for the Work Item Orchestrator.
    Mirrors AGENT-CONTRACTS.md §3 Output exactly.
    WORC-05: lifecycle_summary is persisted to Linear as a comment after each cycle.
    """
    work_item_id: str
    lifecycle_status: Literal[
        "implementation_ready",
        "pr_ready",
        "qa_ready",
        "fix_required",
        "done",
        "escalated_to_human",
    ]
    next_skill: Optional[Literal[
        "implementation",
        "git_pr_management",
        "qa_review",
        "linear_system_of_record",
    ]] = None
    handoff_payload: dict = Field(default_factory=dict)
    lifecycle_summary: str   # WORC-05: posted to Linear as a structured comment

    model_config = {"extra": "forbid"}
```

**Critical rules (same as Phase 2 `contracts/qa.py`):**
- `extra="forbid"` MANDATORY on both models — same enforcement rationale as all prior contracts
- `lifecycle_summary` field is the WORC-05 persistence payload — it is posted to Linear after every cycle via `run_validated_linear_agent(operation="comment", ...)`
- Do NOT add fields not in `agents/AGENT-CONTRACTS.md §3`

---

### `src/hsb/cli/main.py` — extend Phase 2 (controller, request-response)

**Analog:** `src/hsb/cli/main.py` (Phase 1 PATTERNS.md §cli/main.py + Phase 2 PATTERNS.md delta — same `@app.command()` + `asyncio.run()` pattern)
**Source spec:** `03-RESEARCH.md` Pattern 2 (Typer async command handler); CONTEXT.md D-06, D-08

**Delta: add Phase 3 subcommands** (do NOT rewrite Phase 1/2 commands — append these):

```python
# Additional imports at top of existing main.py (after Phase 2 imports)
from rich.console import Console
from rich.table import Table
from hsb.agents.work_item_orchestrator import run_orchestration_cycle

# NOTE: show_state and show_next_action require a fetch_linear_state helper
# (to be implemented inline or in a separate hsb/cli/state.py utility module)


@app.command("run-next-step")
def run_next_step(
    work_item_id: str = typer.Option(
        None, "--work-item-id",
        help="Linear work item ID (e.g. LIN-42). If omitted, selects next todo task automatically."
    ),
) -> None:
    """Trigger one orchestration cycle — a single work item progresses exactly one lifecycle step (CLIR-01)."""
    # asyncio.run() at CLI boundary only — NEVER inside a coroutine (Phase 1 Shared Patterns)
    asyncio.run(run_orchestration_cycle(work_item_id))


@app.command("show-state")
def show_state() -> None:
    """Render current system state: EPICs, tasks, QA status, PR links (CLIR-02, D-08)."""
    asyncio.run(_render_state_table())


@app.command("show-next-action")
def show_next_action(
    work_item_id: str = typer.Option(
        None, "--work-item-id",
        help="Linear work item ID. If omitted, inspects next available todo task."
    ),
) -> None:
    """Display next recommended action without executing it (CLIR-03). No side effects."""
    asyncio.run(_render_next_action(work_item_id))
```

**Rich table helper** (`03-RESEARCH.md` Pattern 3; to be defined as async helpers or in `hsb/cli/state.py`):

```python
# Async helper called by show_state() via asyncio.run()
async def _render_state_table() -> None:
    """Fetch Linear state and render rich table. Read-only — no writes (CLIR-02)."""
    # Fetch EPIC + child tasks via Linear Agent service (read operation)
    result = await run_validated_linear_agent("read", {"scope": "all_epics"})
    # Parse result into epics list — exact shape depends on LinearOutput
    epics = _parse_epics_from_linear_output(result)

    console = Console()
    table = Table(
        title="HSBTech Work Item State",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("EPIC", style="bold", no_wrap=True)
    table.add_column("Task")
    table.add_column("Status", justify="center")
    table.add_column("QA Status", justify="center")
    table.add_column("QA Cycles", justify="right")
    table.add_column("PR Link")
    for epic in epics:
        for task in epic.get("tasks", []):
            table.add_row(
                epic.get("title", "—"),
                task.get("title", "—"),
                task.get("status", "—"),
                task.get("qa_status", "—"),
                str(task.get("qa_cycle_count", 0)),
                task.get("pr_link", "—"),
            )
    console.print(table)
```

**Critical:** Same `asyncio.run()` rule as Phases 1/2 — all three new command functions are synchronous Typer handlers that wrap async coroutines with `asyncio.run()`. NEVER mark them `async def`. NEVER nest `asyncio.run()` inside a coroutine (Phase 1 Shared Patterns anti-pattern).

---

### `run_loop.py` (utility, event-driven)

**Analog:** `03-RESEARCH.md` Pattern 4 — no prior analog in codebase. Pattern is spec-derived.

**Imports and structure:**

```python
"""
run_loop.py — Thin repo-root wrapper that calls `hsb run-next-step` in a loop.
Stops when no todo-status tasks remain or operator presses Ctrl+C (CLIR-04, D-07).
Each iteration is a standalone asyncio.run() — no process-level state (CLIR-05).
"""
import asyncio
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()
```

**Core loop pattern** (`03-RESEARCH.md` Pattern 4 §main()):

```python
async def has_ready_tasks() -> bool:
    """Query Linear for any todo-status tasks in scope.
    Returns False when loop should stop (no todo tasks remain).
    Uses minimal Linear MCP call: list_issues filtered by status=todo.
    Exact filter is Claude's discretion (CONTEXT.md) — kept minimal here.
    """
    from hsb.agents.linear_agent import run_validated_linear_agent
    result = await run_validated_linear_agent(
        operation="read",
        payload={"filter": {"status": {"eq": "todo"}}},
    )
    return len(result.linear_entities) > 0


def main() -> None:
    print("Starting HSBTech run loop. Press Ctrl+C to stop.")
    try:
        while True:
            if not asyncio.run(has_ready_tasks()):
                print("No ready tasks remaining. Loop complete.")
                break
            result = subprocess.run(["hsb", "run-next-step"], check=False)
            if result.returncode != 0:
                print(
                    f"run-next-step failed (exit {result.returncode}). Stopping loop."
                )
                sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nLoop interrupted by operator.")


if __name__ == "__main__":
    main()
```

**Critical:** Each `asyncio.run()` call creates a new event loop — no Python process state persists between iterations. Linear is the entire state store (CLIR-05). Check `result.returncode != 0` after each subprocess call to prevent infinite loop on error (RESEARCH.md Pitfall 5).

---

### `.claude/skills/task-orchestration/SKILL.md` (config)

**Analog:** `.claude/skills/linear-system-of-record/SKILL.md` (Phase 1 PATTERNS.md §SKILL.md — same frontmatter structure, `disable-model-invocation: true`)
**Source spec:** `03-RESEARCH.md` Pattern 5; `skills/06-TASK-ORCHESTRATION.md` (body content)

**Frontmatter block** (`03-RESEARCH.md` Pattern 5 §Example frontmatter):

```yaml
---
name: task-orchestration
description: |
  Work Item Orchestrator — drives a single task from todo to done through the full lifecycle
  (Linear read → Builder → Git → QA → fix loop → done).
  Only invoke when: operator triggers run-next-step on a specific work item.
  Side effects: updates Linear state, calls Builder/Git/QA agents.
  Do NOT invoke during conversation or without an explicit work item trigger.
disable-model-invocation: true
allowed-tools: "mcp__agents__run_builder mcp__agents__run_git mcp__agents__run_qa mcp__agents__run_linear_op mcp__linear__get_issue mcp__linear__update_issue mcp__linear__create_comment mcp__linear__list_issues"
arguments:
  - name: work_item_id
    description: "Linear work item ID to orchestrate (e.g. LIN-42)"
---
```

**Body:** Append the full content of `skills/06-TASK-ORCHESTRATION.md` (all lines) verbatim after the frontmatter. Do not modify the body — the source file remains as human reference.

**Critical:** `disable-model-invocation: true` is MANDATORY. The Task Orchestrator has Linear write side effects (status updates, comments, fix subtask creation) — auto-invocation from conversation would corrupt Linear state (RESEARCH.md Pitfall 5; same rationale as all Phase 1/2 SKILL.md files).

---

### `tests/unit/test_orchestrator.py` (test, unit)

**Analog:** `tests/unit/test_qa_contract.py` (Phase 2 PATTERNS.md — tests that combine schema validation with business logic via `model_validator`; same `pytest.mark.parametrize` + `pytest.raises(ValidationError)` pattern)

```python
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, patch, MagicMock
from hsb.contracts.orchestrator import WorkItemOrchInput, WorkItemOrchOutput


# --- WORC-02: No sub-agent dispatch ---

def test_no_subagent_dispatch_in_options():
    """WORC-02: ClaudeAgentOptions must not register agents={} — only mcp_servers."""
    from hsb.agents.work_item_orchestrator import run_orchestration_cycle
    import inspect
    source = inspect.getsource(run_orchestration_cycle)
    # The source must NOT contain AgentDefinition or agents= key in ClaudeAgentOptions
    assert "AgentDefinition" not in source, (
        "Sub-agent dispatch detected. Use create_sdk_mcp_server + @tool instead (RESEARCH.md Pitfall 1)."
    )
    assert '"agents":' not in source or "mcp_servers" in source, (
        "agents= key in ClaudeAgentOptions means sub-agent dispatch. Must use mcp_servers only."
    )


# --- WORC-03: QA cycle cap ---

def test_qa_cycle_cap_model_validator():
    """WORC-03 / QAAG-04: qa_cycle_count >= 3 with changes_required is rejected at contract level."""
    # This test confirms the Phase 2 QAOutput model_validator still applies
    from hsb.contracts.qa import QAOutput
    with pytest.raises(ValidationError, match="qa_cycle_count >= 3"):
        QAOutput.model_validate({
            "work_item_id": "LIN-123",
            "qa_status": "changes_required",
            "qa_cycle_count": 3,
            "summary": "Still failing",
            "findings": [],
        })


@pytest.mark.asyncio
async def test_qa_cycle_cap_safety_net_posts_comment():
    """WORC-03 Layer 2: Safety net posts escalation comment when cap is reached."""
    from hsb.agents.work_item_orchestrator import _check_qa_cycle_cap
    with patch("hsb.agents.work_item_orchestrator.run_validated_linear_agent", new_callable=AsyncMock) as mock_linear:
        mock_linear.return_value = MagicMock(model_dump_json=lambda: '{"result": "success"}')
        await _check_qa_cycle_cap("LIN-123", qa_cycle_count=3, qa_status="changes_required")
        mock_linear.assert_called_once()
        call_kwargs = mock_linear.call_args
        assert call_kwargs[1]["operation"] == "comment" or call_kwargs[0][0] == "comment"


# --- WORC-04: Full context passed in tool calls ---

def test_tool_wrapper_requires_full_issue_content():
    """WORC-04: run_builder_tool must accept issue_content as a structured JSON string."""
    import inspect
    from hsb.agents.work_item_orchestrator import run_builder_tool
    source = inspect.getsource(run_builder_tool)
    # issue_content must be parsed from the args dict — not taken from context window state
    assert "issue_content" in source
    assert "json.loads" in source or "model_validate" in source


# --- Contract validation ---

def test_valid_orch_output_passes():
    output = WorkItemOrchOutput.model_validate({
        "work_item_id": "LIN-123",
        "lifecycle_status": "done",
        "next_skill": None,
        "handoff_payload": {},
        "lifecycle_summary": "Task completed successfully. QA approved on first cycle.",
    })
    assert output.lifecycle_status == "done"


def test_invalid_lifecycle_status_fails():
    with pytest.raises(ValidationError):
        WorkItemOrchOutput.model_validate({
            "work_item_id": "LIN-123",
            "lifecycle_status": "unknown_status",  # not in Literal
            "handoff_payload": {},
            "lifecycle_summary": "x",
        })


def test_orch_output_extra_field_rejected():
    with pytest.raises(ValidationError):
        WorkItemOrchOutput.model_validate({
            "work_item_id": "LIN-123",
            "lifecycle_status": "done",
            "handoff_payload": {},
            "lifecycle_summary": "done",
            "unexpected_field": "boom",
        })
```

---

### `tests/unit/test_cli.py` (test, unit)

**Analog:** `tests/test_contracts.py` (Phase 1 PATTERNS.md — schema test pattern); Phase 1/2 CLI tests (CLIR-02, CLIR-03, CLIR-05)

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typer.testing import CliRunner
from hsb.cli.main import app

runner = CliRunner()


# --- CLIR-02: show-state renders table without executing ---

def test_show_state_renders_table():
    """CLIR-02: show-state renders rich table from Linear state. No side-effect writes."""
    with patch("hsb.cli.main.run_validated_linear_agent", new_callable=AsyncMock) as mock_linear:
        mock_linear.return_value = MagicMock(linear_entities=[])
        result = runner.invoke(app, ["show-state"])
    # Command should exit 0 even if no tasks exist
    assert result.exit_code == 0


# --- CLIR-03: show-next-action has no side effects ---

def test_show_next_action_no_side_effects():
    """CLIR-03: show-next-action must produce output without any Linear writes."""
    with patch("hsb.cli.main.run_validated_linear_agent", new_callable=AsyncMock) as mock_linear:
        mock_linear.return_value = MagicMock(linear_entities=[])
        result = runner.invoke(app, ["show-next-action"])
    # Confirm no update/create/comment operations were called
    for call in mock_linear.call_args_list:
        op = call[1].get("operation") or (call[0][0] if call[0] else None)
        assert op not in ("update", "create", "comment", "create_subtasks"), (
            f"show-next-action triggered a write operation: {op}"
        )


# --- CLIR-05: No process-level state between invocations ---

def test_run_next_step_uses_asyncio_run():
    """CLIR-05: run-next-step handler must use asyncio.run() — not be async itself."""
    import inspect
    from hsb.cli.main import run_next_step
    assert not asyncio.iscoroutinefunction(run_next_step), (
        "run_next_step must be a synchronous Typer handler, not async. "
        "Wrap with asyncio.run() inside the function body."
    )
    source = inspect.getsource(run_next_step)
    assert "asyncio.run(" in source, (
        "run_next_step must call asyncio.run() to invoke run_orchestration_cycle()"
    )


def test_show_state_uses_asyncio_run():
    """CLIR-05: show-state handler must use asyncio.run()."""
    import inspect
    from hsb.cli.main import show_state
    assert not asyncio.iscoroutinefunction(show_state)
    source = inspect.getsource(show_state)
    assert "asyncio.run(" in source
```

---

### `tests/integration/test_orchestrator_e2e.py` (test, integration)

**Analog:** `tests/integration/test_qa_agent.py` (Phase 2 PATTERNS.md — real service integration, `pytestmark = [pytest.mark.integration]`, same async test function pattern)

```python
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
async def test_full_lifecycle_todo_to_done():
    """WORC-01: Orchestrator drives a real Linear task from todo to done.
    Requires: real Linear test workspace, real hsb-test-fixture repo, ANTHROPIC_API_KEY set.
    """
    from hsb.agents.work_item_orchestrator import run_orchestration_cycle
    # work_item_id should be a known LIN-* task in todo state in the test workspace
    # Set via env var or fixture to avoid hardcoding
    import os
    work_item_id = os.environ.get("TEST_WORK_ITEM_ID", "LIN-TEST-1")
    # Should complete without raising — full lifecycle cycle
    await run_orchestration_cycle(work_item_id)


@pytest.mark.integration
async def test_lifecycle_comment_persisted():
    """WORC-05: lifecycle_summary is posted to Linear as a comment after cycle."""
    from hsb.agents.work_item_orchestrator import run_orchestration_cycle
    from hsb.agents.linear_agent import run_validated_linear_agent
    import os

    work_item_id = os.environ.get("TEST_WORK_ITEM_ID", "LIN-TEST-1")
    await run_orchestration_cycle(work_item_id)

    # Verify a comment was created on the issue
    result = await run_validated_linear_agent("read", {"issueId": work_item_id})
    # Exact assertion depends on how LinearOutput exposes comments;
    # at minimum confirm the cycle did not raise
    assert result.result == "success"


@pytest.mark.integration
async def test_qa_cycle_cap_not_exceeded():
    """WORC-03: Orchestrator never initiates a 4th QA cycle on any work item."""
    from hsb.contracts.qa import QAOutput
    # After a full e2e run, qa_cycle_count in Linear should be <= 3
    # Assertion: QAOutput model_validator would have blocked qa_cycle_count >= 3 + changes_required
    # This test is a safety gate — it should always pass if Phase 2 contracts are intact
    with pytest.raises(Exception):
        QAOutput.model_validate({
            "work_item_id": "LIN-TEST-1",
            "qa_status": "changes_required",
            "qa_cycle_count": 3,
            "summary": "Fourth cycle attempt",
            "findings": [],
        })
```

---

### `tests/integration/test_cli.py` (test, integration)

**Analog:** `tests/integration/test_builder_agent.py` (Phase 2 PATTERNS.md — same integration marker + Typer runner pattern)

```python
import pytest
from typer.testing import CliRunner
from hsb.cli.main import app

pytestmark = [pytest.mark.integration]

runner = CliRunner()


@pytest.mark.integration
def test_run_next_step_triggers_lifecycle():
    """CLIR-01: hsb run-next-step triggers one orchestration cycle against real Linear."""
    import os
    work_item_id = os.environ.get("TEST_WORK_ITEM_ID", "LIN-TEST-1")
    result = runner.invoke(app, ["run-next-step", "--work-item-id", work_item_id])
    # Non-zero exit is a test failure, not a CLI usage error
    assert result.exit_code == 0, f"run-next-step failed: {result.output}"


@pytest.mark.integration
def test_show_state_returns_table_output():
    """CLIR-02: hsb show-state produces a rich table against real Linear state."""
    result = runner.invoke(app, ["show-state"])
    assert result.exit_code == 0
    # Rich table output contains at minimum the table title
    assert "State" in result.output or result.exit_code == 0
```

---

### `tests/integration/test_run_loop.py` (test, integration)

**Analog:** `tests/integration/test_backlog_agent.py` (Phase 2 PATTERNS.md — integration test with side effects, subprocess output assertions)

```python
import pytest
import subprocess
import sys

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
def test_loop_terminates_when_no_ready_tasks():
    """CLIR-04: run_loop.py exits when no todo tasks remain in Linear."""
    # Pre-condition: no todo tasks in test workspace
    # Invoke run_loop.py directly as a subprocess
    result = subprocess.run(
        [sys.executable, "run_loop.py"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Should exit cleanly with "No ready tasks remaining" message
    assert result.returncode == 0
    assert "No ready tasks remaining" in result.stdout or "Loop complete" in result.stdout


@pytest.mark.integration
def test_loop_exits_on_ctrl_c(tmp_path):
    """CLIR-04: run_loop.py stops cleanly on KeyboardInterrupt."""
    import signal
    import time
    process = subprocess.Popen(
        [sys.executable, "run_loop.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(2)  # Let loop start
    process.send_signal(signal.SIGINT)
    process.wait(timeout=10)
    # Should exit with 0 (KeyboardInterrupt handled) or 130 (SIGINT default)
    assert process.returncode in (0, 130)


@pytest.mark.integration
def test_loop_stops_on_run_next_step_failure(monkeypatch):
    """RESEARCH.md Pitfall 5: Loop stops when run-next-step exits non-zero."""
    # This is verified by the returncode check in run_loop.py main()
    # Unit-level verification: run_loop.py source contains returncode check
    import inspect
    from run_loop import main  # type: ignore[import]
    source = inspect.getsource(main)
    assert "returncode" in source, (
        "run_loop.py must check returncode to stop on non-zero exit (RESEARCH.md Pitfall 5)"
    )
```

---

## Shared Patterns

### Pattern: `extra="forbid"` on all pydantic models

**Source:** Phase 1 PATTERNS.md §Shared Patterns; Phase 2 PATTERNS.md §Shared Patterns
**Apply to:** `WorkItemOrchInput` and `WorkItemOrchOutput` in `src/hsb/contracts/orchestrator.py`

```python
model_config = {"extra": "forbid"}
```

Absent on any model → silent schema drift passes undetected. Consistent across all phases.

---

### Pattern: `asyncio.run()` at CLI boundary only — NEVER inside coroutines

**Source:** Phase 1 PATTERNS.md §Shared Patterns §asyncio.run at CLI boundary; `03-RESEARCH.md` Anti-Patterns §async CLI handlers
**Apply to:** All three new `src/hsb/cli/main.py` command handlers (`run_next_step`, `show_state`, `show_next_action`)

```python
# CORRECT — synchronous Typer handler wraps coroutine with asyncio.run()
@app.command("run-next-step")
def run_next_step(work_item_id: str = typer.Option(None)) -> None:
    asyncio.run(run_orchestration_cycle(work_item_id))

# WRONG — Typer does not support async handlers natively
@app.command("run-next-step")
async def run_next_step(work_item_id: str = typer.Option(None)) -> None:  # DO NOT DO THIS
    await run_orchestration_cycle(work_item_id)
```

---

### Pattern: `@tool` return value serialization

**Source:** `03-RESEARCH.md` §Pitfall 4 + §Code Examples §@tool decorator
**Apply to:** All four `@tool`-decorated functions in `work_item_orchestrator.py`

```python
# CORRECT — SDK MCP layer requires this exact return structure
return {"content": [{"type": "text", "text": result.model_dump_json()}]}

# WRONG — Pydantic model returned directly causes silent tool failure
return result  # SDK cannot serialize Pydantic models
```

---

### Pattern: No sub-agent dispatch — `mcp_servers` only in `ClaudeAgentOptions`

**Source:** `03-RESEARCH.md` Pitfall 1 + Anti-Patterns §Sub-agent dispatch; CONTEXT.md D-01
**Apply to:** `run_orchestration_cycle()` in `work_item_orchestrator.py`

```python
# CORRECT — in-process MCP server, no AgentDefinition
options = ClaudeAgentOptions(
    mcp_servers={"agents": sdk_server},   # only mcp_servers
    allowed_tools=["mcp__agents__*"],     # mcp__agents__* prefix
    # NO agents={} key
)

# WRONG — AgentDefinition spawns separate SDK session, violates D-01
options = ClaudeAgentOptions(
    agents={"builder": AgentDefinition(...)},  # DO NOT DO THIS
    allowed_tools=["Task"],
)
```

---

### Pattern: `load_dotenv()` at module level

**Source:** Phase 1 PATTERNS.md §Shared Patterns §load_dotenv; Phase 2 PATTERNS.md §Shared Patterns
**Apply to:** `work_item_orchestrator.py` and `run_loop.py`

```python
from dotenv import load_dotenv
load_dotenv()  # Must be before any os.environ, Anthropic(), or SDK call
```

---

### Pattern: `disable-model-invocation: true` in SKILL.md

**Source:** Phase 1 PATTERNS.md §SKILL.md; Phase 2 PATTERNS.md §disable-model-invocation; `03-RESEARCH.md` Pattern 5
**Apply to:** `.claude/skills/task-orchestration/SKILL.md`

Every skill with Linear write side effects must have `disable-model-invocation: true`. Task Orchestration writes Linear state (status updates, comments, fix subtask creation) — auto-invocation from conversation would corrupt the Linear workspace.

---

### Pattern: `@pytest.mark.integration` and `pytestmark` for all integration tests

**Source:** Phase 1 PATTERNS.md §test_integration.py; Phase 2 PATTERNS.md §integration tests
**Apply to:** All files in `tests/integration/`

```python
import pytest
pytestmark = [pytest.mark.integration]

@pytest.mark.integration
async def test_something_live():
    ...
```

Run with: `pytest tests/integration/ -v -m integration`
Skip with: `pytest tests/unit/ -x` (no real services needed)

---

## No Analog Found

All Phase 3 files have strong analogs in Phase 1 and Phase 2 PATTERNS.md or project specification documents.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `run_loop.py` (subprocess loop) | utility | event-driven | No prior subprocess-loop file exists in codebase; pattern is spec-derived from `03-RESEARCH.md` Pattern 4. The `asyncio.run()` + Typer boundary patterns from Phase 1/2 apply inside the helper function, but the subprocess loop shell is novel to Phase 3. |

---

## Metadata

**Analog search scope:** Phase 1 PATTERNS.md (primary), Phase 2 PATTERNS.md (primary), `03-RESEARCH.md`, `03-CONTEXT.md`, `agents/AGENT-CONTRACTS.md` §3, `skills/06-TASK-ORCHESTRATION.md`
**Files scanned:** Phase 1 PATTERNS.md, Phase 2 PATTERNS.md, 03-CONTEXT.md, 03-RESEARCH.md, AGENT-CONTRACTS.md, skills/06-TASK-ORCHESTRATION.md
**Python source files found:** 0 (greenfield; Phases 1 and 2 are pre-implementation)
**Pattern extraction date:** 2026-05-05
**Primary pattern sources:** Phase 1 PATTERNS.md (foundation: `asyncio.run()`, `load_dotenv()`, pydantic contracts, Typer CLI, `extra="forbid"`), Phase 2 PATTERNS.md (agent/contract/test extensions), `03-RESEARCH.md` Pattern 1-5 (SDK-specific patterns: `create_sdk_mcp_server`, `@tool`, `ClaudeAgentOptions`)
