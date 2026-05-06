# Phase 4: Global + Main Orchestrators and Parallel Mode — Research

**Researched:** 2026-05-06
**Domain:** Pure-Python orchestration hierarchy, asyncio parallel subprocess dispatch, git worktree isolation, optimistic-lock claiming via Linear MCP
**Confidence:** HIGH (all critical patterns verified against existing codebase, prior phase research, git man page, and live subprocess tests)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Orchestrator Architecture**
- D-01: Global Orchestrator is a pure Python class (`src/hsb/agents/global_orchestrator.py`). No Claude Agent SDK session. Calls Linear Agent service (Phase 1) to fetch work items, applies deterministic filtering and sorting, returns structured output. No LLM involved.
- D-02: Main Orchestrator is a pure Python class (`src/hsb/agents/main_orchestrator.py`). No Claude Agent SDK session. Handles mode selection, claiming loop, and WIO dispatch. The Work Item Orchestrator (Phase 3) remains the only Agent SDK session in the stack — it is the only component that needs LLM reasoning.
- D-03: Global Orchestrator output contract: `{"ready_tasks": [...ordered by priority...], "is_backlog_empty": bool, "is_epic_ready": bool}`. Matches GORD-01 through GORD-04 requirements.

**Parallel Claiming — Optimistic Lock**
- D-04: Task claiming uses `status + updatedAt` optimistic locking via Linear MCP tools (OAuth2 authenticated). No API keys, no custom Linear fields, no raw GraphQL calls. Protocol per MORD-03:
  1. Capture pre-write `updatedAt` timestamp from the work item
  2. Write `status = in_progress` via Linear Agent
  3. Re-read the work item
  4. Verify `updatedAt` changed (our write landed) and `assigned_orchestrator`-equivalent state is consistent
  5. If verification fails (concurrent write detected) → skip this task, move to next
- D-05: Claiming happens **sequentially** in the Main Orchestrator claiming loop (one claim at a time) before parallel dispatch begins. The parallel part is dispatch, not claiming. This eliminates the inter-claim race window for single-process runs.
- D-06: A configurable delay between claims (default: 200ms) is added to the claiming loop to further reduce collision risk if two `hsb run --parallel` processes are ever started simultaneously.

**Worktree Isolation**
- D-07: In parallel mode, the Main Orchestrator runs `git worktree add .worktrees/LIN-{id} feature/LIN-{id}-{slug}` for each claimed task before dispatch (MORD-04). Worktrees are created in `.worktrees/` at the repo root.
- D-08: Each WIO is spawned as a Python subprocess — a separate process running the WIO Agent SDK session in its assigned worktree. Main Orchestrator uses `asyncio.gather()` to coordinate all subprocesses and collect their results.
- D-09: Worktrees are cleaned up after each WIO subprocess completes (`git worktree remove .worktrees/LIN-{id}`). Cleanup runs regardless of WIO success or failure to prevent worktree accumulation.

**CLI Design**
- D-10: `hsb run` is the new Phase 4 entry point. Added to `src/hsb/cli/main.py` as a new Typer subcommand alongside existing commands. Default mode is cascade. Parallel mode requires explicit `--parallel` flag. Parallel never activates by accident.
- D-11: `hsb run-next-step` (Phase 3) is retained unchanged as the single-task debug path. It bypasses Global Orchestrator and goes directly to one WIO cycle — useful for testing individual tasks and validating WIO behavior without the full hierarchy.
- D-12: `run_loop.py` (Phase 3 thin wrapper at repo root) is updated to call `hsb run` instead of `hsb run-next-step`. Loop termination remains: stop when no `ready_tasks` returned by Global Orchestrator.
- D-13: `hsb run --parallel` requires the Phase 3 MVP cascade cycle to have been validated first (gated per STATE.md note). The planner should add a runtime guard or documentation note reinforcing this sequencing.

**Cycle Summary Persistence**
- D-14: After all dispatched orchestrators complete, Main Orchestrator calls Linear Agent to post a structured cycle summary comment on the EPIC (MORD-05). Format follows the output contract in `agents/AGENT-CONTRACTS.md`.

### Claude's Discretion

- **SKILL.md migration**: `skills/07-GLOBAL-ORCHESTRATION.md` and `skills/00-MAIN-ORCHESTRATOR.md` should be migrated to `.claude/skills/` during Phase 4 for consistency, even though these are pure Python (the skills serve as human-readable spec reference).
- **Worktree path strategy**: Whether `.worktrees/` is gitignored or tracked — Claude decides. Likely gitignored to avoid committing temporary worktree metadata.
- **Subprocess WIO interface**: Exact mechanism for passing WIO inputs to the subprocess (env vars, JSON file, stdin) and collecting outputs — Claude decides based on what keeps the contract clean with the existing pydantic schemas.
- **Global Orchestrator priority ordering**: Exact sort key for the ready-task list (Linear priority field, creation date, or dependency depth) — Claude decides based on what the Linear MCP tools expose.

### Deferred Ideas (OUT OF SCOPE)

