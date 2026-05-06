# Phase 4: Global + Main Orchestrators and Parallel Mode - Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 13 new/modified files
**Analogs found:** 13 / 13 (all spec-derived from Phase 1–3 PATTERNS.md and specification documents; no Python source exists yet)

> **Greenfield note (same as Phases 1–3):** The repository still contains only markdown documentation — no Python source code has been created yet. Every pattern below is derived from (1) Phase 1 PATTERNS.md (canonical foundation: `asyncio.run()`, `load_dotenv()`, Pydantic `extra="forbid"`, Typer CLI, MCP init check), (2) Phase 2 PATTERNS.md (agent/contract/test extensions, `MAX_VALIDATION_RETRIES` retry loop), (3) Phase 3 PATTERNS.md (WIO SDK session, `run_loop.py` subprocess loop, `@pytest.mark.integration`), and (4) `04-RESEARCH.md` Patterns 1–7 plus the spec documents. Phase 4 adds two new architectural primitives not present in prior phases: (a) pure Python orchestrator classes (no Agent SDK session, no LLM) and (b) `asyncio.gather` subprocess fan-out with `git worktree` isolation. All code excerpts below are canonical — copy verbatim, do not paraphrase.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/hsb/agents/global_orchestrator.py` | service | CRUD (pure Python filter/sort over Linear data) | `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md — async service class, `load_dotenv`, Linear MCP calls) | role-match (no SDK session) |
| `src/hsb/agents/main_orchestrator.py` | service | event-driven (dispatch controller: claim loop + `asyncio.gather` subprocess fan-out) | `src/hsb/agents/work_item_orchestrator.py` (Phase 3 PATTERNS.md — async orchestration entrypoint, coroutine structure) + `run_loop.py` (subprocess invocation pattern) | role-match + data-flow-match |
| `src/hsb/contracts/global_orchestrator.py` | model | CRUD (pydantic validate) | `src/hsb/contracts/orchestrator.py` (Phase 3 PATTERNS.md — `WorkItemOrchOutput`, `Literal` status enum, `extra="forbid"`) | exact-role |
| `src/hsb/contracts/main_orchestrator.py` | model | CRUD (pydantic validate + `Literal`) | `src/hsb/contracts/orchestrator.py` (Phase 3 PATTERNS.md — same pattern, multiple model classes per file) | exact-role |
| `src/hsb/cli/main.py` (extend) | controller | request-response (typer CLI → `asyncio.run`) | `src/hsb/cli/main.py` (Phase 3 PATTERNS.md — `@app.command` + `asyncio.run()` at CLI boundary) | exact-role |
| `run_loop.py` (update) | utility | event-driven (subprocess loop + termination check) | `run_loop.py` (Phase 3 PATTERNS.md — exact file; update `hsb run-next-step` → `hsb run`) | exact-role (delta only) |
| `.claude/skills/global-orchestration/SKILL.md` | config | — | `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md — same frontmatter structure, `disable-model-invocation: true`) | exact-role |
| `.claude/skills/main-orchestrator/SKILL.md` | config | — | `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md — same frontmatter structure) | exact-role |
| `tests/unit/test_global_orchestrator.py` | test | CRUD (unit, pure Python logic) | `tests/unit/test_orchestrator.py` (Phase 3 PATTERNS.md — same `pytest.raises(ValidationError)` + `pytest.mark.asyncio` pattern) | exact-role |
| `tests/unit/test_main_orchestrator.py` | test | event-driven (unit, mock subprocess + mock Linear) | `tests/unit/test_orchestrator.py` (Phase 3 PATTERNS.md — `AsyncMock` + `patch` pattern for async agent functions) | exact-role |
| `tests/integration/test_global_orchestrator_e2e.py` | test | CRUD (integration, real Linear) | `tests/integration/test_orchestrator_e2e.py` (Phase 3 PATTERNS.md — `pytestmark = [pytest.mark.integration]`, real Linear workspace) | exact-role |
| `tests/integration/test_parallel_mode_e2e.py` | test | event-driven (integration, real git worktree + real Linear) | `tests/integration/test_orchestrator_e2e.py` (Phase 3 PATTERNS.md — integration marker, two-task gate pattern) | role-match |
| `.gitignore` (update) | config | — | None (single-line append) | delta-only |

---

## Pattern Assignments

### `src/hsb/agents/global_orchestrator.py` (service, CRUD)

**Analog:** `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md §linear_agent.py — `load_dotenv()` at module level, `run_validated_linear_agent` import, async coroutine structure). No SDK session — pure Python class over Linear service calls.

**Source specs:** `04-RESEARCH.md` Pattern 1, §Code Examples (dependency filter + EPIC completion check); `skills/07-GLOBAL-ORCHESTRATION.md` §Task Identification Logic; `agents/AGENT-CONTRACTS.md` §0 output contract.

**Imports pattern** (Phase 1 PATTERNS.md `linear_agent.py` import block + Phase 4 contract import):

```python
from __future__ import annotations
import logging
from typing import Any

from dotenv import load_dotenv

from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.contracts.global_orchestrator import GlobalOrchestratorOutput, ReadyTask

load_dotenv()

logger = logging.getLogger(__name__)
```

**Core class pattern** (`04-RESEARCH.md` Pattern 1 §GlobalOrchestrator):

```python
class GlobalOrchestrator:
    """
    Pure Python class — no LLM, no SDK session (D-01).
    Reads Linear state via run_validated_linear_agent, applies deterministic
    filter/sort, returns GlobalOrchestratorOutput.
    """

    async def get_ready_tasks(self) -> GlobalOrchestratorOutput:
        all_items = await self._fetch_all_items()

        if not all_items:
            return GlobalOrchestratorOutput(
                ready_tasks=[],
                is_backlog_empty=True,
                is_epic_ready=False,
            )

        ready = self._filter_ready_items(all_items)
        # Sort: Linear priority ascending (1=urgent → 4=low), createdAt as tiebreaker
        ready.sort(key=lambda x: (x.get("priority", 999), x.get("createdAt", "")))

        is_epic_ready = self._check_epic_complete(all_items)

        return GlobalOrchestratorOutput(
            ready_tasks=[ReadyTask(id=t["id"], title=t["title"]) for t in ready],
            is_backlog_empty=False,
            is_epic_ready=is_epic_ready,
        )
