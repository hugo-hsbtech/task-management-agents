# Phase 1: Foundation and Linear Integration — Research

**Researched:** 2026-05-05
**Domain:** Python package scaffolding + Claude Agent SDK + Linear MCP + Pydantic contract validation + SKILL.md migration
**Confidence:** HIGH (primary sources are the project's own pre-researched STACK.md, PITFALLS.md, and AI-SPEC.md; all critical library versions verified against PyPI registry)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use OAuth 2.1 interactive browser flow for Linear MCP authentication. The `mcp-remote` transport handles this via `npx -y mcp-remote https://mcp.linear.app/mcp`. No API key management required.
- **D-02:** Token refresh is handled automatically by `mcp-remote`. No custom re-auth code needed.
- **D-03:** Use `src/hsb/` layout — a proper Python package under `src/`. Subdirectories: `agents/`, `contracts/`, `cli/`.
- **D-04:** Pydantic contract models live in `src/hsb/contracts/` with one file per agent (e.g., `linear.py`, `backlog.py`, `qa.py`) — mirrors the AGENT-CONTRACTS.md structure.
- **D-05:** Use `pyproject.toml` (not `requirements.txt`) for packaging, entry points, and dependency pins. This enables `pip install -e .` and named CLI entry points.
- **D-06:** Migrate only the Linear System of Record skill in Phase 1. Create `.claude/skills/linear-system-of-record/SKILL.md` with proper SKILL.md frontmatter.
- **D-07:** Keep `skills/05-LINEAR-SYSTEM-OF-RECORD.md` in place as human-readable reference. The two files serve different purposes.
- **D-08:** Other skills are NOT migrated in Phase 1.

### Claude's Discretion

- **Linear verification testing:** Whether to verify Linear operations with live calls to a real workspace or mock at the MCP boundary — Claude decides the test approach that satisfies LINR acceptance criteria.
- **Knowledge Store initialization:** Auto-create `knowledge/` subdirectories on first run or as part of a setup script — Claude decides. Must result in directory structure matching FOUND-04.
- **SKILL.md frontmatter content:** Exact frontmatter fields for `.claude/skills/linear-system-of-record/SKILL.md` (model, allowed-tools, disable-model-invocation, arguments) — Claude decides based on STACK.md guidance.

### Deferred Ideas (OUT OF SCOPE)

- Full skill migration for all 14 skills — deferred to their respective phases (Phase 2+)
- API key fallback for headless/CI Linear auth — not in Phase 1 scope; revisit if CI integration is needed
- `run_loop.py` CLI loop — Phase 3 scope; Phase 1 only builds the Linear Agent verification CLI
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FOUND-01 | Verified MCP connection to the official Linear server using OAuth 2.1 auth | Linear official MCP server + mcp-remote transport; OAuth handled by mcp-remote; setup command documented below |
| FOUND-02 | Python project scaffold with Claude Agent SDK 0.1.73+, pydantic 2.x, typer, rich | PyPI verified: claude-agent-sdk 0.1.73 (latest), pydantic 2.13.3, typer 0.25.1, rich 15.0.0 |
| FOUND-03 | Every agent I/O validated against pydantic schema matching AGENT-CONTRACTS.md | Pydantic v2 `extra="forbid"` + regex field constraints; exact contract models specified in AI-SPEC.md |
| FOUND-04 | Knowledge Store at `knowledge/` with category subdirectories | Flat markdown+YAML-frontmatter; categories: architecture, qa, implementation, patterns, anti-patterns, risk |
| LINR-01 | Create EPIC, User Story, Task, Subtask with correct parent linkage | `mcp__linear__create_issue` with `parentId`; hierarchy verified via re-read |
| LINR-02 | Update status, qa_status, uat_status, assigned_orchestrator via Linear Agent | `mcp__linear__update_issue`; custom fields via Linear label/custom field API |
| LINR-03 | Add structured comment (decision, QA finding, implementation note) | `mcp__linear__create_comment` with structured body |
| LINR-04 | Link GitHub PR URL to Linear work item | `mcp__linear__update_issue` or `mcp__linear__create_comment` with PR URL |
| LINR-05 | Exponential backoff retry + log updatedAt before/after each mutation | PostToolUseFailure hook pattern; pre/post-write re-read via `mcp__linear__get_issue` |
</phase_requirements>

---

## Summary

Phase 1 is a greenfield Python package implementation with no existing `src/` directory, no `pyproject.toml`, and no test infrastructure. The work is anchored in three pre-researched domain artifacts — STACK.md, PITFALLS.md, and AI-SPEC.md — that have already resolved all major technology decisions. The planner does not need to revisit those decisions; this research maps them directly to implementable tasks.

The core deliverable is an `hsb` Python package (installed via `pip install -e .`) that exposes a `typer` CLI where every command invokes the Linear Agent — a validated wrapper around the `mcp__linear__*` MCP tools. The validation layer uses pydantic v2 contract models that exactly mirror `agents/AGENT-CONTRACTS.md`. Write operations implement a read-before / write / read-after pattern for optimistic-lock verification, with exponential backoff on tool failures via the Claude Agent SDK's `PostToolUseFailure` hook.

The phase also bootstraps the Knowledge Store directory tree (`knowledge/` with category subdirectories) and migrates the Linear System of Record skill to `.claude/skills/linear-system-of-record/SKILL.md` with correct SKILL.md frontmatter.

**Primary recommendation:** Build in the order Wave 0 (pyproject.toml + package skeleton) → Wave 1 (pydantic contracts) → Wave 2 (Linear Agent core with hooks) → Wave 3 (typer CLI commands) → Wave 4 (SKILL.md migration + Knowledge Store bootstrap). This ordering ensures each layer is testable before the next is added.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Linear MCP calls (`mcp__linear__*`) | API / Backend (Python process) | — | MCP tool calls are server-side operations in the Python agent process; not browser, not CDN |
| Pydantic contract validation | API / Backend (Python process) | — | I/O validation is a data-layer concern at the agent boundary, not a CLI concern |
| Retry / backoff logic | API / Backend (Python process) | — | Implemented as SDK hooks that intercept at the tool-call layer inside the agent loop |
| CLI entry point (typer) | Frontend (CLI process) | — | CLI is the operator-facing surface; it delegates all business logic to the agent layer |
| SKILL.md auto-discovery | Claude Code runtime | — | `.claude/skills/` path is read by Claude Code and Agent SDK at session start |
| Knowledge Store (directory) | Database / Storage (filesystem) | — | Flat file store; accessed by Glob+Grep; no process owns it exclusively |
| OAuth token cache (~/.mcp-remote/) | OS / System | — | Managed by `mcp-remote`; persists across process invocations |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `claude-agent-sdk` | 0.1.73 (latest on PyPI as of 2026-05-05) | Agent loop, MCP tool execution, lifecycle hooks, session resumption | Mandated by FOUND-02; only SDK with native MCP and SKILL.md support for Claude runtimes |
| `pydantic` | 2.13.3 (latest) | Contract validation for all agent I/O | Mandated by FOUND-02 and FOUND-03; v2 brings strict mode, `extra="forbid"`, regex field validators |
| `typer` | 0.25.1 (latest) | CLI interface for `hsb` commands | Mandated by FOUND-02; type-annotated commands with auto-generated help; synchronous at CLI boundary (safe for `asyncio.run()`) |
| `rich` | 15.0.0 (latest) | Terminal output formatting | Mandated by FOUND-02; colored status, tables for `show current state` |
| `python-dotenv` | 1.2.2 (latest) | `.env` file loading for `ANTHROPIC_API_KEY` | Mandated by FOUND-02; keeps secrets out of code |

**Note:** System already has `rich` 13.7.1 installed globally. pyproject.toml should pin `rich>=13.0` so the project does not require a global upgrade.

[VERIFIED: pip index from PyPI registry, 2026-05-05]

### Supporting (for testing/eval)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 8.x | Test runner | All unit and contract-validation tests |
| `pytest-asyncio` | 0.23+ | Async test support | Testing `async def` agent functions |
| `arize-phoenix` | 4.x | Trace store + eval observability | Optional for Phase 1 dev; required for eval sign-off |

[ASSUMED — versions from AI-SPEC.md; no separate PyPI verification performed]

### Not Installed, Required

| Package | Currently Present | Install Command |
|---------|-----------------|-----------------|
| `claude-agent-sdk` | No | `pip install claude-agent-sdk>=0.1.73` |
| `pydantic` | No (system pip install check returned not installed) | `pip install pydantic>=2.0` |
| `typer` | No | `pip install typer>=0.12` |
| `python-dotenv` | No | `pip install python-dotenv>=1.0` |
| `pytest` | No binary found | `pip install pytest pytest-asyncio` |

[VERIFIED: environment probe 2026-05-05 — python3 12.3 present, npm 11.9.0 present, gh 2.89.0 present, no Python packages installed in project venv]

### Installation

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install claude-agent-sdk>=0.1.73 pydantic>=2.0 typer>=0.12 rich>=13.0 python-dotenv>=1.0
pip install pytest pytest-asyncio  # dev/test dependencies
```

**pyproject.toml (exact content to create):**

```toml
[project]
name = "hsb-agents"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "claude-agent-sdk>=0.1.73",
    "pydantic>=2.0",
    "typer>=0.12",
    "rich>=13.0",
    "python-dotenv>=1.0",
]

