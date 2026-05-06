# Phase 1: Foundation and Linear Integration - Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 11 new files to create
**Analogs found:** 0 / 11 (greenfield — no source code exists in this repo)

> **Greenfield note:** The repository contains only markdown documentation. No Python source code, no pyproject.toml, no tests exist yet. Every pattern below is derived from the project's own pre-researched specification documents — `01-AI-SPEC.md`, `01-RESEARCH.md`, and `STACK.md` — which were authored against official Anthropic and Linear documentation. All code excerpts below are canonical: copy them verbatim, do not paraphrase.

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `pyproject.toml` | config | — | None (greenfield) | none |
| `.mcp.json` | config | — | None (greenfield) | none |
| `src/hsb/__init__.py` | package-init | — | None (greenfield) | none |
| `src/hsb/agents/__init__.py` | package-init | — | None (greenfield) | none |
| `src/hsb/agents/linear_agent.py` | service | request-response (async query loop) | `01-AI-SPEC.md` §3 Entry Point Pattern | spec-derived |
| `src/hsb/agents/hooks.py` | middleware | event-driven (SDK lifecycle hooks) | `01-AI-SPEC.md` §4 Core Pattern | spec-derived |
| `src/hsb/contracts/__init__.py` | package-init | — | None (greenfield) | none |
| `src/hsb/contracts/linear.py` | model | CRUD (pydantic validate) | `01-AI-SPEC.md` §4b.1 + `AGENT-CONTRACTS.md` §2 | spec-derived |
| `src/hsb/contracts/base.py` | model | CRUD (pydantic validate) | `01-AI-SPEC.md` §4b.1 + `AGENT-CONTRACTS.md` envelopes | spec-derived |
| `src/hsb/cli/__init__.py` | package-init | — | None (greenfield) | none |
| `src/hsb/cli/main.py` | controller | request-response (typer CLI → asyncio.run) | `01-AI-SPEC.md` §4b.2 + `01-RESEARCH.md` Pattern §typer | spec-derived |
| `src/hsb/observability.py` | utility | event-driven (OTLP spans) | `01-AI-SPEC.md` §7 | spec-derived |
| `tests/conftest.py` | test | — | None (greenfield) | none |
| `tests/test_contracts.py` | test | CRUD (unit) | `01-AI-SPEC.md` §5 Reference Dataset | spec-derived |
| `tests/test_hooks.py` | test | event-driven (unit) | `01-AI-SPEC.md` §5 Reference Dataset | spec-derived |
| `tests/test_integration.py` | test | request-response (integration) | `01-AI-SPEC.md` §5 Reference Dataset | spec-derived |
| `.claude/skills/linear-system-of-record/SKILL.md` | config | — | `skills/05-LINEAR-SYSTEM-OF-RECORD.md` (body) + `STACK.md` §SKILL.md frontmatter (structure) | content-derived |
| `knowledge/` directory tree | storage | file-I/O | `STACK.md` §File-Based Knowledge Store | spec-derived |

---

## Pattern Assignments

### `pyproject.toml` (config)

**Source:** `01-RESEARCH.md` Standard Stack section; `01-AI-SPEC.md` §3 Installation

**Exact content to create** (do not modify version pins):

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

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: requires live Linear MCP connection and ANTHROPIC_API_KEY",
]
```

**Critical:** Entry point is `hsb.cli.main:app` not `hsb.cli.main:main`. The `[tool.hatch.build.targets.wheel]` `packages` key must be `["src/hsb"]` to match the src layout (D-05).

---

### `.mcp.json` (config)

**Source:** `STACK.md` §Linear MCP Integration; `01-AI-SPEC.md` §3

**Exact content to create** (committed, no secrets):

```json
{
  "mcpServers": {
    "linear": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"]
    }
  }
}
```

**Critical:** The key `"linear"` determines the MCP tool prefix at runtime: `mcp__linear__*`. Never use `"Linear"` (case-sensitive). This file is committed. OAuth token is stored separately by mcp-remote at `~/.mcp-remote/` and must NOT appear here.

---

### `src/hsb/agents/linear_agent.py` (service, request-response)

**Source:** `01-AI-SPEC.md` §3 Entry Point Pattern + §4b.1 Validation and Retry Pattern

**Imports pattern** (`01-AI-SPEC.md` §3, lines 228-238):

```python
import asyncio
import json
import logging
import os
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    SystemMessage,
    AssistantMessage,
    ResultMessage,
)
from dotenv import load_dotenv
from pydantic import ValidationError
from hsb.contracts.linear import LinearOutput
from hsb.agents.hooks import LINEAR_HOOKS

