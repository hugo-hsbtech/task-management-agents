"""Main Orchestrator — Phase 4 Plan 03.

Pure Python dispatch controller (D-02): no Claude Agent SDK session, no LLM,
no skill injection. Calls Global Orchestrator, routes between cascade and
parallel modes, performs sequential optimistic-lock claiming for parallel
mode, manages per-task git worktrees, fans out WIO subprocesses via
asyncio.gather, and posts a structured cycle summary to Linear.

Implements MORD-01 (mode routing), MORD-02 (cascade sequential), MORD-03
(optimistic-lock claiming), MORD-04 (worktree-isolated parallel dispatch),
and MORD-05 (cycle summary persistence to Linear).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

from hsb.agents.global_orchestrator import GlobalOrchestrator
from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.contracts.main_orchestrator import (
    DispatchedItem,
)
from settings import settings

load_dotenv()

logger = logging.getLogger(__name__)

WORKTREES_DIR = ".worktrees"
CLAIM_DELAY_MS = settings.orchestrator.claim_delay_ms


def _entity_get(entity: Any, key: str, default: Any = None) -> Any:
    """Defensive accessor — entities may be Pydantic instances or plain dicts."""
    if hasattr(entity, "get") and callable(entity.get):
        return entity.get(key, default)
    if hasattr(entity, "model_dump"):
        return entity.model_dump().get(key, default)
    return getattr(entity, key, default)


async def run_main_orchestrator(
    mode: Literal["cascade", "parallel"] = "cascade",
) -> None:
    """
    Main Orchestrator entrypoint (MORD-01, MORD-05, D-02, D-14).

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

    # MORD-05 + D-14: Post cycle summary to Linear EPIC.
    # TODO(Phase 5): Resolve "CURRENT_EPIC_ID" via Intelligence Agent integration
    # or env-var injection. Phase 4 leaves this as a documented placeholder so the
    # write path is exercised end-to-end without coupling to per-EPIC scoping.
    summary = _build_cycle_summary(mode, dispatched)
    await run_validated_linear_agent(
        operation="comment",
        payload={"epicId": "CURRENT_EPIC_ID", "body": summary},
    )


async def _cascade_dispatch(
    ready_tasks: list[Any],
    repo_root: str,
) -> list[DispatchedItem]:
    """
    Cascade mode (MORD-02, D-10/D-11): take first task only, run synchronously
    in main working tree.

    No claiming (single-process cascade has no contention).
    No worktree (runs in main working tree — preserves Phase 3 behavior).
    """
    if not ready_tasks:
        return []
    task = ready_tasks[0]
    result = await _run_wio_subprocess(task, worktree_path=repo_root)
    return [
        DispatchedItem(
            work_item_id=task.id,
            orchestrator_instance="cascade-0",
            claim_status="claimed",
            final_status=result.get("status", "completed"),
        )
    ]


async def _sequential_claiming_loop(
    ready_tasks: list[Any],
    delay_ms: int = CLAIM_DELAY_MS,
) -> list[tuple[Any, str]]:
    """
    MORD-03 + D-04 + D-05 + D-06: sequential claiming loop with optimistic lock.

    For each task:
      1. Capture pre-write updatedAt (read).
      2. Write status=in_progress (update).
      3. Re-read; if updatedAt changed, claim succeeded; else skip.
      4. Sleep CLAIM_DELAY_MS to reduce inter-claim collision window.

    Returns list of (task, post_updated_at) tuples for successfully claimed tasks.
    """
    claimed: list[tuple[Any, str]] = []
    for task in ready_tasks:
        # Step 1: Capture pre-write updatedAt
        fresh_before = await run_validated_linear_agent(
            operation="read",
            payload={"issueId": task.id},
        )
        pre_updated_at = ""
        if fresh_before.linear_entities:
            pre_updated_at = _entity_get(
                fresh_before.linear_entities[0], "updatedAt", ""
            )

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
        post_updated_at = ""
        if fresh_after.linear_entities:
            post_updated_at = _entity_get(
                fresh_after.linear_entities[0], "updatedAt", ""
            )

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