[project.scripts]
hsb = "hsb.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/hsb"]

[project.optional-dependencies]
eval = [
    "arize-phoenix>=4.0",
    "opentelemetry-sdk>=1.20",
    "opentelemetry-exporter-otlp>=1.20",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]
```

[CITED: AI-SPEC.md Section 3, pyproject.toml entry]

---

## Architecture Patterns

### System Architecture Diagram

```
Operator (terminal)
       |
       v
[typer CLI — hsb <command>]   ← asyncio.run() boundary
       |
       v
[LinearInput pydantic validation]  ← FOUND-03: validate before dispatch
       |
  invalid → raise ValidationError → CLI prints error, exits 1
       |
  valid
       v
[run_validated_linear_agent()]
       |
       v
[claude_agent_sdk.query()]  ←  ClaudeAgentOptions(
       |                           mcp_servers={"linear": mcp-remote},
       |                           allowed_tools=["mcp__linear__*"],
       |                           hooks=LINEAR_HOOKS,
       |                           system_prompt=...,
       |                           max_turns=20
       |                       )
       |
       |  [SystemMessage subtype=init]  → verify mcp_servers prefix == "mcp__linear__"
       |  [AssistantMessage]            → stream tool calls to terminal ([TOOL] mcp__linear__*)
       |  [PostToolUse hook]            → log to .claude/linear_audit.log
       |  [PostToolUseFailure hook]     → exponential backoff 1s/2s/4s, max 3 retries
       |  [PreCompact hook]             → archive transcript, inject re-read instruction
       |  [ResultMessage]              → capture result_text
       |
       v