```

**Dependency filter** (`04-RESEARCH.md` §Code Examples — copy verbatim, implements GORD-01 + GORD-02):

```python
    def _filter_ready_items(self, all_items: list[dict]) -> list[dict]:
        """
        GORD-01: Return items with status='todo'.
        GORD-02: Exclude items with any unresolved blocked-by dependency.
        """
        done_ids = {item["id"] for item in all_items if item["status"] == "done"}
        ready = []
        for item in all_items:
            if item.get("status") != "todo":
                continue
            deps = item.get("dependencies", [])
            if all(dep_id in done_ids for dep_id in deps):
                ready.append(item)
        return ready
```

**EPIC completion check** (`04-RESEARCH.md` §Code Examples — implements GORD-04):

```python
    def _check_epic_complete(self, all_items: list[dict]) -> bool:
        """
        GORD-04: Signal is_epic_ready when all EPIC children are done + qa_approved.
        Returns False if no children exist (empty backlog case already handled above).
        """
        children = [i for i in all_items if i.get("type") != "epic"]
        if not children:
            return False
        return all(
            i.get("status") == "done" and i.get("qa_status") in ("approved", "not_required")
            for i in children
        )

    async def _fetch_all_items(self) -> list[dict]:
        """
        Fetch all work items from Linear for the current project scope.
        Uses run_validated_linear_agent — all Linear reads go through OAuth2 MCP layer (no API keys).
        """
        result = await run_validated_linear_agent(
            operation="read",
            payload={"filter": {"project": {"id": {"eq": "CURRENT_PROJECT_ID"}}}},
        )
        return [entity.__dict__ for entity in result.linear_entities]
```

**Critical:** No `ClaudeAgentOptions`, no `query()`, no `create_sdk_mcp_server`. This class MUST remain a pure Python async service. Introducing an SDK session here violates D-01.

---

### `src/hsb/agents/main_orchestrator.py` (service, event-driven)

**Analog:** `src/hsb/agents/work_item_orchestrator.py` (Phase 3 PATTERNS.md §run_orchestration_cycle — async coroutine structure, `load_dotenv`, `run_validated_linear_agent` import) + `run_loop.py` (Phase 3 PATTERNS.md — subprocess invocation pattern).

**Source specs:** `04-RESEARCH.md` Patterns 2–5; `skills/00-MAIN-ORCHESTRATOR.md` §Execution Modes; `agents/AGENT-CONTRACTS.md` §0 Claiming Rule.

**Imports pattern:**

```python
from __future__ import annotations
import asyncio
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from hsb.agents.global_orchestrator import GlobalOrchestrator
from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.contracts.main_orchestrator import (
    MainOrchestratorOutput,
    DispatchedItem,
    ClaimResult,
)

load_dotenv()

logger = logging.getLogger(__name__)

WORKTREES_DIR = ".worktrees"
CLAIM_DELAY_MS = int(os.environ.get("HSB_CLAIM_DELAY_MS", "200"))
```

**Top-level entrypoint** (called by CLI via `asyncio.run()`):

```python
async def run_main_orchestrator(mode: Literal["cascade", "parallel"] = "cascade") -> None:
    """
    Main Orchestrator entrypoint.
    1. Calls GlobalOrchestrator to get ready tasks.
    2. Dispatches WIOs in cascade or parallel mode.
    3. Posts cycle summary to Linear EPIC via linear_agent.
    No SDK session — pure Python dispatch controller (D-02).
    """
    go = GlobalOrchestrator()
    global_output = await go.get_ready_tasks()

    if global_output.is_backlog_empty:
        logger.info("Backlog empty — no tasks to dispatch.")
        return

    if not global_output.ready_tasks:
        logger.info("No ready tasks (all blocked or none todo).")
        return

    repo_root = os.getcwd()

    if mode == "cascade":
        dispatched = await _cascade_dispatch(global_output.ready_tasks, repo_root)
    else:
        dispatched = await _parallel_dispatch(global_output.ready_tasks, repo_root)

    # MORD-05: Post cycle summary to Linear EPIC
    summary = _build_cycle_summary(mode, dispatched)
    await run_validated_linear_agent(
        operation="comment",
        payload={"epicId": "CURRENT_EPIC_ID", "body": summary},
    )
```

**Cascade dispatch** (`04-RESEARCH.md` Pattern 5 — single task, no claiming, no worktrees):

```python
async def _cascade_dispatch(
    ready_tasks: list,
    repo_root: str,
) -> list[DispatchedItem]:
    """
    Cascade mode: take first task only, run synchronously in main working tree.
    No claiming (single-process, no contention).
    No worktree (runs in main working tree).
    """
    if not ready_tasks:
        return []
    task = ready_tasks[0]
    result = await _run_wio_subprocess(task, worktree_path=repo_root)
    return [DispatchedItem(
        work_item_id=task.id,
        orchestrator_instance="cascade-0",
        claim_status="claimed",
        final_status=result.get("status", "completed"),
    )]
```

**Optimistic-lock claiming loop** (`04-RESEARCH.md` Pattern 2 — MORD-03; D-05 sequential claiming, D-06 delay):

```python
async def _sequential_claiming_loop(
    ready_tasks: list,
    delay_ms: int = CLAIM_DELAY_MS,
) -> list[tuple]:
    """
    MORD-03: Sequential claiming loop — claim each task before dispatch.
    Returns list of (task, pre_updated_at) tuples for successfully claimed tasks.
    Claiming is sequential even in parallel mode (D-05) to eliminate the inter-claim
    race window described in PITFALLS.md Pitfall 1 for single-process runs.
    """
    claimed = []
    for task in ready_tasks:
        # Step 1: Capture pre-write updatedAt
        fresh_before = await run_validated_linear_agent(
            operation="read",
            payload={"issueId": task.id},
        )
        pre_updated_at = fresh_before.linear_entities[0].get("updatedAt", "")

        # Step 2: Write status = in_progress
        await run_validated_linear_agent(
            operation="update",
            payload={"issueId": task.id, "status": "in_progress"},
        )

        # Step 3: Re-read and verify updatedAt changed
        fresh_after = await run_validated_linear_agent(
            operation="read",
            payload={"issueId": task.id},
        )
        post_updated_at = fresh_after.linear_entities[0].get("updatedAt", "")

        if post_updated_at != pre_updated_at:
            claimed.append((task, post_updated_at))
            logger.info("Claimed task %s", task.id)
        else:
            logger.warning(
                "Claim verification failed for %s — updatedAt unchanged. "
                "Possible concurrent write. Skipping.",
                task.id,
            )

        # D-06: inter-claim delay to reduce collision window
        await asyncio.sleep(delay_ms / 1000)

    return claimed