load_dotenv()

logger = logging.getLogger(__name__)
```

**Core async query pattern** (`01-AI-SPEC.md` §3, lines 242-298):

```python
async def run_linear_agent(prompt: str) -> str | None:
    """Execute one Linear Agent turn. Returns the result string or None on failure."""
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        mcp_servers={
            "linear": {
                "command": "npx",
                "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
                # For headless/CI: "env": {"LINEAR_API_KEY": os.environ["LINEAR_API_KEY"]},
            }
        },
        allowed_tools=["mcp__linear__*"],
        permission_mode="acceptEdits",
        system_prompt=(
            "You are the Linear Agent for the HSBTech AI Engineering Workflow. "
            "You manage Linear work items via the mcp__linear__* tools. "
            "You MUST validate all inputs against the contract schema before calling tools. "
            "On tool failure, retry up to 3 times with exponential backoff (1s, 2s, 4s). "
            "Always confirm the write was successful by re-reading the updated entity via "
            "mcp__linear__get_issue. Return your result as a JSON object matching LinearOutput schema."
        ),
        max_turns=20,
        hooks=LINEAR_HOOKS,
    )

    result_text = None

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            session_id = message.data.get("session_id")
            mcp_servers = message.data.get("mcp_servers", [])
            failed = [s for s in mcp_servers if s.get("status") != "connected"]
            if failed:
                raise RuntimeError(f"Linear MCP server failed to connect: {failed}")
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

**Validation and retry layer pattern** (`01-AI-SPEC.md` §4b.1, lines 660-719):

```python
MAX_VALIDATION_RETRIES = 3

async def run_validated_linear_agent(
    operation: str,
    payload: dict,
) -> LinearOutput:
    """
    Run Linear Agent and validate result against LinearOutput.
    Retries up to MAX_VALIDATION_RETRIES on validation failure.
    """
    prompt = (
        f"Execute Linear operation '{operation}' with this payload:\n"
        f"```json\n{json.dumps(payload, indent=2)}\n```\n\n"
        "Return your result as a JSON object matching this schema:\n"
        "{ operation, result: 'success'|'failed', linear_entities: [...], error?: string }"
    )

    last_error = None

    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        result_text = await run_linear_agent(prompt)

        if result_text is None:
            logger.warning("Attempt %d: agent returned None result", attempt)
            continue

        try:
            json_start = result_text.index("{")
            json_end = result_text.rindex("}") + 1
            raw = json.loads(result_text[json_start:json_end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning("Attempt %d: could not parse JSON: %s", attempt, e)
            last_error = e
            prompt += f"\n\nPrevious attempt returned invalid JSON: {e}. Return ONLY valid JSON."
            continue

        try:
            output = LinearOutput.model_validate(raw)
            logger.info("Attempt %d: validation succeeded", attempt)
            return output
        except ValidationError as e:
            last_error = e
            logger.warning("Attempt %d: LinearOutput validation failed:\n%s", attempt, e.json(indent=2))
            prompt += (
                f"\n\nPrevious attempt returned invalid output. Validation errors:\n"
                f"{e.json(indent=2)}\nFix these errors and return corrected JSON."
            )

    raise ValueError(
        f"Linear Agent failed validation after {MAX_VALIDATION_RETRIES} attempts. "
        f"Last error: {last_error}"
    )
```