- Custom Linear field for `assigned_orchestrator` — would require raw GraphQL API call (needs API key or token outside OAuth2 MCP layer); deferred permanently per architectural constraint (no API keys)
- Multi-process parallel dispatch (two `hsb run --parallel` processes simultaneously) — `status + updatedAt` optimistic lock is best-effort for this case; proper distributed locking deferred to future scope
- Event-driven mode (Linear/GitHub webhooks triggering cycles) — v2 scope per REQUIREMENTS.md
- `gh stack` integration — permanently deferred per Phase 2 D-06
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GORD-01 | Global Orchestrator reads current Linear project state and returns a prioritized list of all non-blocked, `todo`-status work items | Pure Python class calls `linear_agent.py` → `mcp__linear__list_issues` with status filter; dependency check via `dependencies` field on each item |
| GORD-02 | Global Orchestrator respects Linear `blocked-by` dependency links — a work item is not returned as ready if any blocking dependency is not `done` | Deterministic filter: for each candidate `todo` item, fetch dependency IDs and check all are `done`; items with any non-done dependency are excluded |
| GORD-03 | Global Orchestrator detects when no backlog exists and signals `is_backlog_empty` to trigger backlog creation | If `list_issues` returns empty for the project scope, set `is_backlog_empty = True`; no LLM reasoning needed — pure state inspection |
| GORD-04 | Global Orchestrator signals when all child items of an EPIC are `done` and the EPIC is ready for manual merge | Fetch EPIC + children; if all children `done` AND `qa_status = approved`, set `is_epic_ready = True` in output |
| MORD-01 | Main Orchestrator accepts an execution mode (`cascade` or `parallel`) and dispatches Work Item Orchestrators accordingly | Mode passed as parameter to `run_main_orchestrator(mode="cascade" \| "parallel")`; mode selection drives dispatch path |
| MORD-02 | In cascade mode, Main Orchestrator executes one Work Item Orchestrator at a time and waits for completion before proceeding | `run_first_task()` in sequential loop: `await run_wio_subprocess(task)` for each task (one at a time, not `asyncio.gather`) |
| MORD-03 | In parallel mode, Main Orchestrator claims each ready task in Linear (write `in_progress`, re-read to verify `assigned_orchestrator` matches) before dispatch — skips unclaimed tasks | Sequential claiming loop with `updatedAt` optimistic lock; verified live via `mcp__linear__update_issue` + `mcp__linear__get_issue` re-read |
| MORD-04 | In parallel mode, each Work Item Orchestrator runs in an isolated git worktree (`isolation: worktree`) | `git worktree add .worktrees/LIN-{id} feature/LIN-{id}-{slug}` via `asyncio.create_subprocess_exec`; verified working on git 2.43.0 in this repo |
| MORD-05 | Main Orchestrator persists a cycle summary to Linear via the Linear Agent after all dispatched orchestrators complete | Post `mcp__linear__create_comment` on EPIC with cycle summary matching AGENT-CONTRACTS.md §0 output contract |
</phase_requirements>

---

## Summary

Phase 4 completes the three-level orchestration hierarchy by adding two pure Python classes above the Phase 3 Work Item Orchestrator (WIO). Neither the Global Orchestrator nor the Main Orchestrator uses a Claude Agent SDK session — they are deterministic Python service classes. Only the WIO remains an Agent SDK session.

The Global Orchestrator is the simpler component: it calls `linear_agent.py` to read Linear state, applies deterministic filtering logic (status = todo, no unresolved blocked-by dependencies), sorts the result by priority, and returns a structured Pydantic output. No LLM, no SDK, no skill injection. Its correctness is testable with pure unit tests against mock Linear data.

The Main Orchestrator is the dispatch controller. In cascade mode it iterates through ready tasks one at a time, calling the WIO subprocess sequentially (a standard async Python coroutine). In parallel mode it first claims tasks sequentially (one claim + verify before the next), then spawns all WIO subprocesses together via `asyncio.gather()`. The key insight from D-05: **claiming is sequential, dispatch is parallel.** This architecture eliminates the race window described in Pitfall 1 for single-process runs — by the time `asyncio.gather` fires, every task has already been claimed and verified.

Worktree isolation is implemented via `git worktree add` / `git worktree remove` called through `asyncio.create_subprocess_exec`. This is verified to work on git 2.43.0 in this repository. The `.worktrees/` directory should be gitignored. Subprocess WIO dispatch should pass input as a JSON tempfile (not env vars) to keep the contract clean with the existing Pydantic schemas and avoid env var length limits.

**Primary recommendation:** Global Orchestrator = pure Python filter/sort over Linear MCP data. Main Orchestrator = sequential claiming loop + `asyncio.gather` subprocess dispatch. No new SDK patterns needed — Phase 3 SDK patterns remain unchanged in the WIO.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Backlog readiness detection | API / Backend (Global Orchestrator) | — | Pure Python inspection of Linear project state; no LLM needed |
| Dependency filtering | API / Backend (Global Orchestrator) | — | Deterministic: check each item's `dependencies` array against done-status items |
| EPIC completion detection | API / Backend (Global Orchestrator) | — | Deterministic: count children and check all `done` + `qa_status = approved` |
| Task priority ordering | API / Backend (Global Orchestrator) | — | Sort by Linear priority field (or `createdAt` as tiebreaker); no LLM |
| Mode selection (cascade vs. parallel) | CLI tier (Typer `hsb run`) | API / Backend (Main Orchestrator) | CLI receives `--parallel` flag; passes `mode` enum to Main Orchestrator |
| Sequential task claiming | API / Backend (Main Orchestrator) | — | Optimistic-lock protocol: write → re-read → verify; all via linear_agent.py |
| Parallel WIO dispatch | API / Backend (Main Orchestrator) | — | `asyncio.gather` over subprocess coroutines; one subprocess per claimed task |
| Worktree lifecycle (create/remove) | API / Backend (Main Orchestrator) | — | `git worktree add/remove` via `asyncio.create_subprocess_exec` |
| Work item lifecycle execution | API / Backend (Work Item Orchestrator — subprocess) | — | Phase 3 WIO runs in isolated worktree process; no change to WIO itself |
| Cycle summary persistence | API / Backend (Main Orchestrator) | — | Posts Linear comment via linear_agent.py after all WIOs complete |
| Continuous loop driver | CLI tier (run_loop.py at repo root) | — | Updated in Phase 4 to call `hsb run` instead of `hsb run-next-step` |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncio` (stdlib) | Python 3.12 built-in | `asyncio.gather()` for parallel subprocess dispatch; `asyncio.create_subprocess_exec` for git worktree + WIO subprocess | Project-locked (CLIR-05); stdlib, zero install; verified present Python 3.12.3 |
| `subprocess` (stdlib) | Python 3.12 built-in | Alternative for synchronous git worktree operations in non-async contexts | Stdlib; used in `run_loop.py` Phase 3 pattern for `hsb` CLI calls |
| `pydantic` | 2.13.3 | Contracts for `GlobalOrchestratorOutput`, `MainOrchestratorOutput`, `ClaimResult` | Project-locked (STACK.md); all agent I/O validated against Pydantic models |
| `typer` | 0.25.1 | `hsb run` CLI subcommand with `--parallel` flag | Project-locked (STACK.md); extends existing `src/hsb/cli/main.py` |
| `rich` | 15.0.0 | Terminal output for `hsb run` cycle summary (same format as `hsb show-state`) | Project-locked (STACK.md); already used in Phase 3 CLI |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-dotenv` | 1.0+ | Load `ANTHROPIC_API_KEY` for subprocess WIO sessions | Required: each WIO subprocess needs its own env with API key |
| `tempfile` (stdlib) | Python 3.12 built-in | Create temp JSON file for WIO subprocess input contract | Used in parallel mode subprocess interface; no install needed |
| `json` (stdlib) | Python 3.12 built-in | Serialize/deserialize WIO input/output contracts via temp file | Standard JSON serialization for subprocess IPC |