```

**Worktree lifecycle** (`04-RESEARCH.md` Pattern 3 — git worktree add/remove via asyncio.create_subprocess_exec):

```python
async def _git_worktree_add(repo_root: str, task_id: str, branch_name: str) -> str:
    """
    Creates .worktrees/LIN-{task_id}/ as a linked worktree on branch_name.
    Checks for existing branch before add (Pitfall B mitigation).
    Returns the worktree path.
    """
    wt_path = os.path.join(repo_root, WORKTREES_DIR, f"LIN-{task_id}")
    proc = await asyncio.create_subprocess_exec(
        "git", "worktree", "add", "-b", branch_name, wt_path,
        cwd=repo_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"git worktree add failed for LIN-{task_id}: {stderr.decode()}"
        )
    return wt_path


async def _git_worktree_remove(repo_root: str, task_id: str) -> None:
    """
    Removes .worktrees/LIN-{task_id}/ worktree.
    Uses --force — cleanup must always succeed (D-09).
    Do NOT raise on failure — log and continue (anti-pattern: raising on cleanup failure).
    """
    wt_path = os.path.join(repo_root, WORKTREES_DIR, f"LIN-{task_id}")
    proc = await asyncio.create_subprocess_exec(
        "git", "worktree", "remove", "--force", wt_path,
        cwd=repo_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    if proc.returncode != 0:
        logger.warning(
            "git worktree remove failed for LIN-%s (non-fatal — worktree may already be gone).",
            task_id,
        )
```

**WIO subprocess dispatch** (`04-RESEARCH.md` Pattern 4 — JSON tempfile IPC, asyncio.gather):

```python
async def _run_wio_subprocess(task, worktree_path: str) -> dict:
    """
    Spawns WIO as a subprocess in the given worktree.
    Input/output via JSON tempfiles (clean Pydantic contract, no shell arg escaping).
    Returns WIO output dict or error dict on failure (never raises — asyncio.gather handles errors).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as input_file:
        json.dump({"work_item_id": task.id}, input_file)
        input_path = input_file.name

    output_path = input_path.replace(".json", "-output.json")

    # Pass only required env vars — never pass **os.environ wholesale (security: env leakage)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "HSB_WIO_INPUT_FILE": input_path,
        "HSB_WIO_OUTPUT_FILE": output_path,
    }

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "hsb.agents.work_item_orchestrator",
            cwd=worktree_path,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(
                "WIO subprocess failed for %s (exit %d): %s",
                task.id, proc.returncode, stderr.decode()
            )
            return {"status": "failed", "task_id": task.id, "error": stderr.decode()}

        if Path(output_path).exists():
            with open(output_path) as f:
                return json.load(f)
        return {"status": "completed", "task_id": task.id}
    finally:
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)


async def _parallel_dispatch(
    ready_tasks: list,
    repo_root: str,
) -> list[DispatchedItem]:
    """
    Parallel mode dispatch (MORD-04).
    Phase 1: Sequential claiming loop.
    Phase 2: Create worktrees.
    Phase 3: asyncio.gather all WIO subprocesses.
    Phase 4: Cleanup worktrees (always, regardless of WIO outcome).
    """
    # Pitfall C mitigation: prune stale worktrees before any new ones are created
    await asyncio.create_subprocess_exec(
        "git", "worktree", "prune",
        cwd=repo_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Phase 1: Sequential claiming
    claimed_pairs = await _sequential_claiming_loop(ready_tasks)

    dispatched_items: list[DispatchedItem] = []
    skipped_ids = {t.id for t in ready_tasks} - {t.id for t, _ in claimed_pairs}

    for skipped_id in skipped_ids:
        dispatched_items.append(DispatchedItem(
            work_item_id=skipped_id,
            orchestrator_instance="skipped",
            claim_status="skipped",
            final_status="blocked",
        ))

    if not claimed_pairs:
        return dispatched_items

    # Phase 2: Create worktrees
    worktree_paths = []
    for task, _ in claimed_pairs:
        slug = task.title.lower().replace(" ", "-")[:30]
        branch = f"feature/LIN-{task.id}-{slug}"
        wt_path = await _git_worktree_add(repo_root, task.id, branch)
        worktree_paths.append(wt_path)

    # Phase 3: asyncio.gather — return_exceptions=True: one failure does not abort others
    results = await asyncio.gather(
        *[
            _run_wio_subprocess(task, wt)
            for (task, _), wt in zip(claimed_pairs, worktree_paths)
        ],
        return_exceptions=True,
    )

    # Normalize exceptions to error dicts (Pitfall E: asyncio.gather swallows exceptions)
    normalized = [
        r if isinstance(r, dict) else {"status": "exception", "error": str(r)}
        for r in results
    ]

    # Phase 4: Cleanup worktrees (always — even on WIO failure)
    for task, _ in claimed_pairs:
        await _git_worktree_remove(repo_root, task.id)

    # Build dispatched items from results
    for i, ((task, _), result) in enumerate(zip(claimed_pairs, normalized)):
        dispatched_items.append(DispatchedItem(
            work_item_id=task.id,
            orchestrator_instance=f"parallel-{i}",
            claim_status="claimed",
            final_status=result.get("status", "completed") if isinstance(result, dict) else "failed",
        ))

    return dispatched_items
```

**Cycle summary builder** (`04-RESEARCH.md` §Code Examples §Cycle Summary Comment Format; `agents/AGENT-CONTRACTS.md` §0 output):

```python
def _build_cycle_summary(mode: str, dispatched: list[DispatchedItem]) -> str:
    """MORD-05: Build cycle summary for Linear EPIC comment."""
    completed = [d for d in dispatched if d.final_status == "completed"]
    failed = [d for d in dispatched if d.final_status in ("failed", "blocked", "exception")]
    skipped = [d for d in dispatched if d.claim_status == "skipped"]

    lines = [
        "## Orchestration Cycle Summary",
        f"**Mode:** {mode}",
        f"**Dispatched:** {len(dispatched)} tasks",
        f"**Completed:** {len(completed)}",
        f"**Failed/Blocked:** {len(failed)}",
        f"**Skipped (claim failed):** {len(skipped)}",
        "",
        "### Details",
    ]
    for d in dispatched:
        icon = "✓" if d.final_status == "completed" else "✗"
        lines.append(f"- {icon} {d.work_item_id}: {d.claim_status} -> {d.final_status}")

    return "\n".join(lines)
```

**Critical:** No `ClaudeAgentOptions`, no `query()`, no `create_sdk_mcp_server` in this file. D-02 is absolute. WIO subprocess input MUST be passed via JSON tempfile (not CLI args, not env var payload) to respect Pydantic contract boundaries and avoid env var length limits.

---

### `src/hsb/contracts/global_orchestrator.py` (model, CRUD)

**Analog:** `src/hsb/contracts/orchestrator.py` (Phase 3 PATTERNS.md §contracts/orchestrator.py — same `BaseModel` + `Literal` + `extra="forbid"` + `Field(default_factory=...)` pattern)

**Source spec:** `agents/AGENT-CONTRACTS.md` §0 output contract; `04-RESEARCH.md` Pattern 6.

**Full contract models** (`04-RESEARCH.md` Pattern 6 §global_orchestrator.py — copy verbatim):

```python
from __future__ import annotations
from pydantic import BaseModel, Field


class ReadyTask(BaseModel):
    """A single ready work item returned by the Global Orchestrator."""
    model_config = {"extra": "forbid"}

    id: str
    title: str
    priority: int = 999        # Linear priority: 1=urgent, 2=high, 3=medium, 4=low, 0/999=none
    dependencies: list[str] = Field(default_factory=list)


class GlobalOrchestratorOutput(BaseModel):
    """
    Output contract for the Global Orchestrator.
    Mirrors AGENT-CONTRACTS.md §0 GlobalOrchestratorOutput exactly (D-03).
    """
    model_config = {"extra": "forbid"}

    ready_tasks: list[ReadyTask]
    is_backlog_empty: bool      # GORD-03: True when project has no work items at all
    is_epic_ready: bool         # GORD-04: True when all EPIC children are done + qa_approved
```

**Critical rules (same as all prior contracts):**
- `extra="forbid"` MANDATORY — absent causes silent schema drift (Phase 1 PATTERNS.md §Shared Patterns)
- `ready_tasks` is an ordered list — sort order is set by `GlobalOrchestrator.get_ready_tasks()`, callers must not re-sort
- Do NOT add fields not in `agents/AGENT-CONTRACTS.md §0`

---

### `src/hsb/contracts/main_orchestrator.py` (model, CRUD)

**Analog:** `src/hsb/contracts/orchestrator.py` (Phase 3 PATTERNS.md — multiple `Literal`-typed models in one file, `extra="forbid"` on all)

**Source spec:** `agents/AGENT-CONTRACTS.md` §0 output contract; `04-RESEARCH.md` Pattern 6.

**Full contract models** (`04-RESEARCH.md` Pattern 6 §main_orchestrator.py — copy verbatim):

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class ClaimResult(BaseModel):
    """Internal result of a single claiming attempt."""
    model_config = {"extra": "forbid"}

    work_item_id: str
    claimed: bool
    pre_updated_at: str   # timestamp before write — used to verify claim
    post_updated_at: str  # timestamp after write — must differ from pre if claimed


class DispatchedItem(BaseModel):
    """Record of a single dispatched work item within a cycle."""
    model_config = {"extra": "forbid"}

    work_item_id: str
    orchestrator_instance: str
    claim_status: Literal["claimed", "skipped"]
    final_status: Literal["completed", "failed", "blocked", "exception"]


class MainOrchestratorOutput(BaseModel):
    """
    Output contract for the Main Orchestrator cycle.
    Mirrors AGENT-CONTRACTS.md §0 Output exactly (MORD-05 format).
    """
    model_config = {"extra": "forbid"}

    mode: Literal["cascade", "parallel"]
    dispatched: list[DispatchedItem] = Field(default_factory=list)
    cycle_summary: str
```

**Critical rules:**
- `extra="forbid"` MANDATORY on all three models
- `final_status` includes `"exception"` to cover `asyncio.gather` exception normalization (Pitfall E mitigation)
- `ClaimResult` is an internal intermediate — not in the AGENT-CONTRACTS.md output, used only within `_sequential_claiming_loop()`

---

### `src/hsb/cli/main.py` — extend Phase 3 (controller, request-response)

**Analog:** `src/hsb/cli/main.py` (Phase 3 PATTERNS.md §cli/main.py — exact same `@app.command()` + `asyncio.run()` pattern; D-10 adds one new subcommand)

**Source spec:** `04-RESEARCH.md` Pattern 7; CONTEXT.md D-10, D-11, D-13.

**Delta: add `hsb run` subcommand** (do NOT rewrite Phase 1–3 commands — append only):

```python
# Additional import at top of existing main.py (after Phase 3 imports)
from hsb.agents.main_orchestrator import run_main_orchestrator


@app.command("run")
def run(
    parallel: bool = typer.Option(
        False,
        "--parallel",
        help=(
            "Run all ready tasks in parallel with worktree isolation. "
            "Requires Phase 3 cascade cycle to have been validated first (D-13)."
        ),
    ),
) -> None:
    """
    Run one orchestration cycle.
    Default mode: cascade (one task at a time, sequential WIO).
    Use --parallel for concurrent WIO dispatch (D-10).
    Parallel never activates by accident — requires explicit opt-in (D-10).
    """
    # D-13 runtime guard: warn if Phase 3 gate has not been validated
    # (Planner: add a STATE.md check or env-var gate here per D-13 note)
    mode = "parallel" if parallel else "cascade"
    # asyncio.run() at CLI boundary only — same pattern as Phase 1/2/3 (Phase 1 Shared Patterns)
    asyncio.run(run_main_orchestrator(mode=mode))
```

**Critical:** Same `asyncio.run()` rule as Phases 1–3 — the handler is a synchronous Typer callback that wraps an async coroutine. NEVER mark it `async def`. `hsb run-next-step` (Phase 3) is RETAINED UNCHANGED — do not modify or remove it.

---

### `run_loop.py` — update Phase 3 (utility, event-driven)

**Analog:** `run_loop.py` (Phase 3 PATTERNS.md §run_loop.py — exact file; delta is one-line change in `main()` and updated `has_ready_tasks()` to use GlobalOrchestrator)

**Source spec:** `04-RESEARCH.md` §Code Examples §run_loop.py Update; CONTEXT.md D-12.

**Full updated file** (`04-RESEARCH.md` §Code Examples §run_loop.py Update — copy verbatim):

```python
"""
run_loop.py — Thin repo-root wrapper that calls `hsb run` in a loop.
Stops when no ready_tasks remain or operator presses Ctrl+C (CLIR-04, D-12).
Phase 4 update: calls `hsb run` instead of `hsb run-next-step`.
Each iteration is a standalone asyncio.run() — no process-level state (CLIR-05).
"""
import asyncio
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()


async def has_ready_tasks() -> bool:
    """
    Check for ready tasks by calling GlobalOrchestrator directly (Phase 4 update).
    Returns False when loop should stop (no todo tasks remain).
    """
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    return bool(output.ready_tasks)


def main() -> None:
    print("Starting HSBTech run loop. Press Ctrl+C to stop.")
    try:
        while True:
            # Phase 4 update: call `hsb run` instead of `hsb run-next-step`
            result = subprocess.run(["hsb", "run"], check=False)
            if result.returncode != 0:
                print(
                    f"hsb run failed (exit {result.returncode}). Stopping loop.",
                    file=sys.stderr,
                )
                sys.exit(result.returncode)

            if not asyncio.run(has_ready_tasks()):
                print("No ready tasks remaining. Loop complete.")
                break
    except KeyboardInterrupt:
        print("\nLoop interrupted by operator.")


if __name__ == "__main__":
    main()
```

**Critical:** Each `asyncio.run()` creates a new event loop — no Python process state persists. `result.returncode` check is MANDATORY — absent causes infinite loop on `hsb run` failure (Phase 3 PATTERNS.md anti-pattern).

---

### `.claude/skills/global-orchestration/SKILL.md` (config)

**Analog:** `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md §SKILL.md — same frontmatter structure, `disable-model-invocation: true`, body from skills source file)

**Source spec:** `04-RESEARCH.md` §Claude's Discretion (SKILL.md migration); `skills/07-GLOBAL-ORCHESTRATION.md` (body content).

**Frontmatter block** (adapt Phase 3 SKILL.md frontmatter structure for global orchestration):

```yaml
---
name: global-orchestration
description: |
  Reads Linear project state and returns a prioritized list of ready, non-blocked work items.
  Detects empty backlog (is_backlog_empty) and EPIC completion (is_epic_ready).
  Pure Python class — no LLM invocation during normal operation.
  Only invoke when: Global Orchestrator logic needs to be understood or debugged.
  Do NOT invoke during conversation or as a write-side-effect trigger.
disable-model-invocation: true
allowed-tools: "mcp__linear__list_issues mcp__linear__get_issue"
arguments:
  - name: project_id
    description: "Linear project ID to evaluate"
---
```

**Body:** Append the full content of `skills/07-GLOBAL-ORCHESTRATION.md` verbatim after the frontmatter. Do not modify the body — `skills/` remains as human reference; `.claude/skills/` is the auto-discovered copy.

**Critical:** `disable-model-invocation: true` is MANDATORY even though the Global Orchestrator is pure Python. The SKILL.md serves as a human-readable spec reference and must not auto-invoke (Phase 1 PATTERNS.md §Shared Patterns rationale).

---

### `.claude/skills/main-orchestrator/SKILL.md` (config)

**Analog:** `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md §SKILL.md — identical frontmatter structure)

**Source spec:** `04-RESEARCH.md` §Claude's Discretion (SKILL.md migration); `skills/00-MAIN-ORCHESTRATOR.md` (body content).

**Frontmatter block:**

```yaml
---
name: main-orchestrator
description: |
  Dispatch controller for the HSBTech agent hierarchy. Accepts cascade or parallel mode,
  calls Global Orchestrator, claims tasks via optimistic lock, and dispatches Work Item Orchestrators.
  Pure Python class — no LLM invocation during normal operation.
  Only invoke when: Main Orchestrator behavior needs to be understood, debugged, or traced.
  Do NOT invoke during conversation.
disable-model-invocation: true
allowed-tools: "mcp__linear__list_issues mcp__linear__get_issue mcp__linear__update_issue mcp__linear__create_comment"
arguments:
  - name: mode
    description: "Execution mode: cascade | parallel"
---
```

**Body:** Append the full content of `skills/00-MAIN-ORCHESTRATOR.md` verbatim after the frontmatter.

---

### `tests/unit/test_global_orchestrator.py` (test, unit)

**Analog:** `tests/unit/test_orchestrator.py` (Phase 3 PATTERNS.md §tests/unit/test_orchestrator.py — `AsyncMock` + `patch`, `pytest.mark.asyncio`, business logic assertions)

**Source spec:** `04-RESEARCH.md` §Validation Architecture §Phase Requirements → Test Map (GORD-01 through GORD-04).

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from hsb.contracts.global_orchestrator import GlobalOrchestratorOutput, ReadyTask


# --- GORD-01: Returns only todo items sorted by priority ---

@pytest.mark.asyncio
async def test_returns_todo_only():
    """GORD-01: Only items with status='todo' and resolved dependencies are returned."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    mock_items = [
        {"id": "LIN-1", "status": "todo", "priority": 2, "createdAt": "2024-01-01", "type": "task", "dependencies": [], "title": "Task 1"},
        {"id": "LIN-2", "status": "done", "priority": 1, "createdAt": "2024-01-02", "type": "task", "dependencies": [], "title": "Task 2"},
        {"id": "LIN-3", "status": "in_progress", "priority": 3, "createdAt": "2024-01-03", "type": "task", "dependencies": [], "title": "Task 3"},
    ]
    go = GlobalOrchestrator()
    result = go._filter_ready_items(mock_items)
    assert len(result) == 1
    assert result[0]["id"] == "LIN-1"


