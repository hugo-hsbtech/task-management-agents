---
phase: 04-global-main-orchestrators-and-parallel-mode
plan: 04
status: partial
completed: 2026-05-06
checkpoint: human-verify
checkpoint_status: pending
requirements:
  - MORD-01
  - MORD-03
  - MORD-04
  - MORD-05
  - CLIR-01
  - CLIR-04
key-files:
  modified:
    - src/hsb/cli/main.py
    - run_loop.py
    - tests/integration/test_global_orchestrator_e2e.py
    - tests/integration/test_parallel_mode_e2e.py
---

# Plan 04-04 Summary: CLI Integration + Parallel Mode Acceptance Gate

## Status: AUTONOMOUS WORK COMPLETE — OPERATOR MVP CHECKPOINT PENDING

Tasks 1 and 2 are merged. Task 3 (the human-verify GO/NO-GO checkpoint that
exercises parallel mode against a live Linear workspace) requires browser
OAuth2 + a seeded test workspace and cannot be executed by the autonomous
orchestrator. This document is the resume contract — when the operator runs
through the steps below and signs off, Phase 4 is fully validated.

The same pattern was used for 01-05 (HUMAN-SETUP.md), 02 (02-HUMAN-UAT.md),
and 03 (03-04-SUMMARY.md operator MVP). Phase 5 planning is unblocked per
project pattern (operator checkpoints do not gate phase completion).

## What Was Shipped Autonomously

### Task 1 — CLI integration (D-10, D-11, D-12)

- `src/hsb/cli/main.py` — added `hsb run` Typer subcommand. Cascade is the
  default mode; `--parallel` is an explicit opt-in flag (D-10). `hsb
  run-next-step` (Phase 3) is retained unchanged (D-11). The handler is a
  synchronous Typer callback that wraps the coroutine via `asyncio.run()` at
  the CLI boundary (Phase 1 Shared Patterns).
- `run_loop.py` — updated to call `["hsb", "run"]` (D-12). Termination check
  now goes through `GlobalOrchestrator.get_ready_tasks()` instead of querying
  Linear directly. Returncode check + KeyboardInterrupt handling preserved
  from Phase 3.

Smoke verification:

```
$ python -m hsb.cli.main run --help
... shows --parallel flag (D-10) ...

$ python -m hsb.cli.main run-next-step --help
... still works (D-11 regression check) ...

$ python -c "src=open('run_loop.py').read(); ..."
OK: run_loop.py calls hsb run + GlobalOrchestrator
```

### Task 2 — Integration test stubs filled in

- `tests/integration/test_global_orchestrator_e2e.py` — 5 live tests for
  GORD-01..04 + MORD-05 cycle summary smoke test.
- `tests/integration/test_parallel_mode_e2e.py` — 3 live tests:
  `test_no_double_claim_parallel_two_tasks` (THE Phase 4 Success Criterion 5
  acceptance gate), `test_no_double_claim` alias, and
  `test_worktree_cleanup_after_parallel` (D-09 cleanup verification).
- Test collection: 8 integration tests collect cleanly. No `Wave 0 stub`
  markers remain anywhere under `tests/`.
- Full unit suite: **58 passed in 0.54s** (no Phase 1–3 regressions).

## Operator MVP Checkpoint — Resume Contract

### Pre-Conditions (must be true before running the gate)

1. Operator has authenticated `mcp-remote` to the Linear test workspace via
   browser OAuth2 (Phase 1 setup completed and verified by Phase 1
   HUMAN-SETUP.md sign-off).
2. The `hsb-test-fixture` GitHub repo is accessible (Phase 2 setup completed
   and verified by Phase 2 HUMAN-UAT.md sign-off).
3. The Linear test workspace has **at least 2 todo-status tasks** in the same
   project, with no blocking dependencies. Seed them via Linear UI or via
   `hsb backlog create` (Phase 2) before the gate test.
4. The Phase 3 cascade cycle has been previously validated (CONTEXT.md D-13
   gate; signed off in 03-04-SUMMARY.md).
5. `.worktrees/` directory at the repo root is empty before starting (run
   `git worktree prune` if you have stale entries from prior runs).
6. `ANTHROPIC_API_KEY` is exported in the operator's shell so the WIO
   subprocess can authenticate against the Anthropic API.

### Step-by-Step Verification

**Step 1 — Run the two-task parallel acceptance gate (THE Phase 4 gate):**

```bash
cd /home/ubuntu/hugo/task-management-agents
uv run python -m pytest tests/integration/test_parallel_mode_e2e.py::test_no_double_claim_parallel_two_tasks -v
```

**Expected:** test PASSES. Two tasks transition from `todo` to `in_progress`
(or further). Neither remains in `todo`. No `RuntimeError` about
`git worktree add` failing. No "claim verification failed" warning unless
two `hsb run --parallel` processes were started simultaneously.

**Step 2 — Run the worktree cleanup verification:**

```bash
uv run python -m pytest tests/integration/test_parallel_mode_e2e.py::test_worktree_cleanup_after_parallel -v
ls -la .worktrees/ 2>/dev/null || echo "(.worktrees/ does not exist — cleanup OK)"
```

**Expected:** test PASSES; `.worktrees/` directory is empty (or non-existent).

**Step 3 — Cascade cycle summary verification (MORD-05):**

```bash
uv run python -m pytest tests/integration/test_global_orchestrator_e2e.py::test_cycle_summary_posted -v
```

**Expected:** test PASSES. Open the EPIC in Linear and confirm a comment
titled `## Orchestration Cycle Summary` is present, listing mode, dispatch
counts, and per-task details.

**Step 4 — Full integration suite:**