[LinearOutput.model_validate(result_text)]  ← extra="forbid", regex on id/url
       |
  invalid → retry prompt with ValidationError details (max 3 attempts)
       |
  valid
       v
[post-write re-read: mcp__linear__get_issue]
       |
  compare pre_updatedAt < post_updatedAt  ← LINR-05 optimistic lock
       |
       v
[rich console output]  →  Operator sees result
       |
       v
[.claude/linear_audit.log]  ← append entry with pre/post updatedAt
```

### Recommended Project Structure

```
task-management-agents/
├── pyproject.toml                        # Package config, deps, entry points [D-05]
├── .env                                  # ANTHROPIC_API_KEY (gitignored)
├── .mcp.json                             # MCP server config (committed, no secrets)
├── .claude/
│   ├── CLAUDE.md                         # Project-level instructions
│   ├── session_cache.json                # Session IDs for resumption (gitignored)
│   ├── linear_audit.log                  # Write audit log (gitignored)
│   └── skills/
│       └── linear-system-of-record/
│           └── SKILL.md                  # Migrated from skills/05-LINEAR-SYSTEM-OF-RECORD.md [D-06]
├── src/
│   └── hsb/                              # [D-03] src layout
│       ├── __init__.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── linear_agent.py           # query() wrapper + run_validated_linear_agent()
│       │   └── hooks.py                  # PostToolUseFailure, PostToolUse, PreCompact, PreToolUse hooks
│       ├── contracts/
│       │   ├── __init__.py
│       │   ├── base.py                   # RuntimeEnvelope, ErrorContract
│       │   └── linear.py                 # LinearInput, LinearOutput, LinearEntity [D-04]
│       └── cli/
│           ├── __init__.py
│           └── main.py                   # typer app: create-issue, update-issue, add-comment, link-pr
├── tests/
│   ├── conftest.py                       # Shared fixtures
│   ├── test_contracts.py                 # Pydantic validation unit tests (FOUND-03)
│   ├── test_hooks.py                     # Retry hook unit tests (LINR-05)
│   └── test_cli.py                       # CLI smoke tests (LINR-01 through LINR-05)
├── knowledge/                            # [FOUND-04]
│   ├── architecture/
│   ├── qa/
│   ├── implementation/
│   ├── patterns/
│   ├── anti-patterns/
│   └── risk/
└── skills/
    └── 05-LINEAR-SYSTEM-OF-RECORD.md    # Human-readable reference (kept per D-07)
```

### Pattern 1: Linear Agent Entry Point (query() wrapper)

**What:** An async function that executes one Linear operation by running the Claude Agent SDK loop, streaming output to terminal, and returning the result text for downstream pydantic validation.

**When to use:** Every CLI command delegates to this function. It is stateless — receives full input each call.

```python
# Source: AI-SPEC.md Section 3, Entry Point Pattern
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, SystemMessage, AssistantMessage, ResultMessage
from dotenv import load_dotenv

load_dotenv()

async def run_linear_agent(prompt: str) -> str | None:
    options = ClaudeAgentOptions(
        mcp_servers={
            "linear": {
                "command": "npx",
                "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
            }
        },
        allowed_tools=["mcp__linear__*"],
        permission_mode="acceptEdits",
        system_prompt=(
            "You are the Linear Agent for the HSBTech AI Engineering Workflow. "
            "You manage Linear work items via the mcp__linear__* tools. "
            "Validate all inputs against the contract schema before calling tools. "
            "On tool failure, retry up to 3 times with exponential backoff (1s, 2s, 4s). "
            "Always confirm writes by re-reading the updated entity via mcp__linear__get_issue. "
            "Return your result as a JSON object matching LinearOutput schema."
        ),
        max_turns=20,
        hooks=LINEAR_HOOKS,  # from hooks.py
    )

    result_text = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            mcp_servers = message.data.get("mcp_servers", [])
            failed = [s for s in mcp_servers if s.get("status") != "connected"]
            if failed:
                raise RuntimeError(f"Linear MCP failed to connect: {failed}")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text"):
                    print(block.text)
                elif hasattr(block, "name"):
                    print(f"[TOOL] {block.name}")
        elif isinstance(message, ResultMessage):
            if message.subtype == "success":
                result_text = message.result
            else:
                raise RuntimeError(f"Agent failed: {message.subtype}")
    return result_text
```

### Pattern 2: Pydantic Contract Models (exact mirror of AGENT-CONTRACTS.md)

**What:** Pydantic v2 models with `extra="forbid"` and regex constraints that exactly mirror `agents/AGENT-CONTRACTS.md`. No new fields are invented.

**When to use:** Validate every response from `run_linear_agent()` before returning to CLI.

```python
# Source: AI-SPEC.md Section 4b.1
from __future__ import annotations
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class LinearOperation(str, Enum):
    create = "create"
    update = "update"
    read = "read"
    link = "link"
    comment = "comment"
    create_subtasks = "create_subtasks"