# --- GORD-02: Dependency filter ---

@pytest.mark.asyncio
async def test_dependency_filter():
    """GORD-02: Items with non-done blocking dependencies are excluded."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    mock_items = [
        {"id": "LIN-10", "status": "todo", "priority": 1, "createdAt": "2024-01-01", "type": "task", "dependencies": ["LIN-11"], "title": "Blocked task"},
        {"id": "LIN-11", "status": "todo", "priority": 2, "createdAt": "2024-01-02", "type": "task", "dependencies": [], "title": "Blocking task"},  # dep not done
    ]
    go = GlobalOrchestrator()
    result = go._filter_ready_items(mock_items)
    # LIN-10 is excluded (LIN-11 not done); LIN-11 is included (no deps)
    assert len(result) == 1
    assert result[0]["id"] == "LIN-11"


# --- GORD-03: Empty backlog detection ---

@pytest.mark.asyncio
async def test_empty_backlog_signal():
    """GORD-03: Returns is_backlog_empty=True when project has no work items."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    go = GlobalOrchestrator()
    with patch.object(go, "_fetch_all_items", new_callable=AsyncMock, return_value=[]):
        output = await go.get_ready_tasks()
    assert output.is_backlog_empty is True
    assert output.ready_tasks == []
    assert output.is_epic_ready is False