---

### `src/hsb/agents/hooks.py` (middleware, event-driven)

**Source:** `01-AI-SPEC.md` §4 Core Pattern (lines 418-506) and §4b.4 (lines 823-871)

**Imports pattern:**

```python
import asyncio
import json
import shutil
from datetime import datetime, timezone
from claude_agent_sdk import HookMatcher
```

**PostToolUseFailure hook — exponential backoff** (`01-AI-SPEC.md` §4, lines 429-467):

```python
_retry_counts: dict[str, int] = {}
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0


async def linear_retry_hook(input_data: dict, tool_use_id: str | None, context) -> dict:
    """PostToolUseFailure hook: exponential backoff for mcp__linear__* failures."""
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

**PostToolUse hook — audit log** (`01-AI-SPEC.md` §4, lines 470-506):

```python
async def linear_audit_hook(input_data: dict, tool_use_id: str | None, context) -> dict:
    """PostToolUse hook: logs every successful mcp__linear__* call."""
    tool_name = input_data.get("tool_name", "")
    if not tool_name.startswith("mcp__linear__"):
        return {}

    if tool_use_id:
        _retry_counts.pop(tool_use_id, None)

    asyncio.create_task(_write_audit_log(tool_name, input_data))
    return {"async_": True, "asyncTimeout": 5000}


async def _write_audit_log(tool_name: str, input_data: dict) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "output": input_data.get("tool_output", {}),
    }
    with open(".claude/linear_audit.log", "a") as f:
        f.write(json.dumps(entry) + "\n")
```

**PreCompact hook — transcript archive** (`01-AI-SPEC.md` §4b.4, lines 823-842):

```python
async def pre_compact_handler(input_data: dict, tool_use_id: str | None, context) -> dict:
    """Archive transcript before SDK auto-compaction."""
    transcript_path = input_data.get("transcript_path")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    archive_path = f".claude/compaction_archive_{ts}.jsonl"
    if transcript_path:
        shutil.copy(transcript_path, archive_path)
    return {
        "systemMessage": (
            "CONTEXT COMPACTION TRIGGERED. "
            "Re-read the current Linear issue state before proceeding. "
            "Do not assume previously-read data is still accurate."
        )
    }
```

**PreToolUse hook — block unfiltered list_issues** (`01-AI-SPEC.md` §4b.4, lines 850-870):

```python
async def enforce_list_filters(input_data: dict, tool_use_id: str | None, context) -> dict:
    """Block un-filtered list_issues calls that would overflow context."""
    if input_data.get("tool_name") != "mcp__linear__list_issues":
        return {}
    tool_input = input_data.get("tool_input", {})
    if not tool_input.get("teamId") and not tool_input.get("projectId"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "list_issues requires teamId or projectId filter to prevent "
                    "context overflow. Add a filter and retry."
                ),
            }
        }
    return {}
```

**LINEAR_HOOKS dict — wire all hooks together** (`01-AI-SPEC.md` §4, lines 499-506):

```python
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
```

---

### `src/hsb/contracts/linear.py` (model, CRUD)

**Source:** `01-AI-SPEC.md` §4b.1 (lines 572-638); must mirror `agents/AGENT-CONTRACTS.md` §2 exactly

**Imports pattern:**

```python
from __future__ import annotations
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, model_validator
```

**Full contract models** (copy verbatim — every field mirrors `agents/AGENT-CONTRACTS.md` §2):

```python
class LinearOperation(str, Enum):
    create = "create"
    update = "update"
    read = "read"
    link = "link"
    comment = "comment"
    create_subtasks = "create_subtasks"


class LinearInput(BaseModel):
    """Input contract for the Linear System of Record Agent.
    Mirrors AGENT-CONTRACTS.md §2 Input exactly.
    """
    operation: LinearOperation
    payload: dict  # Operation-specific; validated by operation-specific models

    model_config = {"extra": "forbid"}