class LinearInput(BaseModel):
    operation: LinearOperation
    payload: dict
    model_config = {"extra": "forbid"}

class LinearEntity(BaseModel):
    id: str = Field(..., pattern=r"^LIN-\d+$")
    type: Literal["epic", "user_story", "task", "subtask"]
    url: str = Field(..., pattern=r"^https://linear\.app/")

class LinearOutput(BaseModel):
    operation: str
    result: Literal["success", "failed"]
    linear_entities: list[LinearEntity] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def failed_must_have_error(self) -> LinearOutput:
        if self.result == "failed" and not self.error:
            raise ValueError("failed result must include error message")
        return self

    model_config = {"extra": "forbid"}
```

### Pattern 3: PostToolUseFailure Hook (exponential backoff)

**What:** A Claude Agent SDK lifecycle hook that fires when a `mcp__linear__*` tool call fails. Implements exponential backoff (1s, 2s, 4s) with a 3-retry cap. Returns a `systemMessage` instruction telling the agent to retry.

**When to use:** Wire into `ClaudeAgentOptions(hooks=...)` for all Linear Agent invocations.

```python
# Source: AI-SPEC.md Section 4, Core Pattern — Retry/Backoff Hook
import asyncio
from claude_agent_sdk import HookMatcher

_retry_counts: dict[str, int] = {}
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0

async def linear_retry_hook(input_data: dict, tool_use_id: str | None, context) -> dict:
    tool_name = input_data.get("tool_name", "")
    if not tool_name.startswith("mcp__linear__"):
        return {}
    key = tool_use_id or tool_name
    retry_count = _retry_counts.get(key, 0)
    if retry_count >= MAX_RETRIES:
        _retry_counts.pop(key, None)
        return {
            "systemMessage": (
                f"Linear tool {tool_name} failed after {MAX_RETRIES} retries. "
                "Do not retry. Return status='failed' with error_type='tool_failure'."
            )
        }
    delay = BASE_DELAY_SECONDS * (2 ** retry_count)
    _retry_counts[key] = retry_count + 1
    await asyncio.sleep(delay)
    return {
        "systemMessage": (
            f"Linear tool {tool_name} failed (attempt {retry_count + 1}/{MAX_RETRIES}). "
            f"Waited {delay:.0f}s. Retry the same tool call now."
        )
    }
```

### Pattern 4: SKILL.md Frontmatter (linear-system-of-record)

**What:** The SKILL.md frontmatter fields that control Claude Code / Agent SDK auto-discovery behavior.

**When to use:** Creating `.claude/skills/linear-system-of-record/SKILL.md` from `skills/05-LINEAR-SYSTEM-OF-RECORD.md`.

```yaml
# Source: STACK.md — SKILL.md frontmatter fields section
---
name: linear-system-of-record
description: |
  Manages Linear work items as the operational state engine for the HSBTech delivery pipeline.
  Only invoke when: an explicit Linear operation is requested (create, update, comment, link PR).
  Do NOT invoke for read-only reporting or conversational queries about project status.
disable-model-invocation: true
allowed-tools:
  - mcp__linear__create_issue
  - mcp__linear__update_issue
  - mcp__linear__get_issue
  - mcp__linear__list_issues
  - mcp__linear__create_comment
  - mcp__linear__list_projects
  - mcp__linear__list_teams
arguments:
  - name: operation
    description: "The Linear operation to perform: create | update | read | link | comment | create_subtasks"
  - name: payload
    description: "JSON payload for the operation (matches LinearInput contract)"