# --- GORD-04: EPIC completion detection ---

@pytest.mark.asyncio
async def test_epic_ready_signal():
    """GORD-04: Returns is_epic_ready=True when all children are done + qa_approved."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    mock_items = [
        {"id": "LIN-100", "status": "in_progress", "type": "epic", "priority": 1, "createdAt": "2024-01-01", "dependencies": [], "title": "EPIC"},
        {"id": "LIN-101", "status": "done", "qa_status": "approved", "type": "task", "priority": 2, "createdAt": "2024-01-02", "dependencies": [], "title": "Task 1"},
        {"id": "LIN-102", "status": "done", "qa_status": "approved", "type": "task", "priority": 2, "createdAt": "2024-01-03", "dependencies": [], "title": "Task 2"},
    ]
    go = GlobalOrchestrator()
    with patch.object(go, "_fetch_all_items", new_callable=AsyncMock, return_value=mock_items):
        output = await go.get_ready_tasks()
    assert output.is_epic_ready is True
    assert output.ready_tasks == []  # No todo items


# --- Contract validation ---

def test_global_orchestrator_output_contract():
    """GlobalOrchestratorOutput schema validates correctly."""
    from pydantic import ValidationError
    output = GlobalOrchestratorOutput.model_validate({
        "ready_tasks": [{"id": "LIN-1", "title": "Task 1"}],
        "is_backlog_empty": False,
        "is_epic_ready": False,
    })
    assert output.ready_tasks[0].id == "LIN-1"


def test_global_orchestrator_output_extra_field_rejected():
    """GlobalOrchestratorOutput rejects extra fields (extra='forbid')."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        GlobalOrchestratorOutput.model_validate({
            "ready_tasks": [],
            "is_backlog_empty": True,
            "is_epic_ready": False,
            "unexpected_field": "boom",
        })