class LinearEntity(BaseModel):
    """A Linear entity returned after a create/update operation."""
    id: str = Field(..., pattern=r"^LIN-\d+$")
    type: Literal["epic", "user_story", "task", "subtask"]
    url: str = Field(..., pattern=r"^https://linear\.app/")


class LinearOutput(BaseModel):
    """Output contract for the Linear System of Record Agent.
    Mirrors AGENT-CONTRACTS.md §2 Output exactly.
    """
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

**Critical rules:**
- `extra="forbid"` is MANDATORY on every model — absent on even one model causes silent schema drift (Pitfall 7)
- `id` pattern `^LIN-\d+$` prevents UUID injection and catches format drift
- `url` pattern `^https://linear\.app/` catches wrong-domain responses
- Do NOT add fields not in `agents/AGENT-CONTRACTS.md` — downstream agents depend on exact mirror

---

### `src/hsb/contracts/base.py` (model, CRUD)

**Source:** `01-AI-SPEC.md` §4b.1 (lines 625-637); `agents/AGENT-CONTRACTS.md` §Standard Runtime Envelope and §Error Contract

**Full base contract models:**

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from hsb.contracts.linear import LinearOutput


class RuntimeEnvelope(BaseModel):
    """Standard envelope wrapping every agent invocation result.
    Mirrors AGENT-CONTRACTS.md §Standard Runtime Envelope exactly.
    """
    execution_id: str  # UUID
    requested_by: Literal["global_orchestrator", "work_item_orchestrator", "human"]
    skill: str
    agent: str
    input: dict
    output: LinearOutput | None = None
    status: Literal["success", "failed", "blocked"]
    errors: list[str] = Field(default_factory=list)
    next_recommended_action: str | None = None

    model_config = {"extra": "forbid"}


class ErrorContract(BaseModel):
    """Error contract. Mirrors AGENT-CONTRACTS.md §Error Contract exactly."""
    status: Literal["failed"]
    error_type: Literal[
        "missing_input",
        "invalid_state",
        "tool_failure",
        "validation_failure",
        "blocked_dependency",
    ]
    message: str
    recoverable: bool
    required_action: str

    model_config = {"extra": "forbid"}
```

---

### `src/hsb/cli/main.py` (controller, request-response)

**Source:** `01-RESEARCH.md` §Code Examples typer CLI pattern; `01-AI-SPEC.md` §4b.2

**Imports pattern:**

```python
import asyncio
import typer
from rich.console import Console
from rich.pretty import pprint
from hsb.agents.linear_agent import run_validated_linear_agent
```

**typer app pattern** (`01-RESEARCH.md` §Code Examples, typer CLI block):

```python
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
    pprint(result.model_dump())


@app.command("update-issue")
def update_issue(
    issue_id: str = typer.Option(..., "--issue-id", help="Linear issue ID (e.g. LIN-123)"),
    status: str = typer.Option(None, "--status", help="New status value"),
):
    """Update a Linear issue status (LINR-02)."""
    result = asyncio.run(
        run_validated_linear_agent(
            operation="update",
            payload={"issueId": issue_id, "status": status},
        )
    )
    pprint(result.model_dump())


@app.command("add-comment")
def add_comment(
    issue_id: str = typer.Option(..., "--issue-id"),
    body: str = typer.Option(..., "--body", help="Comment body (structured markdown)"),
):
    """Add a structured comment to a Linear issue (LINR-03)."""
    result = asyncio.run(
        run_validated_linear_agent(
            operation="comment",
            payload={"issueId": issue_id, "body": body},
        )
    )
    pprint(result.model_dump())