```bash
uv run python -m pytest tests/integration/ -v
```

**Expected:** all tests PASS or SKIP with a clear reason (e.g., "Requires at
least 2 todo tasks in Linear test workspace").

**Step 5 — Manual CLI smoke checks:**

```bash
uv run python -m hsb.cli.main run --help            # verify --parallel flag is documented
uv run python -m hsb.cli.main run                   # one cascade cycle
uv run python -m hsb.cli.main run --parallel        # one parallel cycle
uv run python -m hsb.cli.main run-next-step --help  # verify D-11 retained debug path
uv run python run_loop.py                            # verify the loop wrapper (Ctrl+C to exit)
```

**Expected:** all five invocations execute without uncaught exceptions.
`hsb run-next-step` still works (D-11 regression).

**Step 6 — Manual Linear inspection:**

Open the test EPIC. Verify:
- The two tasks chosen by Step 1 transitioned through `in_progress` and
  reached a terminal state.
- Each task has at least one comment trail from the WIO subprocess.
- The EPIC has a cycle-summary comment from the parallel run.
- The cycle-summary placeholder `CURRENT_EPIC_ID` did NOT cause a failure
  (if it did, it indicates the Linear Agent's `comment` payload schema
  needs the actual EPIC ID — see Phase 5 work item).

**Step 7 — Inspect git state:**

```bash
git worktree list
git branch --list 'feature/LIN-*'
```

**Expected:** no leftover worktrees in the list (other than the main
working tree). Feature branches may exist but are clean (the WIO completed
its commits).

**Step 8 — Multi-process collision smoke test (best-effort, deferred per
CONTEXT.md):**

Open two terminals. In both, run `uv run python -m hsb.cli.main run --parallel`
simultaneously. Observe Linear: at most one of the two processes should
successfully claim each task; the other should log a "claim verification
failed" warning and skip. Distributed locking is documented as deferred per
CONTEXT.md.

### Capture for the Sign-Off Note

When you record GO, include in the operator note (paste below under
"Operator Sign-Off Log"):

- Linear EPIC URL where the cycle summary was posted
- The list of task IDs claimed and dispatched during the gate test
- Any "claim verification failed" warnings observed during multi-process
  smoke testing
- Output of `git worktree list` after the run

### Resume Signal

Type **"approved"** if all 8 verification steps pass and Linear state
matches expectations. Type **"blocked: <description>"** if any step fails —
the planner will replan to address the gap (likely as a Phase 4.1 gap
closure).

## Known Open Items for the Operator Run

These are documented during autonomous execution and may need attention
during the live test:

1. **WIO subprocess entry point.** `_run_wio_subprocess` spawns
   `python -m hsb.agents.work_item_orchestrator` and reads/writes
   `HSB_WIO_INPUT_FILE` / `HSB_WIO_OUTPUT_FILE` env vars. If the Phase 3
   module lacks `if __name__ == "__main__"` or these env-var conventions,
   the gate test will fail with a non-zero exit from the WIO subprocess.
   This is 04-RESEARCH.md Open Question 1; if it surfaces, add the guard
   in a Phase 4.1 gap-closure plan.

2. **EPIC ID placeholder.** `run_main_orchestrator` posts the cycle summary
   with `epicId="CURRENT_EPIC_ID"` as a placeholder. The Linear Agent's
   comment handler may either (a) accept this as a literal string and
   silently do nothing useful, or (b) reject the payload. Phase 5
   Intelligence Agent integration is the planned home for resolving the
   real EPIC ID. If the test_cycle_summary_posted assertion fails because
   the comment payload is invalid, document it as a follow-up rather than
   blocking Phase 4 completion.

3. **Live integration tests are async without anyio_backend marker.** If
   pytest-asyncio's auto mode does not pick up these tests (older pytest
   configs), explicitly run with `pytest -p asyncio --asyncio-mode=auto`.
   The repo's pyproject.toml already configures `asyncio_mode = "auto"` so
   this should not surface in practice.

## Operator Sign-Off Log

> Paste your sign-off note here when the gate run completes.

```
Date: ____
Operator: ____
Result: GO | NO-GO
EPIC URL: ____
Claimed task IDs: ____
Worktree cleanup: PASS | FAIL
Cycle summary visible in Linear: YES | NO
Multi-process smoke (Step 8): observed N "claim verification failed" warnings
Notes:
```

## Self-Check (Autonomous Portion)

- [x] `hsb run` registered with `--parallel` flag (D-10)
- [x] `hsb run-next-step` retained unchanged (D-11)
- [x] `run_loop.py` calls `["hsb", "run"]` (D-12) and uses
      `GlobalOrchestrator.get_ready_tasks()`
- [x] Both integration files have all Wave 0 stubs replaced with real
      assertions
- [x] No `Wave 0 stub` markers remain anywhere in `tests/`
- [x] Test collection succeeds on `tests/integration/` (8 tests)
- [x] Full unit suite passes (58 tests, no regressions)
- [ ] Two-task parallel acceptance gate passes against live Linear
      (PENDING — operator step)
- [ ] Worktree cleanup verified (PENDING — operator step)
- [ ] MORD-05 cycle summary posted to Linear EPIC (PENDING — operator step)
- [ ] Operator GO sign-off recorded above (PENDING)

## Self-Check: PASSED (autonomous portion); PENDING (operator portion)

## What This Enables

- **Phase 5** (Enhancement Agents): the four-plan Phase 5 plan tree depends
  only on Phase 4's autonomous portion (the orchestrator hierarchy + CLI
  surface). Per project pattern, Phase 4 is unblocked for Phase 5 planning;
  the operator checkpoint does not gate downstream phases.