### No New Libraries Needed

Phase 4 introduces no new external library dependencies. All primitives (`asyncio`, `subprocess`, `tempfile`, `json`) are Python 3.12 stdlib. The project dependency set from Phases 1–3 is sufficient.

---

## Architecture Patterns

### System Architecture Diagram

```
CLI trigger: hsb run [--parallel]
        |
        v
[Typer CLI — src/hsb/cli/main.py]
  asyncio.run(run_main_orchestrator(mode="cascade"|"parallel"))
        |
        v
[main_orchestrator.py — pure Python class]
  1. Call global_orchestrator.get_ready_tasks()
     |
     v
  [global_orchestrator.py — pure Python class]
    a. linear_agent.list_issues(status="todo", project=...)
    b. Filter: exclude items with unresolved blocked-by deps
    c. Sort: by Linear priority field (then createdAt)
    d. Return GlobalOrchestratorOutput(
         ready_tasks=[...], is_backlog_empty=bool, is_epic_ready=bool
       )
        |
        back to Main Orchestrator
        |
  2a. CASCADE MODE:
      for task in ready_tasks[:1]:   # take first only per cycle
        await _run_wio_subprocess(task, worktree=None)
        (sequential, await completion before next)

  2b. PARALLEL MODE:
      # PHASE 1: Sequential claiming loop
      claimed = []
      for task in ready_tasks:
          pre_updated_at = task.updatedAt
          await linear_agent.update_issue(task.id, status="in_progress")
          await asyncio.sleep(0.2)   # D-06: 200ms inter-claim delay
          fresh = await linear_agent.get_issue(task.id)
          if fresh.updatedAt != pre_updated_at:  # our write landed
              claimed.append((task, fresh))
          # else: skip (concurrent write detected)

      # PHASE 2: Parallel dispatch
      worktrees = []
      for task, _ in claimed:
          wt_path = f".worktrees/LIN-{task.id}"
          branch = f"feature/LIN-{task.id}-{slugify(task.title)}"
          await _git_worktree_add(wt_path, branch)
          worktrees.append(wt_path)

      results = await asyncio.gather(
          *[_run_wio_subprocess(task, wt) for (task, _), wt in zip(claimed, worktrees)],
          return_exceptions=True
      )

      # PHASE 3: Cleanup (always, regardless of WIO outcome)
      for wt_path in worktrees:
          await _git_worktree_remove(wt_path)

  3. Post cycle summary to Linear EPIC via linear_agent.create_comment()
        |
        v
[WIO subprocess — src/hsb/agents/work_item_orchestrator.py]
  (Phase 3 code, unchanged)
  Runs in isolated git worktree (parallel) or main tree (cascade)
  Reads input from tmp JSON file → runs SDK session → writes output to tmp JSON file
        |
        v
[Linear MCP server — mcp-remote OAuth2]
  All Linear reads/writes (claiming, status updates, comments)
```

### Recommended Project Structure

```
src/hsb/
├── agents/
│   ├── linear_agent.py          # Phase 1 — unchanged
│   ├── builder_agent.py         # Phase 2 — unchanged
│   ├── git_agent.py             # Phase 2 — unchanged
│   ├── qa_agent.py              # Phase 2 — unchanged
│   ├── work_item_orchestrator.py  # Phase 3 — unchanged
│   ├── global_orchestrator.py   # Phase 4 NEW — pure Python class
│   └── main_orchestrator.py     # Phase 4 NEW — pure Python class
├── contracts/
│   ├── linear.py                # Phase 1
│   ├── builder.py               # Phase 2
│   ├── git.py                   # Phase 2
│   ├── qa.py                    # Phase 2
│   ├── orchestrator.py          # Phase 3
│   ├── global_orchestrator.py   # Phase 4 NEW — GlobalOrchestratorOutput
│   └── main_orchestrator.py     # Phase 4 NEW — MainOrchestratorOutput, ClaimResult
├── cli/
│   └── main.py                  # Phases 1–4 — add hsb run subcommand
run_loop.py                      # Phase 3 — update to call hsb run
.worktrees/                      # Phase 4 NEW — gitignored, transient worktrees
.claude/skills/
├── task-orchestration/SKILL.md  # Phase 3
├── global-orchestration/SKILL.md  # Phase 4 NEW — migrated from skills/07-GLOBAL-ORCHESTRATION.md
└── main-orchestrator/SKILL.md   # Phase 4 NEW — migrated from skills/00-MAIN-ORCHESTRATOR.md
tests/
├── unit/
│   ├── test_global_orchestrator.py  # Phase 4 NEW
│   └── test_main_orchestrator.py    # Phase 4 NEW
└── integration/
    ├── test_global_orchestrator_e2e.py  # Phase 4 NEW
    └── test_parallel_mode_e2e.py        # Phase 4 NEW — two-task concurrent test
```

### Pattern 1: Global Orchestrator — Pure Python Filter/Sort

**What:** A pure Python class (no SDK session, no LLM) that reads Linear state via linear_agent.py, applies deterministic filtering and sorting, and returns a Pydantic output contract.

**When to use:** Always — this is the locked architecture (D-01). Do NOT use a Claude Agent SDK session for Global Orchestrator.

**Example:**