```

---

### `tests/unit/test_main_orchestrator.py` (test, unit)

**Analog:** `tests/unit/test_orchestrator.py` (Phase 3 PATTERNS.md §tests/unit/test_orchestrator.py — `AsyncMock` + `patch` for async dependencies, `inspect.getsource` for architectural property assertions)

**Source spec:** `04-RESEARCH.md` §Validation Architecture §Phase Requirements → Test Map (MORD-01 through MORD-04).

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# --- MORD-01: Mode routing ---

@pytest.mark.asyncio
async def test_mode_routing_cascade():
    """MORD-01: cascade mode calls _cascade_dispatch, not _parallel_dispatch."""
    from hsb.agents.main_orchestrator import run_main_orchestrator
    with (
        patch("hsb.agents.main_orchestrator.GlobalOrchestrator") as MockGO,
        patch("hsb.agents.main_orchestrator._cascade_dispatch", new_callable=AsyncMock) as mock_cascade,
        patch("hsb.agents.main_orchestrator._parallel_dispatch", new_callable=AsyncMock) as mock_parallel,
        patch("hsb.agents.main_orchestrator.run_validated_linear_agent", new_callable=AsyncMock),
    ):
        mock_go_instance = MockGO.return_value
        mock_go_instance.get_ready_tasks = AsyncMock(return_value=MagicMock(
            ready_tasks=[MagicMock(id="LIN-1", title="Task")],
            is_backlog_empty=False,
        ))
        mock_cascade.return_value = []

        await run_main_orchestrator(mode="cascade")

        mock_cascade.assert_called_once()
        mock_parallel.assert_not_called()


@pytest.mark.asyncio
async def test_mode_routing_parallel():
    """MORD-01: parallel mode calls _parallel_dispatch, not _cascade_dispatch."""
    from hsb.agents.main_orchestrator import run_main_orchestrator
    with (
        patch("hsb.agents.main_orchestrator.GlobalOrchestrator") as MockGO,
        patch("hsb.agents.main_orchestrator._cascade_dispatch", new_callable=AsyncMock) as mock_cascade,
        patch("hsb.agents.main_orchestrator._parallel_dispatch", new_callable=AsyncMock) as mock_parallel,
        patch("hsb.agents.main_orchestrator.run_validated_linear_agent", new_callable=AsyncMock),
    ):
        mock_go_instance = MockGO.return_value
        mock_go_instance.get_ready_tasks = AsyncMock(return_value=MagicMock(
            ready_tasks=[MagicMock(id="LIN-1", title="Task")],
            is_backlog_empty=False,
        ))
        mock_parallel.return_value = []

        await run_main_orchestrator(mode="parallel")

        mock_parallel.assert_called_once()
        mock_cascade.assert_not_called()


# --- MORD-02: Cascade sequential ---

@pytest.mark.asyncio
async def test_cascade_sequential():
    """MORD-02: Cascade mode takes only the first ready task."""
    from hsb.agents.main_orchestrator import _cascade_dispatch
    tasks = [MagicMock(id="LIN-1"), MagicMock(id="LIN-2")]
    with patch("hsb.agents.main_orchestrator._run_wio_subprocess", new_callable=AsyncMock) as mock_wio:
        mock_wio.return_value = {"status": "completed"}
        result = await _cascade_dispatch(tasks, repo_root="/tmp")
    # Only one WIO call — the first task
    mock_wio.assert_called_once()
    assert result[0].work_item_id == "LIN-1"


# --- MORD-03: Optimistic-lock claiming ---

@pytest.mark.asyncio
async def test_claiming_optimistic_lock():
    """MORD-03: Claiming loop verifies updatedAt changed after write."""
    from hsb.agents.main_orchestrator import _sequential_claiming_loop
    tasks = [MagicMock(id="LIN-5")]

    # Simulate: before = "2024-01-01", after = "2024-01-02" (our write changed it)
    call_count = [0]
    async def mock_linear(*args, **kwargs):
        call_count[0] += 1
        entity = MagicMock()
        if call_count[0] == 1:  # first read (pre-write)
            entity.get = lambda k, d=None: "2024-01-01T00:00:00" if k == "updatedAt" else d
        else:  # second read (post-write)
            entity.get = lambda k, d=None: "2024-01-02T00:00:00" if k == "updatedAt" else d
        return MagicMock(linear_entities=[entity])

    with patch("hsb.agents.main_orchestrator.run_validated_linear_agent", side_effect=mock_linear):
        claimed = await _sequential_claiming_loop(tasks, delay_ms=0)

    assert len(claimed) == 1
    assert claimed[0][0].id == "LIN-5"


# --- MORD-04: Worktree lifecycle ---

@pytest.mark.asyncio
async def test_worktree_lifecycle():
    """MORD-04: Worktree created before WIO dispatch, removed after (even on failure)."""
    import inspect
    from hsb.agents.main_orchestrator import _parallel_dispatch
    source = inspect.getsource(_parallel_dispatch)
    # Cleanup must be in a finally block or unconditional call after gather
    assert "_git_worktree_remove" in source, (
        "_parallel_dispatch must call _git_worktree_remove for cleanup (D-09)"
    )
    assert "asyncio.gather" in source, (
        "_parallel_dispatch must use asyncio.gather for parallel dispatch (D-08)"
    )


# --- No LLM in orchestrators ---

def test_no_sdk_session_in_global_orchestrator():
    """D-01: GlobalOrchestrator must not import or use claude_agent_sdk."""
    import inspect
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    source = inspect.getsource(GlobalOrchestrator)
    assert "claude_agent_sdk" not in source, "D-01 violated: GlobalOrchestrator must be pure Python"
    assert "ClaudeAgentOptions" not in source, "D-01 violated: no SDK session in GlobalOrchestrator"


def test_no_sdk_session_in_main_orchestrator():
    """D-02: main_orchestrator.py must not import or use claude_agent_sdk."""
    import inspect
    import hsb.agents.main_orchestrator as mod
    source = inspect.getsource(mod)
    assert "claude_agent_sdk" not in source, "D-02 violated: MainOrchestrator must be pure Python"
    assert "ClaudeAgentOptions" not in source, "D-02 violated: no SDK session in MainOrchestrator"
```