---
```

**Key decisions:** `disable-model-invocation: true` is required because Linear write operations are side-effecting — they must only be triggered by explicit operator CLI commands, never by Claude's auto-invocation during conversation. [CITED: STACK.md, Pitfall 7]

### Pattern 5: Knowledge Store Bootstrap

**What:** Create the `knowledge/` directory tree with the 6 required category subdirectories and a `.gitkeep` in each (to commit empty dirs).

**When to use:** Wave 0 of implementation — directory must exist before any agent writes knowledge entries.

```bash
# Per FOUND-04: category subdirectories from REQUIREMENTS.md + STACK.md
mkdir -p knowledge/{architecture,qa,implementation,patterns,anti-patterns,risk}
touch knowledge/{architecture,qa,implementation,patterns,anti-patterns,risk}/.gitkeep
```

**Note:** REQUIREMENTS.md names the categories as `architecture, qa, implementation, backlog, risk`. STACK.md adds `patterns` and `anti-patterns` and omits `backlog`. The AI-SPEC project structure uses `patterns, anti-patterns`. Claude's discretion (per CONTEXT.md) applies — recommend following STACK.md/AI-SPEC.md which adds patterns and anti-patterns and replaces backlog with them (backlog is tracked in Linear, not the knowledge store).

[CITED: STACK.md — File-Based Knowledge Store section; REQUIREMENTS.md — FOUND-04]

### Anti-Patterns to Avoid

- **Using `mcp__claude_ai_Linear__` prefix in SKILL.md or system prompts:** This is the Claude.ai browser session prefix. In Agent SDK Python sessions, the prefix derives from the `mcp_servers` key (`"linear"` → `mcp__linear__`). Using the wrong prefix causes silent tool resolution failures. [CITED: AI-SPEC.md Section 3, Pitfall 1]
- **Setting `permission_mode="acceptEdits"` and expecting MCP tools to work:** `acceptEdits` only auto-approves filesystem tools. MCP tools (`mcp__linear__*`) require explicit `allowed_tools` entries. [CITED: AI-SPEC.md Section 3, Pitfall 2]
- **Calling `mcp__linear__list_issues` without `teamId` or `projectId` filter:** An unfiltered list can return thousands of issue tokens, exhausting the context budget before the agent can act. Always filter. [CITED: AI-SPEC.md Section 4b.4]
- **Calling `asyncio.run()` inside a running event loop:** Typer callbacks are synchronous — safe to use `asyncio.run()` at the CLI boundary. Never nest `asyncio.run()` inside a coroutine. [CITED: AI-SPEC.md Section 4b.2]
- **Leaving pydantic models in lax mode:** Silent type coercion (`"123"` accepted for an `int` field) masks schema drift. All models must use `model_config = {"extra": "forbid"}`. [CITED: AI-SPEC.md Section 1b, Domain Failure Mode 1]
- **Using `requirements.txt` instead of `pyproject.toml`:** Violates D-05; breaks `pip install -e .` entry-point registration.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Agent loop with tool execution | Manual `anthropic` client + tool dispatch loop | `claude_agent_sdk.query()` | SDK handles context compaction, hooks, MCP transport, session resumption; manual loop misses all of these |
| Retry / backoff on MCP failures | Custom try/except with sleep | `PostToolUseFailure` hook in `ClaudeAgentOptions` | Hook fires at the correct level (tool call layer); custom wrapper fires too late and can't inject retry instructions into the agent context |
| MCP server connection | Direct HTTP to Linear GraphQL | `npx -y mcp-remote https://mcp.linear.app/mcp` | OAuth 2.1 flow and token refresh are handled by `mcp-remote`; direct GraphQL requires manual auth, pagination, and schema maintenance |
| CLI argument parsing | `argparse` | `typer` | Typer provides type-annotated commands, auto-generated `--help`, and clean integration with async entry points with far less boilerplate |
| Linear state persistence | Custom SQLite or JSON file | Linear via `mcp__linear__*` tools | Linear is the mandated system of record (AGENTS.md, RUNTIME-EXECUTION.md); any side-store creates state drift |

**Key insight:** The Claude Agent SDK abstracts the hardest problems in agentic systems (context management, tool retries, MCP transport, session state). Every piece of custom code that duplicates SDK functionality is code that will drift and break as the SDK evolves.

---

## Common Pitfalls

### Pitfall 1: MCP Tool Prefix Mismatch (Silent Runtime Failure)

**What goes wrong:** SKILL.md or system prompt references `mcp__claude_ai_Linear__create_issue`. In the Python SDK runtime, the prefix is determined by the `mcp_servers` dict key: `{"linear": ...}` → `mcp__linear__`. The agent silently fails to resolve tools and either loops or hallucinates success.

**Why it happens:** The Claude.ai browser interface uses a different prefix (`mcp__claude_ai_Linear__`) that appears in documentation screenshots and community examples.

**How to avoid:** Always check the `SystemMessage(subtype="init")` `mcp_servers` field at session start to confirm the active prefix. Hard-code `mcp__linear__` in all system prompts and SKILL.md files.

**Warning signs:** No `[TOOL] mcp__linear__*` lines appear in CLI output during an operation that should write to Linear. Agent returns a result without any tool calls logged.

[CITED: AI-SPEC.md Section 3 Pitfall 1; STACK.md Linear MCP section]

### Pitfall 2: permission_mode Does Not Grant MCP Access

**What goes wrong:** Developer sets `permission_mode="acceptEdits"` expecting it covers all tools. MCP tools (`mcp__linear__*`) are blocked because they require explicit `allowed_tools` entries.

**How to avoid:** Always include `allowed_tools=["mcp__linear__*"]` (or enumerate specific tools) in `ClaudeAgentOptions`. The `permission_mode` controls filesystem/Bash tool permissions only.

[CITED: AI-SPEC.md Section 3 Pitfall 2]

### Pitfall 3: OAuth Token Missing in Non-Interactive Environments

**What goes wrong:** First `query()` call with the Linear MCP opens a browser tab for OAuth 2.1. In a terminal-only session without a browser, this blocks indefinitely.

**How to avoid:** Pre-warm the OAuth token by running one interactive `query()` call in a browser-available environment. The token is cached at `~/.mcp-remote/`. For CI: pass `LINEAR_API_KEY` via the server's `env` field (deferred to Phase 2+ per D-01/D-02, but document the fallback).

**Warning signs:** `query()` hangs on first call with no terminal output.

[CITED: AI-SPEC.md Section 3 Pitfall 3]

### Pitfall 4: Unfiltered list_issues Context Overflow

**What goes wrong:** `mcp__linear__list_issues` without filters returns all workspace issues. At scale this exhausts the context budget mid-session, triggering compaction and silently dropping behavioral instructions.

**How to avoid:** Pass a `PreToolUse` hook that blocks `list_issues` calls without `teamId` or `projectId`. Additionally enforce the filter requirement in the system prompt.

[CITED: AI-SPEC.md Section 4b.4; PITFALLS.md Pitfall 5]

### Pitfall 5: Stale updatedAt on Optimistic Lock (False Positive)