@app.command("link-pr")
def link_pr(
    issue_id: str = typer.Option(..., "--issue-id"),
    pr_url: str = typer.Option(..., "--pr-url", help="GitHub PR URL"),
):
    """Link a GitHub PR URL to a Linear issue (LINR-04)."""
    result = asyncio.run(
        run_validated_linear_agent(
            operation="link",
            payload={"issueId": issue_id, "prUrl": pr_url},
        )
    )
    pprint(result.model_dump())


if __name__ == "__main__":
    app()
```

**Critical:** Every CLI command uses `asyncio.run()` at the top level — NEVER inside an `async def`. Typer callbacks are synchronous; nesting `asyncio.run()` inside a coroutine raises `RuntimeError: This event loop is already running` (`01-AI-SPEC.md` §4b.2, Pitfall 5).

---

### `src/hsb/observability.py` (utility, event-driven)

**Source:** `01-AI-SPEC.md` §7 Production Monitoring (lines 1089-1102)

**Core tracing init pattern:**

```python
import phoenix as px
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


def init_tracing(project_name: str = "hsb-linear-agent") -> None:
    """Initialize Arize Phoenix tracing. Run once before agent sessions."""
    px.launch_app()  # Starts local Phoenix UI at http://localhost:6006
    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
```

**Only import when `[eval]` extras are installed.** This file is optional for Phase 1 core functionality.

---

### `.claude/skills/linear-system-of-record/SKILL.md` (config)

**Source:** Frontmatter from `01-RESEARCH.md` §Pattern 4 (SKILL.md Frontmatter); body migrated from `skills/05-LINEAR-SYSTEM-OF-RECORD.md`

**Frontmatter block** (`01-RESEARCH.md` §Pattern 4, STACK.md §SKILL.md frontmatter fields):

```yaml
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

**Critical:** `disable-model-invocation: true` is required because Linear write operations are side-effecting — they must only be triggered by explicit operator CLI commands, never by Claude's auto-invocation during conversation (`01-RESEARCH.md` §Pattern 4, Pitfall 7 note).

**Body:** Append the full content of `skills/05-LINEAR-SYSTEM-OF-RECORD.md` (lines 1-169) verbatim after the frontmatter. Do not modify the body — D-07 keeps the source file as human reference; the `.claude/skills/` version is the auto-discovered copy.

---

### `tests/conftest.py` (test fixture)

**Source:** `01-AI-SPEC.md` §5 Reference Dataset; `01-RESEARCH.md` §Validation Architecture

**Pattern:**

```python
import pytest
from hsb.contracts.linear import LinearOutput, LinearEntity


@pytest.fixture
def valid_linear_output() -> dict:
    """Canonical valid LinearOutput payload for contract tests."""
    return {
        "operation": "create",
        "result": "success",
        "linear_entities": [
            {
                "id": "LIN-123",
                "type": "task",
                "url": "https://linear.app/hsb/issue/LIN-123",
            }
        ],
        "error": None,
    }


@pytest.fixture
def failed_linear_output() -> dict:
    """Canonical failed LinearOutput payload for contract tests."""
    return {
        "operation": "create",
        "result": "failed",
        "linear_entities": [],
        "error": "tool_failure: mcp__linear__create_issue returned 500",
    }
```

---

### `tests/test_contracts.py` (test, unit)

**Source:** `01-AI-SPEC.md` §5 Reference Dataset scenarios 9-10; §6 Guardrails pydantic enforcement

**Pattern (parametrized schema-drift detection):**

```python
import pytest
from pydantic import ValidationError
from hsb.contracts.linear import LinearOutput, LinearInput


def test_valid_output_passes(valid_linear_output):
    result = LinearOutput.model_validate(valid_linear_output)
    assert result.result == "success"
    assert result.linear_entities[0].id == "LIN-123"


@pytest.mark.parametrize("bad_payload,expected_field", [
    # Scenario 9: raw UUID instead of LIN-xxx
    ({"operation": "create", "result": "success",
      "linear_entities": [{"id": "abc123-uuid", "type": "task",
                            "url": "https://linear.app/x/LIN-1"}]}, "id"),
    # Scenario 10: extra undeclared field
    ({"operation": "create", "result": "success", "linear_entities": [],
      "unexpected_field": "should_fail"}, "unexpected_field"),
    # failed result without error message
    ({"operation": "create", "result": "failed", "linear_entities": []}, "error"),
])
def test_invalid_output_raises(bad_payload, expected_field):
    with pytest.raises(ValidationError):
        LinearOutput.model_validate(bad_payload)
```