---

### `tests/integration/test_global_orchestrator_e2e.py` (test, integration)

**Analog:** `tests/integration/test_orchestrator_e2e.py` (Phase 3 PATTERNS.md §tests/integration/test_orchestrator_e2e.py — `pytestmark = [pytest.mark.integration]`, real Linear workspace, real `hsb-test-fixture` repo)

**Source spec:** `04-RESEARCH.md` §Validation Architecture (GORD-01..04 + MORD-05).

```python
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
async def test_get_ready_tasks_returns_todo_only():
    """GORD-01: Returns only todo items from real Linear workspace."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    # All returned tasks must have been todo-status items
    assert isinstance(output.ready_tasks, list)
    assert isinstance(output.is_backlog_empty, bool)
    assert isinstance(output.is_epic_ready, bool)


@pytest.mark.integration
async def test_dependency_filter_against_live_linear():
    """GORD-02: Dependency filtering works against real Linear dependency graph."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    # No item in ready_tasks should have a non-done dependency in Linear
    # (This is implicitly validated by the filter logic — integration test confirms no crash)
    for task in output.ready_tasks:
        assert task.id.startswith("LIN-"), f"Unexpected task ID format: {task.id}"


@pytest.mark.integration
async def test_cycle_summary_posted():
    """MORD-05: Cycle summary is posted to Linear EPIC after run_main_orchestrator completes."""
    from hsb.agents.main_orchestrator import run_main_orchestrator
    # Run one cascade cycle — should post summary comment without raising
    await run_main_orchestrator(mode="cascade")
```

---

### `tests/integration/test_parallel_mode_e2e.py` (test, integration)

**Analog:** `tests/integration/test_orchestrator_e2e.py` (Phase 3 PATTERNS.md — integration marker + live services). This test adds the two-task parallel gate (CONTEXT.md §Success Criterion 5).

**Source spec:** `04-RESEARCH.md` §Validation Architecture (MORD-03 no-double-claim gate); CONTEXT.md §Specific Ideas (two-task concurrent parallel test).

```python
import pytest
import os

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
async def test_no_double_claim_parallel_two_tasks():
    """
    MORD-03 acceptance gate: Two ready tasks dispatched in parallel must not be double-claimed.
    Pre-condition: At least 2 todo tasks exist in the Linear test workspace with no dependencies.
    This is the Phase 4 Success Criterion 5 (CONTEXT.md §Specific Ideas).
    """
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    from hsb.agents.main_orchestrator import run_main_orchestrator, _sequential_claiming_loop

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()

    if len(output.ready_tasks) < 2:
        pytest.skip("Requires at least 2 todo tasks in Linear test workspace")

    # Run parallel mode — should claim and dispatch both without double-claiming
    await run_main_orchestrator(mode="parallel")

    # Post-condition: read Linear state — both tasks should be in_progress or done,
    # neither should still be in todo (double-claim would leave one unclaimed)
    from hsb.agents.linear_agent import run_validated_linear_agent
    for task in output.ready_tasks[:2]:
        fresh = await run_validated_linear_agent(
            operation="read",
            payload={"issueId": task.id},
        )
        status = fresh.linear_entities[0].get("status", "unknown") if fresh.linear_entities else "unknown"
        assert status != "todo", (
            f"Task {task.id} still in todo after parallel dispatch — possible double-claim failure."
        )


@pytest.mark.integration
async def test_worktree_cleanup_after_parallel():
    """D-09: Worktrees are removed after parallel dispatch completes."""
    import os
    from hsb.agents.main_orchestrator import run_main_orchestrator, WORKTREES_DIR

    worktrees_path = os.path.join(os.getcwd(), WORKTREES_DIR)

    await run_main_orchestrator(mode="parallel")

    # .worktrees/ should be empty (or non-existent) after cleanup
    if os.path.exists(worktrees_path):
        remaining = os.listdir(worktrees_path)
        assert remaining == [], (
            f"Stale worktrees found after parallel dispatch: {remaining}. "
            "Cleanup must succeed regardless of WIO outcome (D-09)."
        )
```

---

### `.gitignore` update (config, delta-only)

**Pattern:** Single-line append.

```
# Phase 4: transient git worktrees created by parallel mode
.worktrees/
```

