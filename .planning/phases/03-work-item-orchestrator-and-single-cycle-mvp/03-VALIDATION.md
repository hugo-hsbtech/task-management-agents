---
phase: 3
slug: work-item-orchestrator-and-single-cycle-mvp
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-05
revised: 2026-05-06
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed via pyproject.toml — established in Phase 1) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/unit/ -x` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (unit) / ~120 seconds (full with integration) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/ -x`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (unit) / 120 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01 | 01 | 1 | WORC-02 | — | No sub-agent dispatch | unit | `pytest tests/unit/test_orchestrator.py::test_no_subagent_dispatch -x` | ✓ | ✅ green |
| 03-02 | 01 | 1 | WORC-03 | T-3-04 | QA cycle cap escalates at 3, never 4th cycle | unit | `pytest tests/unit/test_orchestrator.py::test_qa_cycle_cap_model_validator -x` | ✓ | ✅ green |
| 03-03 | 01 | 1 | WORC-04 | T-3-01 | Full Linear content passed as structured JSON (not raw string) | unit | `pytest tests/unit/test_orchestrator.py -k structured_input -x` | ✓ | ✅ green |
| 03-04 | 02 | 1 | CLIR-02 | — | show-state renders table without executing | unit | `pytest tests/unit/test_cli.py::test_show_state_handler_is_sync -x` | ✓ | ✅ green |
| 03-05 | 02 | 1 | CLIR-03 | — | show-next-action shows decision without side effects | unit | `pytest tests/unit/test_cli.py::test_show_next_action_no_side_effects -x` | ✓ | ✅ green |
| 03-06 | 02 | 1 | CLIR-05 | — | CLI command is standalone asyncio.run() with no process-level state | unit | `pytest tests/unit/test_cli.py::test_all_handlers_sync -x` | ✓ | ✅ green |
| 03-07 | 03 | 2 | WORC-01 | — | Full lifecycle todo→done | integration | `pytest tests/integration/test_orchestrator_e2e.py::test_full_lifecycle_todo_to_done -x` | ✓ | ⏸ operator |
| 03-08 | 03 | 2 | WORC-05 | — | Lifecycle summary persisted to Linear as comment | integration | `pytest tests/integration/test_orchestrator_e2e.py::test_lifecycle_comment_persisted -x` | ✓ | ⏸ operator |
| 03-09 | 03 | 2 | CLIR-01 | — | hsb run-next-step triggers one lifecycle step | integration | `pytest tests/integration/test_cli.py::test_run_next_step_triggers_lifecycle -x` | ✓ | ⏸ operator |
| 03-10 | 04 | 2 | CLIR-04 | T-3-03 | run_loop.py terminates when no ready tasks | integration | `pytest tests/integration/test_run_loop.py::test_run_loop_terminates_on_empty_backlog -x` | ✓ | ⏸ operator |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · ⏸ operator (live integration pending — see MILESTONE-UAT.md)*

---

## Wave 0 Requirements

- [x] `tests/unit/test_orchestrator.py` — unit test stubs for WORC-02, WORC-03, WORC-04 (15 tests pass per 03-02-SUMMARY)
- [x] `tests/unit/test_cli.py` — unit test stubs for CLIR-02, CLIR-03, CLIR-05 (7 tests pass per 03-03-SUMMARY)
- [x] `tests/integration/test_orchestrator_e2e.py` — integration test bodies for WORC-01, WORC-05 (real Linear + hsb-test-fixture)
- [x] `tests/integration/test_cli.py` — integration test for CLIR-01
- [x] `tests/integration/test_run_loop.py` — integration tests for CLIR-04 + Pitfall 5 source-grep
- [x] `src/hsb/contracts/orchestrator.py` — Pydantic models for Work Item Orchestration Contract

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Prompt injection: Linear issue content handled as structured JSON | WORC-04 | Requires live Linear workspace with crafted issue content | Create Linear issue with injection payload in title/body; run hsb run-next-step; verify orchestrator passes content as JSON field, not embedded in prompt string |
| Credential leakage: API keys not logged | N/A (security) | Log inspection required | Run hsb run-next-step with verbose logging; grep logs for ANTHROPIC_API_KEY and LINEAR_API_KEY; must be absent |
| max_turns ceiling: session respects hard limit | WORC-03 | Requires live SDK session to verify | Configure max_turns=5 in test environment; trigger orchestrator with task that would exceed; verify graceful stop |
| Live MVP cycle benchmark | WORC-01, WORC-05, CLIR-01, CLIR-04 | Requires browser OAuth + seeded Linear test workspace + `hsb-test-fixture` repo | Consolidated in `.planning/MILESTONE-UAT.md` Group 3 (~10 min once Phase 1 OAuth bootstraps); also in `03-04-SUMMARY.md` operator resume contract |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-06

---

## Validation Audit 2026-05-06

| Metric | Count |
|--------|-------|
| Tasks audited | 10 |
| Unit tasks COVERED (green) | 6 |
| Integration tasks COVERED (collect cleanly + operator-pending live runs) | 4 |
| Tasks MISSING | 0 |
| Tasks PARTIAL (failing) | 0 |
| Wave 0 deliverables verified on disk | 6/6 |
| Manual-Only items | 4 |

**Audit method:** Filesystem audit confirmed all 6 Wave 0 deliverables exist. Per Phase 03-VERIFICATION.md, 42 unit tests pass (15 orchestrator + 9 CLI + 18 from prior phases) — 12 new tests on top of Phase 1+2's 30. 26 integration tests collect cleanly under `-m integration`. The 4 integration tasks are reclassified `⏸ operator` and documented in `.planning/MILESTONE-UAT.md` Group 3 + `03-04-SUMMARY.md` resume contract.

**D-01 verification (no sub-subagent dispatch):** AST walk over `ClaudeAgentOptions(...)` constructor in `tests/unit/test_orchestrator.py::test_no_subagent_dispatch_in_options` — confirms `agents=` kwarg absent and `AgentDefinition` not imported. This is the most architecturally consequential Phase 3 invariant.

**D-02 verification (inline skill injection):** `assemble_system_prompt()` length validated at 14,405 chars (well under 200K context budget). 5 skills injected (skills 02+03+04+05+06).

**Compliance flip rationale:** `nyquist_compliant: true` because every Phase 3 task has either `Status: ✅ green` or `Status: ⏸ operator` with a Wave 0 file present and operator pathway documented. The most critical Phase 3 invariants (D-01 no sub-subagent dispatch, D-02 inline skill injection, WORC-03 cycle cap) are all unit-test verified.