**What goes wrong:** The pre-write `updatedAt` read is cached or performed several turns earlier. A concurrent mutation occurs between that read and the write. The agent's post-write comparison uses the stale pre-write timestamp and reports the write as clean when it was not.

**How to avoid:** Always read `updatedAt` via `mcp__linear__get_issue` immediately before the write (same invocation, consecutive tool calls). Log both timestamps in the audit entry. Compare `post_updatedAt > pre_updatedAt` strictly.

[CITED: AI-SPEC.md Section 1b, Write Atomicity dimension; PITFALLS.md Pitfall 4]

### Pitfall 6: Linear Issue Hierarchy — parentId Must Be Set at Create Time

**What goes wrong:** Issues are created flat (no `parentId`), then a second call attempts to set the parent. Linear's MCP `update_issue` may not support reparenting for all issue types. Creating with wrong hierarchy requires manual cleanup.

**How to avoid:** Always set `parentId` in the `create_issue` payload — never create then reparent. For EPIC creation, `parentId` is not set (EPICs are top-level). User Stories set `parentId` to EPIC id. Tasks set `parentId` to User Story id. Subtasks set `parentId` to Task id.

[CITED: AGENT-CONTRACTS.md Global State Model; LINR-01 requirement]

### Pitfall 7: pydantic Extra Fields Silently Accepted

**What goes wrong:** A pydantic model without `extra="forbid"` silently ignores unknown fields in agent output. Schema drift between `AGENT-CONTRACTS.md` and `src/hsb/contracts/` goes undetected.

**How to avoid:** Every model in `src/hsb/contracts/` must have `model_config = {"extra": "forbid"}`. Add a pytest parametrized test that deliberately feeds a payload with an extra field and asserts `ValidationError` is raised.

[CITED: AI-SPEC.md Section 1b, Domain Failure Mode 1; FOUND-03]

---

## Code Examples

### MCP Server Setup via Claude Code CLI (one-time)

```bash
# Source: STACK.md — Linear MCP Integration section
claude mcp add-json linear '{"command":"npx","args":["-y","mcp-remote","https://mcp.linear.app/mcp"]}'
```

This writes to `.mcp.json` which should be committed to the repo (no secrets — OAuth token is stored separately by mcp-remote).

### Full ClaudeAgentOptions with All Hooks

```python
# Source: AI-SPEC.md Section 4 — Implementation Guidance
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

LINEAR_HOOKS = {
    "PostToolUseFailure": [
        HookMatcher(matcher="^mcp__linear__", hooks=[linear_retry_hook])
    ],
    "PostToolUse": [
        HookMatcher(matcher="^mcp__linear__", hooks=[linear_audit_hook])
    ],
    "PreCompact": [
        HookMatcher(hooks=[pre_compact_handler])
    ],
    "PreToolUse": [
        HookMatcher(matcher="mcp__linear__list_issues", hooks=[enforce_list_filters])
    ],
}

options = ClaudeAgentOptions(
    mcp_servers={
        "linear": {
            "command": "npx",
            "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
        }
    },
    allowed_tools=["mcp__linear__*"],
    permission_mode="acceptEdits",
    system_prompt="...",  # See Pattern 1 above
    max_turns=20,
    hooks=LINEAR_HOOKS,
)
```

### typer CLI Command Structure

```python
# Source: AI-SPEC.md Section 3, Key Abstractions (typer pattern)
import asyncio
import typer
from rich.console import Console
from hsb.agents.linear_agent import run_validated_linear_agent

app = typer.Typer(name="hsb", help="HSBTech AI Engineering Workflow CLI")
console = Console()

@app.command("create-issue")
def create_issue(
    title: str = typer.Option(..., "--title", help="Issue title"),
    type: str = typer.Option("task", "--type", help="epic|user_story|task|subtask"),
    parent_id: str = typer.Option(None, "--parent-id", help="Linear ID of parent issue"),
    team_id: str = typer.Option(..., "--team-id", help="Linear team ID"),
):
    """Create a Linear issue with correct parent linkage (LINR-01)."""
    result = asyncio.run(
        run_validated_linear_agent(
            operation="create",
            payload={"title": title, "type": type, "parentId": parent_id, "teamId": team_id},
        )
    )
    console.print(result)
```

### Knowledge Store Entry Format

