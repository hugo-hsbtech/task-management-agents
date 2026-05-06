"""Thin repo-root wrapper that calls ``hsb run-next-step`` in a loop.

Stops when no todo-status tasks remain or operator presses Ctrl+C
(CLIR-04, D-07). Each iteration is a standalone ``asyncio.run()`` plus
``subprocess.run(["hsb", "run-next-step"])`` — no process-level state
shared between iterations (CLIR-05).

Design note: run_loop.py deliberately invokes the CLI via ``subprocess``
rather than importing :func:`hsb.agents.work_item_orchestrator.run_orchestration_cycle`
directly. The subprocess boundary forces every iteration into a fresh
Python process, which is the strongest possible guarantee of CLIR-05
(no module-level state persists between cycles). Linear is the entire
state store between iterations.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()


async def has_ready_tasks() -> bool:
    """Return ``True`` if Linear has any ``todo``-status tasks ready to drive.

    Uses a minimal Linear MCP call: ``read`` filtered by ``status=todo``.
    The exact filter shape is Claude's discretion (CONTEXT.md) — kept
    intentionally minimal so the loop's termination check is fast.
    """
    # Lazy import to keep CLI startup cost low for the very first iteration.
    from hsb.agents.linear_agent import run_validated_linear_agent

    result = await run_validated_linear_agent(
        operation="read",
        payload={"filter": {"status": {"eq": "todo"}}},
    )
    return len(result.linear_entities) > 0


# Pitfall 5 (RESEARCH.md): stop the loop on any non-zero exit from
# ``hsb run-next-step``. Without this guard, a transient SDK / Linear
# failure could be retried indefinitely with no operator visibility.
def main() -> None:
    """Entry point — drive the cascade loop until Linear is empty or Ctrl+C."""
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
