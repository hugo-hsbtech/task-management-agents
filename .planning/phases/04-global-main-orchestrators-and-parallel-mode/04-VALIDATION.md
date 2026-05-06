---
phase: 4
slug: global-main-orchestrators-and-parallel-mode
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-06
revised: 2026-05-06
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
| 04-01-01 | 01 | 0 | GORD-01 | — | N/A | unit | `pytest tests/unit/test_global_orchestrator.py::test_returns_todo_only -x` | ✓ | ✅ green |
| 04-01-02 | 01 | 0 | GORD-02 | — | N/A | unit | `pytest tests/unit/test_global_orchestrator.py::test_dependency_filter -x` | ✓ | ✅ green |
| 04-01-03 | 01 | 0 | GORD-03 | — | N/A | unit | `pytest tests/unit/test_global_orchestrator.py::test_empty_backlog_signal -x` | ✓ | ✅ green |
| 04-01-04 | 01 | 0 | GORD-04 | — | N/A | unit | `pytest tests/unit/test_global_orchestrator.py::test_epic_ready_signal -x` | ✓ | ✅ green |
| 04-02-01 | 02 | 1 | MORD-01 | — | N/A | unit | `pytest tests/unit/test_main_orchestrator.py::test_mode_routing_cascade tests/unit/test_main_orchestrator.py::test_mode_routing_parallel -x` | ✓ | ✅ green |
| 04-02-02 | 02 | 1 | MORD-02 | — | N/A | unit | `pytest tests/unit/test_main_orchestrator.py::test_cascade_sequential -x` | ✓ | ✅ green |
| 04-02-03 | 02 | 1 | MORD-03 | T-4-01 | Skip task if updatedAt mismatch detected on re-read | unit | `pytest tests/unit/test_main_orchestrator.py::test_claiming_optimistic_lock -x` | ✓ | ✅ green |
| 04-02-04 | 02 | 1 | MORD-04 | T-4-03 | Worktree created/removed in finally block; prune at startup | unit | `pytest tests/unit/test_main_orchestrator.py::test_worktree_lifecycle -x` | ✓ | ✅ green |
| 04-03-01 | 03 | 2 | MORD-03 | T-4-01 | No double-claim in two-task concurrent run | integration | `pytest tests/integration/test_parallel_mode_e2e.py::test_no_double_claim_parallel_two_tasks -x` | ✓ | ⏸ operator |
| 04-03-02 | 03 | 2 | MORD-05 | — | N/A | integration | `pytest tests/integration/test_global_orchestrator_e2e.py::test_cycle_summary_posted -x` | ✓ | ⏸ operator |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · ⏸ operator (live integration pending — see MILESTONE-UAT.md)*

---

## Wave 0 Requirements

- [x] `tests/unit/test_global_orchestrator.py` — 6 tests for GORD-01..04 + 2 contract validation
- [x] `tests/unit/test_main_orchestrator.py` — 10 tests for MORD-01..04 + D-01/D-02 architectural assertions + 2 contract validation
- [x] `tests/integration/test_global_orchestrator_e2e.py` — 5 live integration tests
- [x] `tests/integration/test_parallel_mode_e2e.py` — 3 live tests including the SC-5 `test_no_double_claim_parallel_two_tasks` acceptance gate
- [x] `src/hsb/contracts/global_orchestrator.py` — `GlobalOrchestratorOutput`, `ReadyTask` Pydantic models
- [x] `src/hsb/contracts/main_orchestrator.py` — `MainOrchestratorOutput`, `DispatchedItem`, `ClaimResult` Pydantic models
- [x] `.claude/skills/global-orchestration/SKILL.md` — migrated from `skills/07-GLOBAL-ORCHESTRATION.md`
- [x] `.claude/skills/main-orchestrator/SKILL.md` — migrated from `skills/00-MAIN-ORCHESTRATOR.md`
- [x] `.worktrees/` added to `.gitignore`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Two concurrent `hsb run --parallel` processes don't double-claim | MORD-03 | Multi-process race requires two terminal sessions | Run `hsb run --parallel` in two terminals simultaneously with 2 ready tasks; verify each task dispatched exactly once |
| `hsb run-next-step` still works for single-task debug | — | Regression check (D-11) | Run `hsb run-next-step` and confirm it bypasses Global Orchestrator and dispatches directly to WIO |
| Live parallel-mode acceptance gate | MORD-03, MORD-04, MORD-05 | Requires browser OAuth + ≥2 seeded Linear test tasks + `hsb-test-fixture` repo | 8-step contract in `04-04-SUMMARY.md`; consolidated in `.planning/MILESTONE-UAT.md` Group 4 (~15 min once Phase 1 OAuth bootstraps) |