---

### `tests/test_hooks.py` (test, event-driven)

**Source:** `01-AI-SPEC.md` §5 Eval Dimension "retry correctness" (scenarios 7-8)

**Pattern:**

```python
import asyncio
import pytest
from unittest.mock import AsyncMock
from hsb.agents.hooks import linear_retry_hook, _retry_counts, MAX_RETRIES


@pytest.mark.asyncio
async def test_retry_backoff_increments_count():
    """Scenario 7: single transient failure — assert 1 retry, correct delay."""
    _retry_counts.clear()
    tool_use_id = "test-tool-use-001"
    input_data = {"tool_name": "mcp__linear__create_issue"}

    result = await linear_retry_hook(input_data, tool_use_id, context=None)

    assert "systemMessage" in result
    assert "attempt 1/3" in result["systemMessage"]
    assert _retry_counts[tool_use_id] == 1


@pytest.mark.asyncio
async def test_retry_cap_at_max():
    """Scenario 8: 3 consecutive failures — assert cap, result=failed returned."""
    _retry_counts.clear()
    tool_use_id = "test-tool-use-002"
    input_data = {"tool_name": "mcp__linear__create_issue"}

    # Exhaust retries
    for _ in range(MAX_RETRIES):
        await linear_retry_hook(input_data, tool_use_id, context=None)

    # 4th call should return "do not retry" message
    result = await linear_retry_hook(input_data, tool_use_id, context=None)
    assert "Do not retry" in result["systemMessage"]
    assert tool_use_id not in _retry_counts  # Counter cleared after cap
```

---

### `tests/test_integration.py` (test, integration)

**Source:** `01-AI-SPEC.md` §5 Reference Dataset scenarios 1-6; `01-RESEARCH.md` §Validation Architecture

**Pattern:**

```python
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
async def test_mcp_connection():
    """FOUND-01: Verify Linear MCP connects and tool prefix is mcp__linear__."""
    from hsb.agents.linear_agent import run_linear_agent
    # Minimal prompt that triggers a read-only list_teams call
    result = await run_linear_agent(
        "List the Linear teams available. Return JSON: {operation: 'read', result: 'success', "
        "linear_entities: [], teams: [...]}"
    )
    assert result is not None


@pytest.mark.integration
@pytest.mark.linr("LINR-01")
async def test_create_hierarchy():
    """LINR-01: Create EPIC → User Story → Task with parentId linkage."""
    # Implementation uses run_validated_linear_agent with real Linear workspace
    ...
```

---

### `knowledge/` directory bootstrap

**Source:** `01-RESEARCH.md` §Pattern 5 + `STACK.md` §File-Based Knowledge Store

**Shell commands to run (Wave 0):**

```bash
mkdir -p knowledge/{architecture,qa,implementation,patterns,anti-patterns,risk,backlog}
touch knowledge/{architecture,qa,implementation,patterns,anti-patterns,risk,backlog}/.gitkeep
```

**Note on categories:** Create 7 dirs — the 5 from `REQUIREMENTS.md` (`architecture, qa, implementation, backlog, risk`) plus `patterns` and `anti-patterns` from `STACK.md`/AI-SPEC.md. This satisfies FOUND-04 while matching the richer STACK.md structure (`01-RESEARCH.md` §Assumptions Log A3 mitigation).

**Knowledge entry frontmatter schema** (for all future entries, from `STACK.md` §File-Based Knowledge Store):