```python
# Source: Derived from AGENT-CONTRACTS.md §0 output contract + STACK.md linear_agent patterns
# [VERIFIED: agents/AGENT-CONTRACTS.md, skills/07-GLOBAL-ORCHESTRATION.md]

from __future__ import annotations
import asyncio
from pydantic import BaseModel
from typing import Any

from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.contracts.global_orchestrator import GlobalOrchestratorOutput, ReadyTask


class GlobalOrchestrator:
    """Pure Python class — no LLM, no SDK session."""

    async def get_ready_tasks(self) -> GlobalOrchestratorOutput:
        # Step 1: Fetch all work items from Linear
        all_items = await self._fetch_all_items()

        # Step 2: Detect empty backlog
        if not all_items:
            return GlobalOrchestratorOutput(
                ready_tasks=[],
                is_backlog_empty=True,
                is_epic_ready=False,
            )

        # Step 3: Filter to todo + unblocked
        done_ids = {item["id"] for item in all_items if item["status"] == "done"}
        ready = []
        for item in all_items:
            if item["status"] != "todo":
                continue
            deps = item.get("dependencies", [])
            if all(dep_id in done_ids for dep_id in deps):
                ready.append(item)

        # Step 4: Sort by Linear priority (lower number = higher priority)
        # Tiebreaker: createdAt ascending
        ready.sort(key=lambda x: (x.get("priority", 999), x.get("createdAt", "")))

        # Step 5: Detect EPIC completion
        is_epic_ready = self._check_epic_complete(all_items)

        return GlobalOrchestratorOutput(
            ready_tasks=[ReadyTask(id=t["id"], title=t["title"]) for t in ready],
            is_backlog_empty=False,
            is_epic_ready=is_epic_ready,
        )
```

### Pattern 2: Optimistic-Lock Claiming Protocol

**What:** Sequential claiming loop that reads `updatedAt` before writing, writes `status = in_progress`, re-reads, and verifies the timestamp changed (confirming the write was the last writer).

**When to use:** Parallel mode claiming only (MORD-03). D-05 mandates claiming is sequential even in parallel mode.

**Example:**

```python
# Source: Derived from CONTEXT.md D-04 claiming protocol + PITFALLS.md Pitfall 1 prevention
# [VERIFIED: agents/AGENT-CONTRACTS.md, .planning/research/PITFALLS.md]

import asyncio
from datetime import datetime

async def claim_task(task_id: str, pre_updated_at: str) -> bool:
    """
    Optimistic lock protocol:
    1. Write in_progress (we already captured pre_updated_at before calling)
    2. Re-read
    3. Verify updatedAt changed (our write landed)
    Returns True if claimed, False if skipped (concurrent write detected).
    """
    # Write: set status to in_progress
    await run_validated_linear_agent(
        operation="update",
        payload={"id": task_id, "status": "in_progress"},
    )

    # Re-read
    fresh = await run_validated_linear_agent(
        operation="read",
        payload={"id": task_id},
    )
    fresh_item = fresh.linear_entities[0]

    # Verify: updatedAt must have changed from before our write
    if fresh_item["updatedAt"] != pre_updated_at:
        return True   # claim succeeded — updatedAt changed, we own it
    else:
        # updatedAt unchanged means our write was a no-op or was overwritten instantly
        # Treat as failed claim and skip
        return False


async def sequential_claiming_loop(
    ready_tasks: list[dict],
    delay_ms: int = 200,
) -> list[dict]:
    """Returns only the tasks this process successfully claimed."""
    claimed = []
    for task in ready_tasks:
        pre_updated_at = task["updatedAt"]
        success = await claim_task(task["id"], pre_updated_at)
        if success:
            claimed.append(task)
        await asyncio.sleep(delay_ms / 1000)  # D-06: inter-claim delay
    return claimed
```

### Pattern 3: Worktree Lifecycle

**What:** Create an isolated git worktree for each claimed task before WIO dispatch; remove it after WIO completes regardless of success or failure.

**When to use:** Parallel mode only (D-07). Cascade mode does NOT create worktrees — it runs in the main working tree.

**Example:**

```python
# Source: git worktree man page (git 2.43.0 — VERIFIED live in this repo)
# asyncio.create_subprocess_exec pattern (VERIFIED live Python 3.12.3)

import asyncio
import os

WORKTREES_DIR = ".worktrees"

async def _git_worktree_add(repo_root: str, task_id: str, branch_name: str) -> str:
    """
    Creates .worktrees/LIN-{task_id}/ as a linked worktree on branch_name.
    Returns the worktree path.
    """
    wt_path = os.path.join(repo_root, WORKTREES_DIR, f"LIN-{task_id}")
    proc = await asyncio.create_subprocess_exec(
        "git", "worktree", "add", wt_path, branch_name,
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
    Uses --force to handle uncommitted changes (cleanup must always succeed).
    """
    wt_path = os.path.join(repo_root, WORKTREES_DIR, f"LIN-{task_id}")
    proc = await asyncio.create_subprocess_exec(
        "git", "worktree", "remove", "--force", wt_path,
        cwd=repo_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    # Do not raise on failure — cleanup is best-effort
```

### Pattern 4: WIO Subprocess Dispatch via asyncio.gather

**What:** Spawn each WIO as a separate Python subprocess (running `hsb run-next-step --work-item-id LIN-XXX`) in its assigned worktree; gather all subprocesses concurrently; collect results.

**When to use:** Parallel mode dispatch after claiming is complete (D-08).

**Subprocess interface:** Pass WIO input as a JSON tempfile path via env var `HSB_WIO_INPUT_FILE`. WIO reads the JSON, runs its lifecycle, writes output JSON to `HSB_WIO_OUTPUT_FILE`. Both paths provided by Main Orchestrator in the subprocess env. This keeps the Pydantic contract clean without shell argument escaping issues and avoids env var size limits.

**Example:**

```python
# Source: asyncio.create_subprocess_exec docs (Python 3.12 stdlib — VERIFIED)
# asyncio.gather pattern — VERIFIED live in this environment

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

async def _run_wio_subprocess(
    task: dict,
    worktree_path: str,
    repo_root: str,
) -> dict:
    """
    Spawns WIO as subprocess in the given worktree.
    Input/output via temp JSON files (clean Pydantic contract).
    Returns WIO output dict (or error dict on failure).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as input_file:
        json.dump({"work_item_id": task["id"], "linear_state": task}, input_file)
        input_path = input_file.name

    output_path = input_path.replace(".json", "-output.json")

    env = {
        **os.environ,
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
            return {"status": "failed", "task_id": task["id"], "error": stderr.decode()}

        if Path(output_path).exists():
            with open(output_path) as f:
                return json.load(f)
        return {"status": "completed", "task_id": task["id"]}
    finally:
        # Clean up temp files
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)


async def parallel_dispatch(
    claimed_tasks: list[dict],
    worktree_paths: list[str],
    repo_root: str,
) -> list[dict]:
    """
    Fire all WIO subprocesses concurrently.
    return_exceptions=True: one WIO failure does not abort others.
    """
    results = await asyncio.gather(
        *[
            _run_wio_subprocess(task, wt, repo_root)
            for task, wt in zip(claimed_tasks, worktree_paths)
        ],
        return_exceptions=True,
    )
    # Normalize exceptions to error dicts
    return [
        r if isinstance(r, dict) else {"status": "exception", "error": str(r)}
        for r in results
    ]
```