---

## Threat Model

| ID | Pattern | STRIDE | Mitigation |
|----|---------|--------|------------|
| T-4-01 | Double-claim / task hijacking | Spoofing | `updatedAt` optimistic lock (D-04); skip on mismatch; sequential claiming loop (D-05). Mitigation verified by `test_claiming_optimistic_lock` (PASS). |
| T-4-02 | Subprocess injection via task title in branch slug | Tampering | Strip shell-special chars from slugs via `re.sub(r"[^a-z0-9-]", "-", task.title.lower())[:30]`; use `asyncio.create_subprocess_exec` (NOT `shell=True`). Verified by source-grep — no `shell=True` anywhere in Phase 4 sources. |
| T-4-03 | Worktree accumulation (disk DoS) | DoS | `try/finally` cleanup in `_parallel_dispatch` (D-09) + `git worktree prune` at startup (Pitfall C); `.worktrees/` in `.gitignore`. Verified by `test_worktree_lifecycle` source-grep (PASS). |
| T-4-04 | Env var leakage to WIO subprocess | Information Disclosure | Subprocess env is a strict 5-key allowlist; no `**os.environ` wholesale. Verified by `test_no_sdk_session_in_main_orchestrator` source-grep (PASS). |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s (unit), < 120s (full)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-06

---

## Validation Audit 2026-05-06

| Metric | Count |
|--------|-------|
| Tasks audited | 10 |
| Unit tasks COVERED (green) | 8 |
| Integration tasks COVERED (collect cleanly + operator-pending live runs) | 2 |
| Tasks MISSING | 0 |
| Tasks PARTIAL (failing) | 0 |
| Wave 0 deliverables verified on disk | 9/9 |
| Manual-Only items | 3 |
| Threats with mitigations verified | 4/4 |

**Audit method:** Filesystem audit confirmed all 9 Wave 0 deliverables exist. Per Phase 04-VERIFICATION.md, 58 unit tests pass in 0.55s; 136 tests collect cleanly across the full suite. All 4 STRIDE threats (T-4-01..T-4-04) have source-grep-verified mitigations. The 2 integration tasks are reclassified `⏸ operator` and documented in `.planning/MILESTONE-UAT.md` Group 4 + `04-04-SUMMARY.md` 8-step operator contract.

**Architectural assertions verified by source-grep:** D-01 (`GlobalOrchestrator` source contains no `claude_agent_sdk`/`ClaudeAgentOptions`), D-02 (`main_orchestrator.py` source contains no SDK imports + no `query(`), T-4-04 (no literal `**os.environ`), T-4-02 (no `shell=True`), Pitfall E (`asyncio.gather(..., return_exceptions=True)` in `_parallel_dispatch`), D-09 (worktree cleanup in `try/finally`), Pitfall C (`git worktree prune` at startup of every `_parallel_dispatch`).

**Compliance flip rationale:** `nyquist_compliant: true` because every Phase 4 task has either `Status: ✅ green` or `Status: ⏸ operator` with a Wave 0 file present, all 4 STRIDE threats have verified mitigations, and the live parallel-mode acceptance gate has a documented 8-step operator contract.