```yaml
---
title: string
type: architecture | qa | implementation | pattern | anti_pattern | risk
context: string  # work item or EPIC slug
evidence:
  linear_issue: LIN-123
  pr: url
  files: []
  qa_finding: ""
insight: string
recommendation: string
applicability: string
date: YYYY-MM-DD
---
```

---

## Shared Patterns

### Pattern: `extra="forbid"` on all pydantic models

**Source:** `01-AI-SPEC.md` §4b.1 (line 599, line 622); `01-RESEARCH.md` §Anti-Patterns #5
**Apply to:** Every `BaseModel` subclass in `src/hsb/contracts/`

```python
model_config = {"extra": "forbid"}
```

Absent on any model → silent schema drift passes undetected. This is Critical Failure Mode 1 in AI-SPEC.md §1.

---

### Pattern: `asyncio.run()` at CLI boundary only

**Source:** `01-AI-SPEC.md` §4b.2; `01-RESEARCH.md` §Anti-Patterns #4
**Apply to:** All `src/hsb/cli/main.py` command handlers

```python
# CORRECT — Typer is synchronous; asyncio.run() is safe at this boundary
@app.command("create-issue")
def create_issue(...):
    result = asyncio.run(run_validated_linear_agent(...))

# WRONG — never nest asyncio.run() inside a coroutine
async def some_function():
    result = asyncio.run(run_validated_linear_agent(...))  # raises RuntimeError
```

---

### Pattern: MCP tool prefix verification at session init

**Source:** `01-AI-SPEC.md` §3 (lines 276-281); `01-AI-SPEC.md` §5 Eval Dimension "MCP tool prefix correctness"
**Apply to:** `run_linear_agent()` in `linear_agent.py`

```python
if isinstance(message, SystemMessage) and message.subtype == "init":
    mcp_servers = message.data.get("mcp_servers", [])
    failed = [s for s in mcp_servers if s.get("status") != "connected"]
    if failed:
        raise RuntimeError(f"Linear MCP server failed to connect: {failed}")
    # Optionally: verify prefix == "mcp__linear__" not "mcp__claude_ai_Linear__"
```

---

### Pattern: `allowed_tools=["mcp__linear__*"]` is required

**Source:** `01-AI-SPEC.md` §3 Common Pitfall #2; `01-RESEARCH.md` §Anti-Patterns #2
**Apply to:** Every `ClaudeAgentOptions` that uses Linear MCP

```python
ClaudeAgentOptions(
    allowed_tools=["mcp__linear__*"],   # REQUIRED — permission_mode does NOT cover MCP
    permission_mode="acceptEdits",       # Only covers filesystem tools
)
```

---

### Pattern: `load_dotenv()` at module level

**Source:** `01-AI-SPEC.md` §3 (line 239); `01-RESEARCH.md` §Security Domain
**Apply to:** `linear_agent.py` and any module that reads `ANTHROPIC_API_KEY`

```python
from dotenv import load_dotenv
load_dotenv()  # Loads .env before any os.environ access
```

`.env` must be gitignored. Never hardcode `ANTHROPIC_API_KEY`.

---

## No Analog Found

All files are greenfield. Patterns for each file are derived entirely from project specification documents rather than existing source code.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| All files listed above | various | various | Repository contains only markdown documentation. No Python source code, no pyproject.toml, no test infrastructure exists in the codebase as of 2026-05-05. |

---

## Metadata

**Analog search scope:** All files in `/home/ubuntu/hugo/task-management-agents/` (excluding `.git/`)
**Files scanned:** 34 repository files (all markdown, no Python source)
**Python source files found:** 0
**Pattern sources used:** `01-AI-SPEC.md`, `01-RESEARCH.md`, `STACK.md`, `agents/AGENT-CONTRACTS.md`, `skills/05-LINEAR-SYSTEM-OF-RECORD.md`
**Pattern extraction date:** 2026-05-05
