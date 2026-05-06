---
phase: 4
slug: global-main-orchestrators-and-parallel-mode
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (established Phase 1, `pyproject.toml` `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/unit/ -x` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (unit); ~120 seconds (full with integration) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/ -x`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (unit), 120 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 0 | GORD-01 | — | N/A | unit | `pytest tests/unit/test_global_orchestrator.py::test_returns_todo_only -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 0 | GORD-02 | — | N/A | unit | `pytest tests/unit/test_global_orchestrator.py::test_dependency_filter -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 0 | GORD-03 | — | N/A | unit | `pytest tests/unit/test_global_orchestrator.py::test_empty_backlog_signal -x` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 0 | GORD-04 | — | N/A | unit | `pytest tests/unit/test_global_orchestrator.py::test_epic_ready_signal -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | MORD-01 | — | N/A | unit | `pytest tests/unit/test_main_orchestrator.py::test_mode_routing -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | MORD-02 | — | N/A | unit | `pytest tests/unit/test_main_orchestrator.py::test_cascade_sequential -x` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 1 | MORD-03 | T-4-01 | Skip task if updatedAt mismatch detected on re-read | unit | `pytest tests/unit/test_main_orchestrator.py::test_claiming_optimistic_lock -x` | ❌ W0 | ⬜ pending |
| 04-02-04 | 02 | 1 | MORD-04 | T-4-03 | Worktree created/removed in finally block; prune at startup | unit | `pytest tests/unit/test_main_orchestrator.py::test_worktree_lifecycle -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | MORD-03 | T-4-01 | No double-claim in two-task concurrent run | integration | `pytest tests/integration/test_parallel_mode_e2e.py::test_no_double_claim -x` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 2 | MORD-05 | — | N/A | integration | `pytest tests/integration/test_global_orchestrator_e2e.py::test_cycle_summary_posted -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_global_orchestrator.py` — stubs for GORD-01, GORD-02, GORD-03, GORD-04
- [ ] `tests/unit/test_main_orchestrator.py` — stubs for MORD-01, MORD-02, MORD-03, MORD-04
- [ ] `tests/integration/test_global_orchestrator_e2e.py` — stubs for GORD-01..04 against real Linear; MORD-05 cycle summary
- [ ] `tests/integration/test_parallel_mode_e2e.py` — stubs for MORD-03 two-task no-double-claim gate
- [ ] `src/hsb/contracts/global_orchestrator.py` — `GlobalOrchestratorOutput`, `ReadyTask` Pydantic models
- [ ] `src/hsb/contracts/main_orchestrator.py` — `MainOrchestratorOutput`, `DispatchedItem`, `ClaimResult` Pydantic models
- [ ] `.claude/skills/global-orchestration/SKILL.md` — migrated from `skills/07-GLOBAL-ORCHESTRATION.md`
- [ ] `.claude/skills/main-orchestrator/SKILL.md` — migrated from `skills/00-MAIN-ORCHESTRATOR.md`
- [ ] `.worktrees/` added to `.gitignore`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Two concurrent `hsb run --parallel` processes don't double-claim | MORD-03 | Multi-process race requires two terminal sessions | Run `hsb run --parallel` in two terminals simultaneously with 2 ready tasks; verify each task dispatched exactly once |
| `hsb run-next-step` still works for single-task debug | — | Regression check | Run `hsb run-next-step` and confirm it bypasses Global Orchestrator and dispatches directly to WIO |

---

## Threat Model

| ID | Pattern | STRIDE | Mitigation |
|----|---------|--------|------------|
| T-4-01 | Double-claim / task hijacking | Spoofing | `updatedAt` optimistic lock (D-04); skip on mismatch; sequential claiming loop (D-05) |
| T-4-02 | Subprocess injection via task title in branch slug | Tampering | Strip shell-special chars from slugs; use `asyncio.create_subprocess_exec` (not `shell=True`) |
| T-4-03 | Worktree accumulation (disk DoS) | DoS | `finally` cleanup + `git worktree prune` at startup; `.worktrees/` in `.gitignore` |
| T-4-04 | Env var leakage to WIO subprocess | Information Disclosure | Pass only allowlisted env vars to subprocess; never pass `**os.environ` wholesale |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (unit), < 120s (full)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