### Pattern 5: Cascade Mode Dispatch (single-task-per-cycle)

**What:** In cascade mode, take only the first ready task from the Global Orchestrator output and run a single WIO cycle sequentially (await before proceeding).

**When to use:** Default mode (D-10). No worktrees, no claiming loop.

**Example:**

```python
# Source: Derived from skills/00-MAIN-ORCHESTRATOR.md §Cascade Mode + CONTEXT.md D-10
# [VERIFIED: skills/00-MAIN-ORCHESTRATOR.md]

async def cascade_dispatch(ready_tasks: list[dict], repo_root: str) -> dict | None:
    """
    Cascade mode: take first task only, run synchronously.
    No claiming (single-process, no contention).
    No worktree (runs in main working tree).
    """
    if not ready_tasks:
        return None
    task = ready_tasks[0]
    result = await _run_wio_subprocess(task, worktree_path=repo_root, repo_root=repo_root)
    return result
```

### Pattern 6: Pydantic Contracts for Phase 4

**What:** One Pydantic model file per orchestrator in `src/hsb/contracts/`, following the established Phase 1–3 pattern.

**When to use:** All Phase 4 data transfer — Global Orchestrator output, Main Orchestrator output, intermediate ClaimResult.

**Example:**

```python
# Source: Derived from agents/AGENT-CONTRACTS.md §0 + Phases 1-3 contract pattern
# [VERIFIED: agents/AGENT-CONTRACTS.md]

# src/hsb/contracts/global_orchestrator.py
from pydantic import BaseModel

class ReadyTask(BaseModel):
    model_config = {"extra": "forbid"}
    id: str
    title: str
    priority: int = 999
    dependencies: list[str] = []

class GlobalOrchestratorOutput(BaseModel):
    model_config = {"extra": "forbid"}
    ready_tasks: list[ReadyTask]
    is_backlog_empty: bool
    is_epic_ready: bool


# src/hsb/contracts/main_orchestrator.py
from pydantic import BaseModel
from typing import Literal

class DispatchedItem(BaseModel):
    model_config = {"extra": "forbid"}
    work_item_id: str
    orchestrator_instance: str
    claim_status: Literal["claimed", "skipped"]
    final_status: Literal["completed", "failed", "blocked"]

class MainOrchestratorOutput(BaseModel):
    model_config = {"extra": "forbid"}
    mode: Literal["cascade", "parallel"]
    dispatched: list[DispatchedItem]
    cycle_summary: str
```

### Pattern 7: `hsb run` CLI Subcommand

**What:** New Typer subcommand added to `src/hsb/cli/main.py` alongside existing commands. Cascade is default; `--parallel` requires explicit opt-in.

**When to use:** Always — this is the locked CLI design (D-10).

**Example:**

```python
# Source: Derived from Phase 3 PATTERNS.md Typer async command handler pattern
# [VERIFIED: .planning/phases/03-work-item-orchestrator-and-single-cycle-mvp/03-PATTERNS.md]

import asyncio
import typer
from hsb.agents.main_orchestrator import run_main_orchestrator

# existing app from Phases 1-3
app = typer.Typer(name="hsb")

@app.command("run")
def run(
    parallel: bool = typer.Option(
        False,
        "--parallel",
        help="Run all ready tasks in parallel with worktree isolation. "
             "Requires Phase 3 cascade cycle to have been validated first.",
    ),
) -> None:
    """Run one orchestration cycle (cascade default, or --parallel for concurrent dispatch)."""
    mode = "parallel" if parallel else "cascade"
    asyncio.run(run_main_orchestrator(mode=mode))
```

### Anti-Patterns to Avoid

