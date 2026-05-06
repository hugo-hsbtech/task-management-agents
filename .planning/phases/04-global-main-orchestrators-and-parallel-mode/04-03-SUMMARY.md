---
phase: 04-global-main-orchestrators-and-parallel-mode
plan: 03
status: complete
completed: 2026-05-06
requirements:
  - MORD-01
  - MORD-02
  - MORD-03
  - MORD-04
  - MORD-05
key-files:
  created:
    - src/hsb/agents/main_orchestrator.py
  modified:
    - tests/unit/test_main_orchestrator.py
---

# Plan 04-03 Summary: Main Orchestrator Implementation

## What Was Built

Pure Python `main_orchestrator.py` module (D-02) at
`src/hsb/agents/main_orchestrator.py`. No Claude Agent SDK session, no LLM,
no skill injection. All concurrency primitives live here:
`asyncio.create_subprocess_exec` (git worktree CLI + WIO subprocess) and
`asyncio.gather(return_exceptions=True)` (parallel WIO fan-out).

### Module Surface

| Function | Purpose | Requirement |
|---------|---------|-------------|
| `run_main_orchestrator(mode)` | Top-level entrypoint, mode router, posts cycle summary | MORD-01, MORD-05, D-14 |
| `_cascade_dispatch` | Take first ready task, run synchronously in main worktree | MORD-02 |
| `_sequential_claiming_loop` | Optimistic-lock claiming over Linear (read → write → re-read → diff) | MORD-03, D-04, D-05, D-06 |
| `_git_worktree_add` | Create per-task worktree on slug-sanitized branch | MORD-04, D-07 |
| `_git_worktree_remove` | Best-effort cleanup with `--force`; logs but does not raise | D-09 |
| `_run_wio_subprocess` | Spawn Phase 3 WIO via JSON tempfile IPC, strict env allowlist | D-08, T-4-04 |
| `_parallel_dispatch` | Prune → claim → worktree → asyncio.gather → finally cleanup | MORD-04, D-08, D-09 |
| `_build_cycle_summary` | Plain-string Linear comment formatter | MORD-05, D-14 |

### Architectural Properties (enforced by source-grep tests)

- **D-02:** No `claude_agent_sdk` / `ClaudeAgentOptions` / `query(` /
  `create_sdk_mcp_server` references.
- **T-4-04:** No `**os.environ` anywhere — subprocess env is a strict 5-key
  allowlist (`PATH`, `HOME`, `ANTHROPIC_API_KEY`, `HSB_WIO_INPUT_FILE`,
  `HSB_WIO_OUTPUT_FILE`).
- **T-4-02:** No `shell=True` anywhere; branch slugs sanitized via
  `re.sub(r"[^a-z0-9-]", "-", task.title.lower())[:30].strip("-")`.
- **Pitfall E:** `asyncio.gather(..., return_exceptions=True)` everywhere;
  exceptions normalized to `{"status": "exception", "error": str(r)}` dicts.
- **D-09:** Worktree cleanup wrapped in `try/finally` — guarantees removal
  even if `gather` itself escapes (defense in depth, since `return_exceptions=True`
  already prevents propagation).
- **Pitfall C:** `git worktree prune` runs at startup of every parallel cycle.

### Optimistic Lock (MORD-03 / D-04)

Sequential per-task protocol:
1. Read pre-write `updatedAt` via `run_validated_linear_agent(operation="read", ...)`.
2. Write `status="in_progress"` via `run_validated_linear_agent(operation="update", ...)`.
3. Re-read post-write `updatedAt`.
4. If timestamps differ → claim succeeded; else → log warning and skip task.
5. `await asyncio.sleep(CLAIM_DELAY_MS / 1000)` (default 200ms per D-06).

A defensive `_entity_get(...)` helper tolerates both Pydantic instances and
plain dicts in `linear_entities`, since the Phase 1 `LinearEntity` shape
exposes only `id`/`type`/`url` and live Linear MCP responses may carry
additional fields as raw dicts.

## Verification Run

```
pytest tests/unit/test_main_orchestrator.py -v
10 passed in 0.71s

pytest tests/unit/test_global_orchestrator.py tests/unit/test_main_orchestrator.py -v
16 passed
```

```
python -c "import inspect; import hsb.agents.main_orchestrator as m; ..."
OK: main_orchestrator.py D-02 + T-4-04 + Pitfall E enforced
```

## Tasks Completed

- Task 1: Implement `main_orchestrator.py` with 8 functions (entrypoint, 2
  dispatch helpers, claiming loop, 2 worktree helpers, WIO subprocess
  spawner, summary builder)
- Task 2: Replace 8 Wave 0 stubs in `tests/unit/test_main_orchestrator.py`
  (MORD-01..04 + alias + D-01/D-02 with extended T-4-04/T-4-02 grep)

## Self-Check

- [x] All 8 expected functions present
- [x] D-02 enforced: no `claude_agent_sdk` / `ClaudeAgentOptions`
- [x] T-4-04 enforced: no literal `**os.environ` in source
- [x] T-4-02 enforced: no `shell=True`; slug regex present
- [x] Pitfall E: `asyncio.gather(..., return_exceptions=True)`
- [x] D-09: `_git_worktree_remove` called for every claimed task in `try/finally`
- [x] D-04 optimistic lock comparison: `post_updated_at != pre_updated_at`
- [x] D-06 inter-claim sleep: `await asyncio.sleep(delay_ms / 1000)`
- [x] MORD-05: `operation="comment"` posted via Linear Agent
- [x] All 10 unit tests in `tests/unit/test_main_orchestrator.py` pass
- [x] All 6 unit tests in `tests/unit/test_global_orchestrator.py` still pass
- [x] No `Wave 0 stub` markers remain in either unit test file

## Self-Check: PASSED

## What This Enables

- **Plan 04:** CLI integration plus operator MVP test can wire `hsb run` to
  call `run_main_orchestrator(mode=...)`. The two-task no-double-claim live
  test simply needs the operator to seed two ready tasks in the Linear test
  workspace and run `hsb run --parallel` — the entire dispatch path is
  exercised against real Linear.
- **Phase 5:** Intelligence Agent integration can resolve the
  `CURRENT_EPIC_ID` placeholder in `run_main_orchestrator` so the cycle
  summary lands on the correct EPIC.

## Notes for Operator (Plan 04 Live Test)

The `_run_wio_subprocess` implementation requires the Phase 3 WIO module to
be invocable as `python -m hsb.agents.work_item_orchestrator` AND to read
input from the `HSB_WIO_INPUT_FILE` env var / write output to
`HSB_WIO_OUTPUT_FILE`. If the Phase 3 module lacks an `if __name__ ==
"__main__"` guard or these env-var conventions, Plan 04 must add them
before the live two-task test runs (see 04-RESEARCH.md Open Question 1).
