---
phase: 3
slug: work-item-orchestrator-and-single-cycle-mvp
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-05
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
| 03-01 | 01 | 1 | WORC-02 | — | No sub-agent dispatch | unit | `pytest tests/unit/test_orchestrator.py::test_no_subagent_dispatch -x` | ❌ W0 | ⬜ pending |
| 03-02 | 01 | 1 | WORC-03 | T-3-04 | QA cycle cap escalates at 3, never 4th cycle | unit | `pytest tests/unit/test_orchestrator.py::test_qa_cycle_cap -x` | ❌ W0 | ⬜ pending |
| 03-03 | 01 | 1 | WORC-04 | T-3-01 | Full Linear content passed as structured JSON (not raw string) | unit | `pytest tests/unit/test_orchestrator.py::test_full_context_in_tool_calls -x` | ❌ W0 | ⬜ pending |
| 03-04 | 02 | 1 | CLIR-02 | — | show-state renders table without executing | unit | `pytest tests/unit/test_cli.py::test_show_state_renders -x` | ❌ W0 | ⬜ pending |
| 03-05 | 02 | 1 | CLIR-03 | — | show-next-action shows decision without side effects | unit | `pytest tests/unit/test_cli.py::test_show_next_action_no_side_effects -x` | ❌ W0 | ⬜ pending |
| 03-06 | 02 | 1 | CLIR-05 | — | CLI command is standalone asyncio.run() with no process-level state | unit | `pytest tests/unit/test_cli.py::test_no_process_state -x` | ❌ W0 | ⬜ pending |
| 03-07 | 03 | 2 | WORC-01 | — | Full lifecycle todo→done | integration | `pytest tests/integration/test_orchestrator_e2e.py::test_full_lifecycle -x` | ❌ W0 | ⬜ pending |
| 03-08 | 03 | 2 | WORC-05 | — | Lifecycle summary persisted to Linear as comment | integration | `pytest tests/integration/test_orchestrator_e2e.py::test_lifecycle_comment -x` | ❌ W0 | ⬜ pending |
| 03-09 | 03 | 2 | CLIR-01 | — | hsb run-next-step triggers one lifecycle step | integration | `pytest tests/integration/test_cli.py::test_run_next_step -x` | ❌ W0 | ⬜ pending |
| 03-10 | 04 | 2 | CLIR-04 | T-3-03 | run_loop.py terminates when no ready tasks | integration | `pytest tests/integration/test_run_loop.py::test_loop_terminates -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_orchestrator.py` — unit test stubs for WORC-02, WORC-03, WORC-04
- [ ] `tests/unit/test_cli.py` — unit test stubs for CLIR-02, CLIR-03, CLIR-05
- [ ] `tests/integration/test_orchestrator_e2e.py` — integration test stubs for WORC-01, WORC-05 (requires real Linear + hsb-test-fixture)
- [ ] `tests/integration/test_cli.py` — integration test stub for CLIR-01
- [ ] `tests/integration/test_run_loop.py` — integration test stub for CLIR-04
- [ ] `src/hsb/contracts/orchestrator.py` — Pydantic models for Work Item Orchestration Contract

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Prompt injection: Linear issue content handled as structured JSON | WORC-04 | Requires live Linear workspace with crafted issue content | Create Linear issue with injection payload in title/body; run hsb run-next-step; verify orchestrator passes content as JSON field, not embedded in prompt string |
| Credential leakage: API keys not logged | N/A (security) | Log inspection required | Run hsb run-next-step with verbose logging; grep logs for ANTHROPIC_API_KEY and LINEAR_API_KEY; must be absent |
| max_turns ceiling: session respects hard limit | WORC-03 | Requires live SDK session to verify | Configure max_turns=5 in test environment; trigger orchestrator with task that would exceed; verify graceful stop |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
