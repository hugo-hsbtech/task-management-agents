"""run_loop.py — Thin repo-root wrapper that calls ``hsb run`` in a loop.

Stops when no ``ready_tasks`` remain or operator presses Ctrl+C
(CLIR-04, D-12). Phase 4 update (D-12): the loop drives the cycle entry
point and the termination check goes through
:class:`hsb.agents.global_orchestrator.GlobalOrchestrator` instead of
querying Linear directly.

Each iteration is a standalone ``asyncio.run()`` plus
``subprocess.run(["hsb", "run"])`` — no process-level state shared
between iterations (CLIR-05). The subprocess boundary forces every
iteration into a fresh Python process, which is the strongest possible
guarantee of CLIR-05.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()


async def has_ready_tasks() -> bool:
    """Return ``True`` if the Global Orchestrator reports ready tasks remaining.

    Phase 4 update (D-12): delegates the readiness check to
    :class:`GlobalOrchestrator` so the loop's stopping condition is
    sourced from the same code path that powers ``hsb run``.
    """
    # Lazy import to keep CLI startup cost low for the very first iteration.
    from hsb.agents.global_orchestrator import GlobalOrchestrator

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    return bool(output.ready_tasks)


# Pitfall 5 (RESEARCH.md): stop the loop on any non-zero exit from
# ``hsb run``. Without this guard, a transient SDK / Linear failure
# could be retried indefinitely with no operator visibility.
def main() -> None:
    """Entry point — drive the cycle loop until no ready tasks remain or Ctrl+C."""
    print("Starting HSBTech run loop. Press Ctrl+C to stop.")
    try:
        while True:
            # Phase 4 update (D-12): drive the cycle entry point.
            # argv form (no shell expansion) — defense in depth (T-4-02).
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