async def _git_worktree_add(repo_root: str, task_id: str, branch_name: str) -> str:
    """
    MORD-04: create .worktrees/LIN-{task_id}/ as a linked worktree on branch_name.

    Uses git's `-b` flag to create the branch if it does not yet exist (delegates
    branch pre-creation to git per 04-RESEARCH.md Open Question 3). Returns the
    absolute worktree path.
    """
    wt_path = os.path.join(repo_root, WORKTREES_DIR, f"LIN-{task_id}")
    proc = await asyncio.create_subprocess_exec(
        "git",
        "worktree",
        "add",
        "-b",
        branch_name,
        wt_path,
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
    D-09: remove .worktrees/LIN-{task_id}/ worktree, best-effort cleanup.

    Uses --force — cleanup must always succeed. Do NOT raise on failure; log
    and continue. Anti-pattern: raising on cleanup failure aborts the cleanup
    loop and leaves stale worktrees behind.
    """
    wt_path = os.path.join(repo_root, WORKTREES_DIR, f"LIN-{task_id}")
    proc = await asyncio.create_subprocess_exec(
        "git",
        "worktree",
        "remove",
        "--force",
        wt_path,
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


async def _run_wio_subprocess(task: Any, worktree_path: str) -> dict[str, Any]:
    """
    Spawns the Phase 3 Work Item Orchestrator as a subprocess in the given worktree.

    Input/output via JSON tempfiles (clean Pydantic contract, no shell arg
    escaping). Returns WIO output dict or error dict on failure (never raises;
    asyncio.gather handles errors).

    Security: env is a strict allowlist (T-4-04 — never pass the full os.environ wholesale).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as input_file:
        json.dump({"work_item_id": task.id}, input_file)
        input_path = input_file.name

    output_path = input_path.replace(".json", "-output.json")

    # T-4-04: strict env allowlist — NEVER pass the full os.environ wholesale.
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "HSB_WIO_INPUT_FILE": input_path,
        "HSB_WIO_OUTPUT_FILE": output_path,
    }

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "hsb.agents.work_item_orchestrator",
            cwd=worktree_path,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(
                "WIO subprocess failed for %s (exit %d): %s",
                task.id,
                proc.returncode,
                stderr.decode(),
            )
            return {"status": "failed", "task_id": task.id, "error": stderr.decode()}

        if Path(output_path).exists():
            with open(output_path) as f:
                result: dict[str, Any] = json.load(f)
                return result
        return {"status": "completed", "task_id": task.id}
    finally:
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)


async def _parallel_dispatch(
    ready_tasks: list[Any],
    repo_root: str,
) -> list[DispatchedItem]:
    """
    Parallel mode dispatch (MORD-04, D-04..D-09).

    Phase 0 (Pitfall C): prune stale worktrees from prior crashed runs.
    Phase 1: sequential claiming loop (D-04, D-05).
    Phase 2: create per-task worktrees (slug-sanitized branches per T-4-02).
    Phase 3: asyncio.gather all WIO subprocesses (D-08; return_exceptions=True
             per Pitfall E so one failure does not abort the others).
    Phase 4: cleanup worktrees in finally — runs regardless of WIO outcome (D-09).
    """
    # Pitfall C mitigation: prune stale worktrees before any new ones are created
    prune_proc = await asyncio.create_subprocess_exec(
        "git",
        "worktree",
        "prune",
        cwd=repo_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await prune_proc.communicate()

    # Phase 1: Sequential claiming
    claimed_pairs = await _sequential_claiming_loop(ready_tasks)

    dispatched_items: list[DispatchedItem] = []
    skipped_ids = {t.id for t in ready_tasks} - {t.id for t, _ in claimed_pairs}

    for skipped_id in skipped_ids:
        dispatched_items.append(
            DispatchedItem(
                work_item_id=skipped_id,
                orchestrator_instance="skipped",
                claim_status="skipped",
                final_status="blocked",
            )
        )

    if not claimed_pairs:
        return dispatched_items

    # Phase 2: Create worktrees with slug-sanitized branch names (T-4-02)
    worktree_paths: list[str] = []
    for task, _ in claimed_pairs:
        slug = re.sub(r"[^a-z0-9-]", "-", task.title.lower())[:30].strip("-")
        branch = f"feature/LIN-{task.id}-{slug}"
        wt_path = await _git_worktree_add(repo_root, task.id, branch)
        worktree_paths.append(wt_path)

    normalized: list[dict[str, Any]] = []
    try:
        # Phase 3: asyncio.gather — return_exceptions=True per Pitfall E.
        # One WIO failure does not abort the others; exceptions are normalized below.
        results = await asyncio.gather(
            *[
                _run_wio_subprocess(task, wt)
                for (task, _), wt in zip(claimed_pairs, worktree_paths, strict=False)
            ],
            return_exceptions=True,
        )

        # Pitfall E: normalize exceptions to error dicts so downstream code
        # never sees a raw Exception instance.
        normalized = [
            r if isinstance(r, dict) else {"status": "exception", "error": str(r)}
            for r in results
        ]
    finally:
        # Phase 4 (D-09): cleanup worktrees — ALWAYS runs, even on cancellation
        # or unexpected exception escape from gather.
        for task, _ in claimed_pairs:
            await _git_worktree_remove(repo_root, task.id)

    # Build dispatched items from normalized results
    for i, ((task, _), result) in enumerate(
        zip(claimed_pairs, normalized, strict=False)
    ):
        final_status = (
            result.get("status", "completed") if isinstance(result, dict) else "failed"
        )
        dispatched_items.append(
            DispatchedItem(
                work_item_id=task.id,
                orchestrator_instance=f"parallel-{i}",
                claim_status="claimed",
                final_status=final_status,
            )
        )

    return dispatched_items


def _build_cycle_summary(mode: str, dispatched: list[DispatchedItem]) -> str:
    """MORD-05: build cycle summary string for Linear EPIC comment (D-14)."""
    completed = [d for d in dispatched if d.final_status == "completed"]
    failed = [
        d for d in dispatched if d.final_status in ("failed", "blocked", "exception")
    ]
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
        icon = "OK" if d.final_status == "completed" else "FAIL"
        lines.append(
            f"- [{icon}] {d.work_item_id}: {d.claim_status} -> {d.final_status}"
        )

    return "\n".join(lines)