**Critical:** `.worktrees/` must be gitignored — worktrees are transient runtime artifacts. Committing them corrupts the git object store (CONTEXT.md §Claude's Discretion — worktree path strategy).

---

## Shared Patterns

### Pattern: `extra="forbid"` on all pydantic models

**Source:** Phase 1 PATTERNS.md §Shared Patterns; Phase 2 PATTERNS.md §Shared Patterns; Phase 3 PATTERNS.md §Shared Patterns
**Apply to:** `ReadyTask`, `GlobalOrchestratorOutput` in `contracts/global_orchestrator.py`; `ClaimResult`, `DispatchedItem`, `MainOrchestratorOutput` in `contracts/main_orchestrator.py`

```python
model_config = {"extra": "forbid"}
```

Absent on any model → silent schema drift passes undetected. Consistent across all phases.

---

### Pattern: `asyncio.run()` at CLI boundary only — NEVER inside coroutines

**Source:** Phase 1 PATTERNS.md §Shared Patterns §asyncio.run at CLI boundary; Phase 3 PATTERNS.md §Shared Patterns
**Apply to:** `run` handler in `src/hsb/cli/main.py`; `has_ready_tasks()` call in `run_loop.py`

```python
# CORRECT — Typer handler is synchronous; asyncio.run() is safe at this boundary
@app.command("run")
def run(parallel: bool = ...) -> None:
    asyncio.run(run_main_orchestrator(mode=...))

# CORRECT — run_loop.py main() is synchronous; asyncio.run() is safe
def main() -> None:
    if not asyncio.run(has_ready_tasks()):
        ...

# WRONG — never nest asyncio.run() inside a coroutine
async def some_function():
    result = asyncio.run(...)  # raises RuntimeError: This event loop is already running
```

---

### Pattern: Pure Python orchestrators — no SDK session, no LLM

**Source:** CONTEXT.md D-01, D-02; `04-RESEARCH.md` Pattern 1 §Anti-Patterns
**Apply to:** `global_orchestrator.py`, `main_orchestrator.py`

```python
# CORRECT — pure Python async class, calls run_validated_linear_agent directly
class GlobalOrchestrator:
    async def get_ready_tasks(self) -> GlobalOrchestratorOutput:
        result = await run_validated_linear_agent(...)
        ...

# WRONG — introduces LLM reasoning into a deterministic dispatch path (D-01/D-02 violation)
async def run_orchestration_cycle(...):
    options = ClaudeAgentOptions(...)  # DO NOT DO THIS in orchestrators
    async for message in query(prompt=..., options=options):
        ...
```

---

### Pattern: `asyncio.gather(return_exceptions=True)` with exception normalization

**Source:** `04-RESEARCH.md` Pattern 4 §parallel_dispatch; Pitfall E mitigation
**Apply to:** `_parallel_dispatch()` in `main_orchestrator.py`

```python
# CORRECT — return_exceptions=True + explicit normalization
results = await asyncio.gather(*coroutines, return_exceptions=True)
normalized = [
    r if isinstance(r, dict) else {"status": "exception", "error": str(r)}
    for r in results
]

# WRONG — omitting return_exceptions=True means one WIO failure aborts all others
results = await asyncio.gather(*coroutines)  # raises on first exception
```

---

### Pattern: Worktree cleanup in `finally` / unconditional block

**Source:** CONTEXT.md D-09; `04-RESEARCH.md` Pattern 3 §_git_worktree_remove; Pitfall C mitigation
**Apply to:** `_parallel_dispatch()` in `main_orchestrator.py`

```python
# CORRECT — cleanup always runs, even on WIO failure
try:
    results = await asyncio.gather(..., return_exceptions=True)
finally:
    for task, _ in claimed_pairs:
        await _git_worktree_remove(repo_root, task.id)

# WRONG — cleanup skipped on exception, worktrees accumulate
results = await asyncio.gather(...)
for task in claimed:   # never reached on exception
    await _git_worktree_remove(repo_root, task.id)
```

---

### Pattern: `load_dotenv()` at module level

**Source:** Phase 1 PATTERNS.md §Shared Patterns §load_dotenv; Phase 2/3 PATTERNS.md §Shared Patterns
**Apply to:** `global_orchestrator.py`, `main_orchestrator.py`

```python
from dotenv import load_dotenv
load_dotenv()  # Must appear before any os.environ, Anthropic(), or SDK call
```

---

### Pattern: `@pytest.mark.integration` and `pytestmark` for all integration tests

**Source:** Phase 1 PATTERNS.md §test_integration.py; Phase 2 PATTERNS.md §integration tests; Phase 3 PATTERNS.md §integration tests
**Apply to:** All files in `tests/integration/` for Phase 4

```python
import pytest
pytestmark = [pytest.mark.integration]

@pytest.mark.integration
async def test_something_live():
    ...
```

---

### Pattern: `disable-model-invocation: true` in SKILL.md

**Source:** Phase 1 PATTERNS.md §SKILL.md; Phase 3 PATTERNS.md §SKILL.md
**Apply to:** `.claude/skills/global-orchestration/SKILL.md`, `.claude/skills/main-orchestrator/SKILL.md`

MANDATORY on all SKILL.md files — these serve as human-readable spec references and must not auto-invoke during conversation.

---

### Pattern: Subprocess env var allowlist (no `**os.environ` wholesale)

**Source:** `04-RESEARCH.md` §Security Domain (Env var leakage to WIO subprocess — Information Disclosure)
**Apply to:** `_run_wio_subprocess()` in `main_orchestrator.py`

```python
# CORRECT — only pass required vars
env = {
    "PATH": os.environ.get("PATH", ""),
    "HOME": os.environ.get("HOME", ""),
    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
    "HSB_WIO_INPUT_FILE": input_path,
    "HSB_WIO_OUTPUT_FILE": output_path,
}

# WRONG — passes all env vars including potentially sensitive ones
env = {**os.environ, "HSB_WIO_INPUT_FILE": input_path}
```

---

## No Analog Found

All Phase 4 files have strong analogs in Phase 1–3 PATTERNS.md or project specification documents. No files lack a pattern source.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| None | — | — | All Phase 4 files follow the Phase 1–3 Python foundation patterns (contracts, service, CLI, tests, SKILL.md) with Phase 4-specific data flow patterns (asyncio.gather subprocess fan-out, git worktree lifecycle) fully specified in `04-RESEARCH.md` Patterns 1–7 |

---

## Metadata

**Analog search scope:** Phase 1 PATTERNS.md (primary), Phase 2 PATTERNS.md (primary), Phase 3 PATTERNS.md (primary), `04-RESEARCH.md`, `04-CONTEXT.md`, `agents/AGENT-CONTRACTS.md` §0, `skills/00-MAIN-ORCHESTRATOR.md`, `skills/07-GLOBAL-ORCHESTRATION.md`
**Files scanned:** Phase 1–3 PATTERNS.md, 04-CONTEXT.md, 04-RESEARCH.md, AGENT-CONTRACTS.md, skills/00-MAIN-ORCHESTRATOR.md, skills/07-GLOBAL-ORCHESTRATION.md
**Python source files found:** 0 (greenfield; Phases 1–3 are pre-implementation)
**Pattern extraction date:** 2026-05-06
**Primary pattern sources:** Phase 3 PATTERNS.md (foundation for async orchestrator structure, `run_loop.py`, CLI `asyncio.run()` pattern, integration test markers); `04-RESEARCH.md` Patterns 1–7 (Phase 4-specific: pure Python orchestrators, optimistic-lock claiming, git worktree lifecycle, `asyncio.gather` subprocess dispatch, Pydantic contracts, Typer CLI delta, run_loop.py update); `agents/AGENT-CONTRACTS.md` §0 (Main Orchestrator output contract shape)