```yaml
# Source: STACK.md — File-Based Knowledge Store, frontmatter schema
---
title: "PostToolUseFailure hook resolves mcp__linear__ retry storm"
type: architecture
context: "phase-1-foundation"
evidence:
  linear_issue: "LIN-5"
  pr: "https://github.com/org/repo/pull/12"
  files: ["src/hsb/agents/hooks.py"]
  qa_finding: ""
insight: "Without MAX_RETRIES=3 cap, transient Linear API errors cause unbounded retry loops that exhaust max_turns budget"
recommendation: "Always cap retry count and enforce minimum delay via PostToolUseFailure hook"
applicability: "Any agent that calls mcp__linear__* tools under unreliable network conditions"
date: "2026-05-05"
---
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Community Linear MCP servers (jerhadf, tacticlaunch) | Official Linear MCP server (mcp.linear.app) | May 2025 (Linear changelog) | Official server supersedes all community alternatives; use only the official server |
| Plain `.md` files in repo root as "skills" | `.claude/skills/<name>/SKILL.md` with frontmatter | Claude Code skills spec (current) | Enables progressive disclosure loading, `disable-model-invocation`, `allowed-tools` frontmatter |
| `requirements.txt` + bare `setup.py` | `pyproject.toml` with `hatchling` backend | PEP 518/660 (2017/2021), industry standard by 2024 | Named entry points (`hsb = "hsb.cli.main:app"`), `pip install -e .`, clean dependency pinning |
| Anthropic Python SDK (`anthropic`) for agent loops | `claude-agent-sdk` | 2024 (SDK GA) | SDK handles tool loop, MCP, hooks, context compaction automatically |

**Deprecated/outdated:**

- `langchain-linear` or any third-party Linear Python client: Use the official MCP server exclusively. Do not call Linear's GraphQL API directly. [CITED: STACK.md "Do NOT use" list]
- `click` for CLI: typer supersedes it with type annotations. [CITED: STACK.md Alternatives Considered]
- `anthropic` client SDK for orchestration: requires manual tool loop; `claude-agent-sdk` is the correct choice. [CITED: STACK.md "Do NOT use" list]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `arize-phoenix>=4.0` and `pytest-asyncio>=0.23` are the correct minimum versions | Standard Stack (Supporting) | Planner includes wrong version pin; fixable on first install |
| A2 | SKILL.md `arguments` frontmatter field syntax matches current Claude Code skills spec | Pattern 4 | SKILL.md may not be parsed correctly; content still loads but argument substitution fails |
| A3 | Knowledge Store categories should be `{architecture, qa, implementation, patterns, anti-patterns, risk}` (following STACK.md/AI-SPEC.md) rather than `{architecture, qa, implementation, backlog, risk}` (following REQUIREMENTS.md FOUND-04) | Pattern 5, Knowledge Store Bootstrap | If REQUIREMENTS.md is authoritative, the `patterns` and `anti-patterns` dirs are extra (harmless) and `backlog` dir is missing (could cause FOUND-04 test failure) |

**Mitigation for A3:** FOUND-04 says "category subdirectories (architecture, qa, implementation, backlog, risk)". The plan should create all 6 dirs from REQUIREMENTS.md **plus** `patterns` and `anti-patterns` as additional dirs — this satisfies FOUND-04 while matching STACK.md's richer structure.

---

## Open Questions

1. **Linear custom fields for `qa_status`, `uat_status`, `assigned_orchestrator`**
   - What we know: `mcp__linear__update_issue` updates standard Linear fields (status, assignee, priority). Linear supports custom fields via the GraphQL API.
   - What's unclear: Whether `mcp__linear__update_issue` exposes custom field updates via the MCP tool, or whether `qa_status` / `uat_status` / `assigned_orchestrator` must be implemented as Linear labels, issue description metadata, or comments rather than true custom fields.
   - Recommendation: Implement LINR-02's `qa_status` / `uat_status` / `assigned_orchestrator` as structured comment data and/or labels in Phase 1. If the MCP tool exposes custom field updates, use them. Verify at runtime by inspecting the tool's input schema in `SystemMessage(subtype="init")`. Do not block Phase 1 on this ambiguity.

2. **Whether pytest tests should mock at the MCP boundary or hit a real Linear workspace**
   - What we know: Claude's discretion per CONTEXT.md. Mocking avoids external dependency but cannot verify real MCP connectivity (FOUND-01).
   - What's unclear: Whether a test Linear workspace is available for Phase 1 validation.
   - Recommendation: Unit tests mock at the `run_linear_agent()` boundary (inject pre-canned result text, test pydantic validation and hook logic). One integration smoke test hits the real Linear MCP to satisfy FOUND-01. The integration test is marked `@pytest.mark.integration` and excluded from CI runs that lack `ANTHROPIC_API_KEY` + `LINEAR_API_KEY`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All Python code | Yes | 3.12.3 | — |
| npm / npx | mcp-remote transport | Yes | 11.9.0 | — |
| Node.js | mcp-remote transport | Yes | v24.14.0 | — |
| gh CLI | GitHub PR linking (LINR-04) | Yes | 2.89.0 | — |
| claude-agent-sdk | Agent loop | No (not installed) | — | Must install |
| pydantic | Contract validation | No (not installed) | — | Must install |
| typer | CLI | No (not installed) | — | Must install |
| python-dotenv | Env loading | No (not installed) | — | Must install |
| pytest | Testing | No (not installed) | — | Must install |
| .venv | Isolated Python env | No (not created) | — | `python3 -m venv .venv` |

**Missing dependencies with no fallback (block execution):**

- Python virtual environment must be created before any `pip install`
- `claude-agent-sdk`, `pydantic`, `typer`, `python-dotenv` must be installed
- `ANTHROPIC_API_KEY` environment variable must be set before any `query()` call

**Missing dependencies with fallback:**

- `pytest` — can defer testing; not needed for initial Linear Agent functionality

[VERIFIED: environment probe 2026-05-05]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (not yet installed) |
| Config file | `pyproject.toml` (add `[tool.pytest.ini_options]` section) |
| Quick run command | `pytest tests/test_contracts.py tests/test_hooks.py -x` |
| Full suite command | `pytest tests/ -x --ignore=tests/test_integration.py` |
| Integration suite | `pytest tests/test_integration.py -x -m integration` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOUND-01 | Linear MCP connection established; tool prefix verified | integration | `pytest tests/test_integration.py::test_mcp_connection -x -m integration` | No — Wave 0 |
| FOUND-02 | pyproject.toml exists; `pip install -e .` succeeds; `hsb --help` works | smoke | `pip install -e . && hsb --help` | No — Wave 0 |
| FOUND-03 | Valid payload passes LinearOutput.model_validate(); extra fields raise ValidationError | unit | `pytest tests/test_contracts.py -x` | No — Wave 0 |
| FOUND-04 | `knowledge/` directory exists with all required subdirectories | smoke | `pytest tests/test_knowledge_store.py::test_directories_exist -x` | No — Wave 0 |
| LINR-01 | Create EPIC, User Story, Task, Subtask with correct parentId | integration | `pytest tests/test_integration.py::test_create_hierarchy -x -m integration` | No — Wave 0 |
| LINR-02 | Update status, qa_status, uat_status, assigned_orchestrator | integration | `pytest tests/test_integration.py::test_update_fields -x -m integration` | No — Wave 0 |
| LINR-03 | Add structured comment to a Linear issue | integration | `pytest tests/test_integration.py::test_add_comment -x -m integration` | No — Wave 0 |
| LINR-04 | Link PR URL to a Linear issue | integration | `pytest tests/test_integration.py::test_link_pr -x -m integration` | No — Wave 0 |
| LINR-05 | Retry fires with 1s/2s/4s delays; max 3 attempts; updatedAt before/after logged | unit | `pytest tests/test_hooks.py::test_retry_backoff tests/test_hooks.py::test_updated_at_logging -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_contracts.py tests/test_hooks.py -x`
- **Per wave merge:** `pytest tests/ -x --ignore=tests/test_integration.py`
- **Phase gate:** Full suite including integration tests green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/conftest.py` — shared fixtures (mock Linear MCP response payloads, sample LinearOutput JSON)
- [ ] `tests/test_contracts.py` — pydantic validation unit tests (FOUND-03, schema drift detection)
- [ ] `tests/test_hooks.py` — retry hook unit tests (LINR-05 timing, attempt count, updatedAt logic)
- [ ] `tests/test_knowledge_store.py` — directory existence smoke test (FOUND-04)
- [ ] `tests/test_integration.py` — live MCP tests marked `@pytest.mark.integration` (FOUND-01, LINR-01 through LINR-05)
- [ ] Framework install: `pip install pytest pytest-asyncio`
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and `markers = ["integration: requires live Linear MCP connection"]`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes (Linear OAuth 2.1) | mcp-remote handles token; no custom auth code |
| V3 Session Management | Yes (session_cache.json) | Gitignore session_cache.json; do not commit session IDs |
| V4 Access Control | No | Internal operator tool; single user |
| V5 Input Validation | Yes | Pydantic v2 with `extra="forbid"` and regex constraints on all contract models |
| V6 Cryptography | No | No encryption of data; secrets via env vars only |

