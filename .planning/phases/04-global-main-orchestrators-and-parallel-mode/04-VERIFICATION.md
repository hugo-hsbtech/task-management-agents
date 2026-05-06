---
phase: 04-global-main-orchestrators-and-parallel-mode
status: human_needed
verified: 2026-05-06
must_haves_total: 9
must_haves_verified_automated: 7
must_haves_pending_human: 2
---

# Phase 4 Verification Report

**Phase goal (from ROADMAP.md):** The full three-level orchestration hierarchy
works in cascade mode, then parallel mode with optimistic claiming and
worktree isolation passes a two-task concurrent test.

**Result:** All 4 plans merged, 13 commits, 0 regressions. Automated
must-haves all verified. Two must-haves require operator MVP checkpoint
(Plan 04-04 Task 3) — same pattern as Phase 1 (01-05) and Phase 3 (03-04).

## Requirement Coverage

| Req | Verified by | Status |
|-----|-------------|--------|
| GORD-01 | `tests/unit/test_global_orchestrator.py::test_returns_todo_only` (PASS) + live stub | automated PASS |
| GORD-02 | `test_dependency_filter` (PASS) + live stub | automated PASS |
| GORD-03 | `test_empty_backlog_signal` (PASS) + live stub | automated PASS |
| GORD-04 | `test_epic_ready_signal` (PASS) + live stub | automated PASS |
| MORD-01 | `test_mode_routing_cascade` + `test_mode_routing_parallel` (PASS) | automated PASS |
| MORD-02 | `test_cascade_sequential` (PASS) | automated PASS |
| MORD-03 | `test_claiming_optimistic_lock` (PASS) — UNIT only; live two-task gate pending operator | partial (operator) |
| MORD-04 | `test_worktree_lifecycle` source-grep (PASS) — UNIT only; live worktree creation pending operator | partial (operator) |
| MORD-05 | Cycle summary written into `_build_cycle_summary` + post path in `run_main_orchestrator` (PASS construction); live posting pending operator | automated PASS / live pending |

## Test Suite Status

```
pytest tests/unit/ -q
58 passed in 0.55s

pytest tests/ --collect-only -q
136 tests collected (58 unit + 78 integration/contract)
```

All Phase 1, 2, 3, and 4 unit tests pass — no cross-phase regressions
introduced.

## Architectural Properties (Source-Grep Verified)

- **D-01:** `GlobalOrchestrator` source contains no `claude_agent_sdk` /
  `ClaudeAgentOptions`. Asserted by
  `test_no_sdk_session_in_global_orchestrator` (PASS).
- **D-02:** `main_orchestrator.py` source contains no `claude_agent_sdk` /
  `ClaudeAgentOptions` / `query(` / `create_sdk_mcp_server`. Asserted by
  `test_no_sdk_session_in_main_orchestrator` (PASS).
- **T-4-04:** No literal `**os.environ` in `main_orchestrator.py`.
  Asserted by `test_no_sdk_session_in_main_orchestrator` (PASS). Subprocess
  env is a strict 5-key allowlist.
- **T-4-02:** No `shell=True` anywhere in Phase 4 sources. Branch slugs
  sanitized via `re.sub(r"[^a-z0-9-]", "-", task.title.lower())[:30]`.
- **Pitfall E:** `asyncio.gather(..., return_exceptions=True)` confirmed in
  `_parallel_dispatch`. Exception normalization to dict shape present.
- **D-09:** Worktree cleanup in `try/finally` in `_parallel_dispatch`.
  Asserted by `test_worktree_lifecycle` source-grep (PASS).
- **Pitfall C:** `git worktree prune` runs at the start of every
  `_parallel_dispatch`.

## Human Verification Required

The following items need a live operator run with the two-task seeded
Linear test workspace. Documented in
`.planning/phases/04-global-main-orchestrators-and-parallel-mode/04-04-SUMMARY.md`
"Operator MVP Checkpoint — Resume Contract" (8 verification steps):

1. **Two-task parallel acceptance gate (Phase 4 Success Criterion 5)** —
   `pytest tests/integration/test_parallel_mode_e2e.py::test_no_double_claim_parallel_two_tasks -v`
   passes against the live Linear test workspace.

2. **Worktree cleanup** —
   `pytest tests/integration/test_parallel_mode_e2e.py::test_worktree_cleanup_after_parallel -v`
   passes; `.worktrees/` directory empty after the run.

3. **MORD-05 cycle summary posted to Linear** —
   `pytest tests/integration/test_global_orchestrator_e2e.py::test_cycle_summary_posted -v`
   passes AND visual confirmation of the cycle-summary comment landing on
   the EPIC.

4. **CLI smoke** — `hsb run`, `hsb run --parallel`, `hsb run-next-step`
   (D-11 retained), and `python run_loop.py` execute without uncaught
   exceptions.

## Sign-Off Path

Operator runs the 8-step verification contract in 04-04-SUMMARY.md and
records GO or NO-GO in the same document. Until then, Phase 4 is
"complete except for operator MVP checkpoint" (same pattern as Phases 1
and 3). Phase 5 planning is unblocked per project convention.