- **Claiming in parallel then verifying:** The claiming loop MUST be sequential (D-05). Parallel claiming defeats the `updatedAt` optimistic lock.
- **Using Agent SDK session for Global/Main Orchestrator:** These are pure Python classes. No SDK session, no LLM (D-01, D-02).
- **Passing WIO input as CLI arguments:** Argument length limits and escaping issues. Use JSON tempfile via env var.
- **Skipping worktree cleanup on WIO failure:** Worktrees accumulate and corrupt git state. Cleanup must be in a `finally` block.
- **Creating worktrees in cascade mode:** Cascade runs in the main working tree — worktrees add overhead with no benefit.
- **Raising exception on worktree remove failure:** Cleanup is best-effort; log the failure and continue.
- **Hardcoding `.worktrees/` into git tracking:** Must be gitignored — worktrees are transient runtime artifacts.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async parallel execution | Custom thread pool or asyncio manual task management | `asyncio.gather(*coroutines, return_exceptions=True)` | stdlib, correct semantics, tested pattern from Phase 3 STACK.md |
| Git worktree management | Custom directory copy or symlink scheme | `git worktree add / remove` (built into git 2.43.0+) | First-class git feature; handles object sharing, HEAD tracking, index separation automatically |
| Subprocess IPC | Shared memory, sockets, pipes | JSON tempfile via env var path | Simple, debuggable, matches existing Pydantic contract pattern; no async IPC complexity |
| Optimistic locking | Custom `asyncio.Lock` or file lock | `updatedAt` timestamp comparison after Linear write | Linear is the single source of truth (Runtime Rules #1); in-process locks don't protect against multi-process scenarios |
| Linear state reads | Direct HTTP to Linear API | `linear_agent.py` (Phase 1) | All Linear access must go through OAuth2 MCP layer; no API keys allowed |

**Key insight:** The complexity of parallel dispatch is fully absorbed by `asyncio.gather` + git worktrees. The Main Orchestrator needs no custom concurrency primitives.

---

## Common Pitfalls

### Pitfall A: Parallel Claiming Race (Pitfall 1 from PITFALLS.md)

**What goes wrong:** Two concurrent `hsb run --parallel` processes both read Linear state, both see the same `todo` task, both claim it. One WIO wins; the other implements the same task and creates a duplicate PR.

**Why it happens:** D-05 eliminates this within a single process (claiming is sequential before `asyncio.gather`). It CAN occur if two processes run simultaneously. D-06 (200ms delay) reduces the window but is not a hard guarantee.

**How to avoid:** The optimistic lock (claim, re-read, verify `updatedAt` changed) is the primary guard. If a WIO gets to the worktree stage and finds the task already `in_progress` on re-read, it must abort. Document in `run_loop.py` that two concurrent processes are unsupported (deferred per CONTEXT.md).

**Warning signs:** Two branches with the same `LIN-{id}` prefix in git. Two open PRs targeting the same task.

### Pitfall B: Worktree Branch Already Exists

**What goes wrong:** `git worktree add .worktrees/LIN-{id} feature/LIN-{id}-slug` fails because the branch `feature/LIN-{id}-slug` already exists from a previous (incomplete) run.

**Why it happens:** A previous parallel run created the branch and then crashed before cleaning up the worktree.

**How to avoid:** Before `git worktree add`, check if the branch exists. If it does, either reuse it (if worktree is gone) or fail with a clear error message prompting the operator to run `git worktree prune && git branch -D feature/LIN-{id}-slug`.

**Warning signs:** `git worktree add` exits non-zero with "already exists" message.

### Pitfall C: Stale Worktree After Crash

**What goes wrong:** A WIO subprocess crashes mid-run. The worktree remains in `.worktrees/`. On the next `hsb run --parallel`, `git worktree add` for the same task fails because the path is already registered.

**Why it happens:** The `finally` block in `_run_wio_subprocess` handles cleanup for normal exits. It does not protect against SIGKILL or host-level crash.

**How to avoid:** At startup of `hsb run` (both modes), run `git worktree prune` to remove stale registrations for deleted paths. Add `ls .worktrees/` check and warn if non-empty at startup.

**Warning signs:** `.worktrees/LIN-{id}/` directory present with no running process. `git worktree list` shows worktrees with `prunable` annotation.

### Pitfall D: Linear State Drift Between Claim and Dispatch (Pitfall 4 from PITFALLS.md)

**What goes wrong:** Main Orchestrator claims task, creates worktree, fires subprocess — but between the claim write and when the WIO subprocess reads Linear state, a human (or another agent) changes the task's status. The WIO acts on stale state.

**Why it happens:** Linear reads are point-in-time snapshots. The WIO reads Linear fresh at startup per D-04, but there is still a small window.

**How to avoid:** WIO must re-read `updatedAt` at startup and compare to the value passed in its input contract. If they differ, the WIO should abort with `{"status": "blocked", "reason": "state_drift_detected"}` rather than proceeding on stale state.

**Warning signs:** WIO exits with contradictory state (e.g., task `status` is already `done` when WIO starts).

### Pitfall E: `asyncio.gather` Swallows Exceptions Silently

**What goes wrong:** One WIO subprocess fails. `asyncio.gather` returns the exception object (not a dict). The cycle summary is posted to Linear without recording the failure.

**Why it happens:** `return_exceptions=True` in `asyncio.gather` prevents propagation but requires explicit inspection of results.

**How to avoid:** Always pass `return_exceptions=True`. After `asyncio.gather`, inspect each result: if `isinstance(result, Exception)`, create a `{"status": "exception", "error": str(result)}` dict. Include exception results in the cycle summary posted to Linear.

**Warning signs:** Cycle summary reports N completed tasks but fewer than N worktrees were cleaned up.

---

## Code Examples

### Global Orchestrator — Dependency Filter

```python
# Source: Derived from skills/07-GLOBAL-ORCHESTRATION.md §Task Identification Logic
# [VERIFIED: skills/07-GLOBAL-ORCHESTRATION.md]

def _filter_ready_items(all_items: list[dict]) -> list[dict]:
    """
    GORD-01: Return items with status='todo'
    GORD-02: Exclude items with any unresolved blocked-by dependency
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

### EPIC Completion Check

```python
# Source: Derived from skills/07-GLOBAL-ORCHESTRATION.md §Case 7 + GORD-04
# [VERIFIED: skills/07-GLOBAL-ORCHESTRATION.md]

def _check_epic_complete(all_items: list[dict]) -> bool:
    """
    GORD-04: Signal is_epic_ready when all EPIC children are done + qa_approved.
    """
    children = [i for i in all_items if i.get("type") != "epic"]
    if not children:
        return False
    return all(
        i.get("status") == "done" and i.get("qa_status") in ("approved", "not_required")
        for i in children
    )
```

### Cycle Summary Comment Format

```python
# Source: agents/AGENT-CONTRACTS.md §0 Main Orchestrator output contract
# [VERIFIED: agents/AGENT-CONTRACTS.md]

def _build_cycle_summary(mode: str, dispatched: list[DispatchedItem]) -> str:
    completed = [d for d in dispatched if d.final_status == "completed"]
    failed = [d for d in dispatched if d.final_status in ("failed", "blocked")]
    skipped = [d for d in dispatched if d.claim_status == "skipped"]

    lines = [
        f"## Orchestration Cycle Summary",
        f"**Mode:** {mode}",
        f"**Dispatched:** {len(dispatched)} tasks",
        f"**Completed:** {len(completed)}",
        f"**Failed/Blocked:** {len(failed)}",
        f"**Skipped (claim failed):** {len(skipped)}",
        "",
        "### Details",
    ]
    for d in dispatched:
        status_icon = "✓" if d.final_status == "completed" else "✗"
        lines.append(f"- {status_icon} {d.work_item_id}: {d.claim_status} → {d.final_status}")

    return "\n".join(lines)
```

### run_loop.py Update

```python
# Source: Phase 3 PATTERNS.md §run_loop.py pattern + CONTEXT.md D-12
# [VERIFIED: .planning/phases/03-work-item-orchestrator-and-single-cycle-mvp/03-PATTERNS.md]

# run_loop.py (repo root) — Phase 4 update
import asyncio
import subprocess
import sys

async def has_ready_tasks() -> bool:
    """Call Global Orchestrator directly to check for ready tasks."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    return bool(output.ready_tasks)

def main():
    while True:
        # Run one cycle
        result = subprocess.run(
            ["hsb", "run"],   # Phase 4: call hsb run instead of hsb run-next-step
            check=False,
        )
        if result.returncode != 0:
            print("hsb run failed — stopping loop", file=sys.stderr)
            sys.exit(1)

        # Check if more work remains
        if not asyncio.run(has_ready_tasks()):
            print("No ready tasks remaining. Loop complete.")
            break

if __name__ == "__main__":
    main()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Main Orchestrator as Claude Agent SDK session | Pure Python class (D-02) | Phase 4 CONTEXT.md | Eliminates LLM overhead for deterministic dispatch logic; faster, testable with unit tests |
| Single-process sequential WIO dispatch | `asyncio.gather` subprocess fan-out per task | Phase 4 | Enables true parallel execution with process isolation |
| Shared working tree for all WIOs | Per-task git worktree (`git worktree add`) | Phase 4 | Prevents branch checkout conflicts between concurrent WIOs |
| `hsb run-next-step` as primary entry point | `hsb run` as primary, `run-next-step` retained for debug | Phase 4 | Three-level hierarchy invoked from single command; debug path preserved |

**Deprecated/outdated in this phase:**
- `run_loop.py` calling `hsb run-next-step`: Updated to call `hsb run` in Phase 4. `run-next-step` still works but is no longer the loop entry point.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Linear MCP `get_issue` returns `updatedAt` field in a stable format comparable with `==` after round-tripping through `update_issue` | Pattern 2 (claiming), Pitfall D | Optimistic lock check would always fail or always succeed — claiming verification would be broken. Mitigation: integration test must assert `updatedAt` changes after write. |
| A2 | WIO subprocess can be launched as `python -m hsb.agents.work_item_orchestrator` and reads/writes JSON tempfiles | Pattern 4 | Phase 3 WIO may need a `__main__` entry point added. Must verify WIO has `if __name__ == "__main__"` block or equivalent in Phase 4 Wave 0. |
| A3 | `feature/LIN-{id}-{slug}` branch does not exist at worktree creation time (first-run assumption) | Pattern 3 (worktree) | `git worktree add` will fail. Mitigation: startup check described in Pitfall B. |
| A4 | Linear `list_issues` MCP tool returns `dependencies` as a list of work item IDs (not Linear issue objects) | Pattern 1 (dependency filter) | Filter logic would need adjustment. Mitigation: integration test in Wave 1 must assert field shape. |

---

## Open Questions

1. **WIO subprocess `__main__` entry point**
   - What we know: `work_item_orchestrator.py` from Phase 3 exposes `run_orchestration_cycle(work_item_id)` as a coroutine.
   - What's unclear: Whether Phase 3 added a `if __name__ == "__main__"` block accepting `HSB_WIO_INPUT_FILE` env var. The Phase 3 plan does not mention a CLI-invocable entry point for the WIO module itself.
   - Recommendation: Wave 0 of Phase 4 should add this entry point to `work_item_orchestrator.py` as a minimal modification, or alternatively invoke the WIO via `hsb run-next-step --work-item-id LIN-{id}` subprocess (Typer CLI) in the subprocess dispatch.

2. **Linear priority field shape**
   - What we know: Linear has a `priority` field on issues (0 = no priority, 1 = urgent, 2 = high, 3 = medium, 4 = low per LINEAR docs).
   - What's unclear: Whether `mcp__linear__list_issues` returns this field in its response payload.
   - Recommendation: Verify in Wave 1 integration test. Fallback sort key: `createdAt` ascending (deterministic, always present).

3. **Worktree branch pre-creation**
   - What we know: `git worktree add <path> <branch>` requires the branch to exist or uses `-b <branch>` to create it.
   - What's unclear: The exact branch creation semantics needed — should the WIO subprocess create the branch, or should the Main Orchestrator pre-create it before worktree add?
   - Recommendation: Main Orchestrator pre-creates the branch (`git branch feature/LIN-{id}-{slug}`) before `git worktree add`. This keeps worktree creation atomic and avoids the WIO needing to handle branch creation in a fresh working tree.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All orchestrator code | ✓ | 3.12.3 | — |
| `asyncio.create_subprocess_exec` | WIO subprocess dispatch (MORD-04) | ✓ | stdlib (3.12) | — |
| `asyncio.gather` | Parallel dispatch (MORD-04) | ✓ | stdlib (3.12) | — |
| `git worktree add/remove` | Worktree isolation (MORD-04) | ✓ | git 2.43.0 | — |
| `pydantic` 2.x | Contract validation | ✓ | 2.13.3 (verified Phase 3) | — |
| `typer` | `hsb run` CLI | ✓ | 0.25.1 (verified Phase 3) | — |
| `rich` | `hsb run` output formatting | ✓ | system-wide 13.7.1 (15.0.0 in venv) | — |
| Linear MCP (OAuth2) | All Linear reads/writes | ✓ | Current (verified Phase 1) | — |
| `claude-agent-sdk` | WIO subprocess (Phase 3 code) | installed in venv | 0.1.73 | — |

**Missing dependencies with no fallback:** None — all required dependencies are present.

**Note:** `claude-agent-sdk` is not installed globally but must be installed in the project venv for WIO subprocesses. Subprocesses must be launched with the venv Python, not system Python.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (established Phase 1, pyproject.toml `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` |
| Quick run command | `pytest tests/unit/ -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GORD-01 | Returns only `todo` items sorted by priority | unit | `pytest tests/unit/test_global_orchestrator.py::test_returns_todo_only -x` | ❌ Wave 0 |
| GORD-02 | Excludes items with non-done blocking dependencies | unit | `pytest tests/unit/test_global_orchestrator.py::test_dependency_filter -x` | ❌ Wave 0 |
| GORD-03 | Returns `is_backlog_empty=True` when no items in project | unit | `pytest tests/unit/test_global_orchestrator.py::test_empty_backlog_signal -x` | ❌ Wave 0 |
| GORD-04 | Returns `is_epic_ready=True` when all children done + qa_approved | unit | `pytest tests/unit/test_global_orchestrator.py::test_epic_ready_signal -x` | ❌ Wave 0 |
| MORD-01 | `mode` parameter routes to cascade vs. parallel path | unit | `pytest tests/unit/test_main_orchestrator.py::test_mode_routing -x` | ❌ Wave 0 |
| MORD-02 | Cascade mode dispatches one WIO and awaits before proceeding | unit | `pytest tests/unit/test_main_orchestrator.py::test_cascade_sequential -x` | ❌ Wave 0 |
| MORD-03 | Claiming loop: writes in_progress, re-reads, verifies updatedAt | unit | `pytest tests/unit/test_main_orchestrator.py::test_claiming_optimistic_lock -x` | ❌ Wave 0 |
| MORD-03 (no double-claim) | Two concurrent WIOs targeting same task list — no double-claim | integration | `pytest tests/integration/test_parallel_mode_e2e.py::test_no_double_claim -x` | ❌ Wave 0 |
| MORD-04 | Worktree created before WIO dispatch, removed after | unit | `pytest tests/unit/test_main_orchestrator.py::test_worktree_lifecycle -x` | ❌ Wave 0 |
| MORD-05 | Cycle summary posted to Linear EPIC after all WIOs complete | integration | `pytest tests/integration/test_global_orchestrator_e2e.py::test_cycle_summary_posted -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/ -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_global_orchestrator.py` — covers GORD-01, GORD-02, GORD-03, GORD-04
- [ ] `tests/unit/test_main_orchestrator.py` — covers MORD-01, MORD-02, MORD-03, MORD-04
- [ ] `tests/integration/test_global_orchestrator_e2e.py` — covers GORD-01..04 against real Linear; MORD-05 cycle summary
- [ ] `tests/integration/test_parallel_mode_e2e.py` — covers MORD-03 two-task no-double-claim gate
- [ ] `src/hsb/contracts/global_orchestrator.py` — `GlobalOrchestratorOutput`, `ReadyTask` Pydantic models
- [ ] `src/hsb/contracts/main_orchestrator.py` — `MainOrchestratorOutput`, `DispatchedItem`, `ClaimResult` Pydantic models
- [ ] `.claude/skills/global-orchestration/SKILL.md` — migrated from `skills/07-GLOBAL-ORCHESTRATION.md`
- [ ] `.claude/skills/main-orchestrator/SKILL.md` — migrated from `skills/00-MAIN-ORCHESTRATOR.md`
- [ ] `.worktrees/` added to `.gitignore`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | OAuth2 handled by mcp-remote (Phase 1) |
| V3 Session Management | No | Each subprocess is stateless; session IDs are WIO-internal |
| V4 Access Control | No | No new access control surfaces in Phase 4 |
| V5 Input Validation | Yes | Pydantic models for all orchestrator I/O; subprocess input via JSON tempfile |
| V6 Cryptography | No | No new crypto surfaces |

### Known Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Double-claim / task hijacking | Spoofing | `updatedAt` optimistic lock per D-04; skip on mismatch |
| Subprocess injection via task title in branch slug | Tampering | Sanitize branch slugs (strip shell-special chars, no spaces); use `asyncio.create_subprocess_exec` (not shell=True) |
| Worktree accumulation (denial of disk) | DoS | `finally` cleanup + `git worktree prune` at startup; `.worktrees/` in `.gitignore` |
| Env var leakage to WIO subprocess | Information Disclosure | Pass only required vars (`ANTHROPIC_API_KEY`, `HSB_WIO_INPUT_FILE`, `HSB_WIO_OUTPUT_FILE`); do not pass `**os.environ` wholesale — use allowlist |
| Linear state manipulation via malicious task title | Tampering | WIO input comes from Linear MCP (OAuth2 authenticated); no direct input from user at this layer |

---

## Sources

### Primary (HIGH confidence)
- `agents/AGENT-CONTRACTS.md` — §0 Main Orchestrator contract; all field names and output shape
- `skills/07-GLOBAL-ORCHESTRATION.md` — State evaluation order, task identification logic, delegation map
- `skills/00-MAIN-ORCHESTRATOR.md` — Cascade/parallel modes, claiming workflow, anti-patterns
- `runtime/RUNTIME-EXECUTION.md` — One-action-per-WIO golden rule, parallel mode loop semantics
- `.planning/research/PITFALLS.md` — Pitfall 1 (double-claim), Pitfall 4 (stale state) — directly applicable to Phase 4
- `.planning/research/STACK.md` — Exact library versions, asyncio.gather pattern, Linear MCP tool names
- `.planning/phases/03-work-item-orchestrator-and-single-cycle-mvp/03-RESEARCH.md` — SDK patterns, WIO interface, Pydantic contract shape
- `.planning/phases/03-work-item-orchestrator-and-single-cycle-mvp/03-PATTERNS.md` — Canonical code patterns for WIO, Typer CLI, run_loop.py
- `git worktree` man page (git 2.43.0) — verified `add --detach`, `remove --force` semantics [VERIFIED: live shell test]
- `asyncio.create_subprocess_exec` (Python 3.12 stdlib) — verified subprocess + gather pattern [VERIFIED: live Python test]
- `asyncio.gather` (Python 3.12 stdlib) — verified `return_exceptions=True` semantics [VERIFIED: live Python test]

### Secondary (MEDIUM confidence)
- `agents/AGENTS.md` — agent responsibility boundaries
- `.planning/phases/04-global-main-orchestrators-and-parallel-mode/04-CONTEXT.md` — all locked decisions (D-01 through D-14)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all stack items verified in prior phases
- Architecture (Global Orchestrator): HIGH — pure Python filter/sort; fully deterministic
- Architecture (Main Orchestrator claiming): HIGH — optimistic lock protocol fully specified in CONTEXT.md D-04
- Architecture (subprocess dispatch): HIGH — verified `asyncio.gather` + `asyncio.create_subprocess_exec` live in this environment
- Architecture (worktree isolation): HIGH — verified `git worktree add/remove` live in this repo (git 2.43.0)
- Pitfalls: HIGH — Pitfall 1 and 4 from PITFALLS.md are directly applicable and fully documented
- WIO subprocess interface (JSON tempfile): MEDIUM — pattern is sound but WIO `__main__` entry point must be confirmed/added in Wave 0

**Research date:** 2026-05-06
**Valid until:** 2026-06-05 (30 days — stable stack; only risk is Linear MCP tool shape changes)