### Key Security Controls

- `ANTHROPIC_API_KEY` and `LINEAR_API_KEY` must be in `.env` (gitignored) — never hardcoded
- `.mcp.json` (committed) must contain no secrets — only the `npx mcp-remote` command
- `session_cache.json` and `linear_audit.log` must be gitignored
- Pydantic regex constraint `^LIN-\d+$` on `id` fields prevents injection of arbitrary strings into Linear issue IDs

[ASSUMED — ASVS mapping based on training knowledge; no formal security review performed]

---

## Sources

### Primary (HIGH confidence)

- `.planning/research/STACK.md` — HSBTech-specific: Linear MCP setup, OAuth, confirmed tool names, library versions, SKILL.md frontmatter spec; compiled from official Anthropic + Linear docs 2026-05-05
- `.planning/research/PITFALLS.md` — domain pitfall taxonomy; pitfalls 1-13 directly applicable to Phase 1 planning
- `.planning/phases/01-foundation-and-linear-integration/01-AI-SPEC.md` — implementation contracts, exact pydantic models, hook patterns, project structure, eval dimensions; compiled from official Claude Agent SDK docs 2026-05-05
- `agents/AGENT-CONTRACTS.md` — canonical contract schemas; pydantic models must mirror exactly
- `agents/AGENTS.md` — agent boundary definitions; Linear Agent scope
- `runtime/RUNTIME-EXECUTION.md` — state model and execution rules
- PyPI registry (via `pip index versions`) — verified package versions 2026-05-05

### Secondary (MEDIUM confidence)

- `skills/05-LINEAR-SYSTEM-OF-RECORD.md` — behavioral spec for SKILL.md migration; project-authored, not verified against external source

### Tertiary (LOW confidence)

- ASVS category mapping — based on training knowledge; no tool-verified ASVS review performed

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all package versions verified against PyPI registry 2026-05-05
- Architecture: HIGH — derived directly from AI-SPEC.md and STACK.md which were themselves sourced from official Anthropic and Linear documentation
- Pitfalls: HIGH — sourced from project's PITFALLS.md (HIGH/MEDIUM confidence ratings documented there)
- Test approach: MEDIUM — Claude's discretion applies per CONTEXT.md; integration vs. mock split is a recommendation not a locked decision

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (stable stack; `claude-agent-sdk` minor versions may update but 0.1.73+ pin is sufficient)
