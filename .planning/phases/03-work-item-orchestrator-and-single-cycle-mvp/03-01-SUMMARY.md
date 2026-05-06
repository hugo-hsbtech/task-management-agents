---
phase: 03-work-item-orchestrator-and-single-cycle-mvp
plan: 01
status: complete
completed: 2026-05-06
self_check: PASSED
---

# Plan 03-01 — Foundation Contracts, Wave 0 Stubs, SKILL.md Migration

## Objective

Lay the Phase 3 foundation: pydantic contracts for the Work Item Orchestrator,
Wave 0 test stubs covering all 10 Phase 3 requirement IDs, and the
`task-orchestration` SKILL.md migration. No production logic shipped — this
plan is verifiable scaffolding for Plans 02 / 03 / 04.

## Files Created

| Path | Purpose |
|------|---------|
| `src/hsb/contracts/orchestrator.py` | `WorkItemOrchInput` and `WorkItemOrchOutput` pydantic models matching `agents/AGENT-CONTRACTS.md §3` |
| `tests/unit/test_orchestrator.py` | Unit stubs for WORC-02/03/04 + 4 functional contract validation tests |
| `tests/unit/test_cli.py` | Unit stubs for CLIR-02/03/05 (with import guard) |
| `tests/integration/test_orchestrator_e2e.py` | E2E stubs for WORC-01/03/05, marked `pytest.mark.integration` |
| `tests/integration/test_cli.py` | Integration CLI stubs for CLIR-01 + CLIR-02 variant |
| `tests/integration/test_run_loop.py` | Loop stubs for CLIR-04 + Pitfall 5 protection |
| `.claude/skills/task-orchestration/SKILL.md` | Migrated skill with YAML frontmatter; body verbatim from `skills/06-TASK-ORCHESTRATION.md` |

## Key Files (created)

- `src/hsb/contracts/orchestrator.py`
- `.claude/skills/task-orchestration/SKILL.md`
- `tests/unit/test_orchestrator.py`
- `tests/unit/test_cli.py`
- `tests/integration/test_orchestrator_e2e.py`
- `tests/integration/test_cli.py`
- `tests/integration/test_run_loop.py`

## Verification Results

| Check | Target | Actual | Status |
|-------|--------|--------|--------|
| Pydantic models import + validate | success | success | PASS |
| Contract validation tests | 3 passing | 3 passing (+ 1 bonus input test) | PASS |
| Wave 0 stub markers across `tests/` | >= 11 | 27 | PASS |
| Integration files marked `pytest.mark.integration` | 3 | 3 | PASS |
| `pytest tests/unit/ --collect-only` | succeeds | 37 tests collected, 0 errors | PASS |
| SKILL.md frontmatter parses as YAML | valid dict | valid dict (`name`, `disable-model-invocation: true`, `allowed-tools`, `arguments`, `description`) | PASS |
| `skills/06-TASK-ORCHESTRATION.md` unchanged | sha unchanged | sha256 `fbad3a9c2bad5491314fdb0702e215f3c4227b2898a77a8d2472aab89c2ce2b7` (matches pre-task) | PASS |

### Pytest evidence

```
tests/unit/test_orchestrator.py::test_valid_orch_output_passes PASSED
tests/unit/test_orchestrator.py::test_invalid_lifecycle_status_fails PASSED
tests/unit/test_orchestrator.py::test_orch_output_extra_field_rejected PASSED
3 passed in 0.12s
```

## Wave 0 Stub Coverage

Wave 0 stub count target: 11+. Actual: **27 stubs** across 5 test files.

| Requirement | Stub Test Function(s) | File |
|-------------|----------------------|------|
| WORC-01 | `test_full_lifecycle_todo_to_done`, `test_full_lifecycle` | `tests/integration/test_orchestrator_e2e.py` |
| WORC-02 | `test_no_subagent_dispatch_in_options`, `test_no_subagent_dispatch` | `tests/unit/test_orchestrator.py` |
| WORC-03 | `test_qa_cycle_cap_model_validator`, `test_qa_cycle_cap`, `test_qa_cycle_cap_safety_net_posts_comment`, `test_qa_cycle_cap_not_exceeded` | `tests/unit/test_orchestrator.py`, `tests/integration/test_orchestrator_e2e.py` |
| WORC-04 | `test_tool_wrapper_requires_full_issue_content`, `test_full_context_in_tool_calls` | `tests/unit/test_orchestrator.py` |
| WORC-05 | `test_lifecycle_comment_persisted`, `test_lifecycle_comment` | `tests/integration/test_orchestrator_e2e.py` |
| CLIR-01 | `test_run_next_step_triggers_lifecycle`, `test_run_next_step` | `tests/integration/test_cli.py` |
| CLIR-02 | `test_show_state_renders_table`, `test_show_state_renders`, `test_show_state_returns_table_output` | `tests/unit/test_cli.py`, `tests/integration/test_cli.py` |
| CLIR-03 | `test_show_next_action_no_side_effects` | `tests/unit/test_cli.py` |
| CLIR-04 | `test_loop_terminates_when_no_ready_tasks`, `test_loop_terminates`, `test_loop_exits_on_ctrl_c`, `test_loop_stops_on_run_next_step_failure` | `tests/integration/test_run_loop.py` |
| CLIR-05 | `test_run_next_step_uses_asyncio_run`, `test_show_state_uses_asyncio_run`, `test_no_process_state` | `tests/unit/test_cli.py` |

Both VALIDATION.md command IDs and PLAN-required canonical names are present
as test functions to keep both invocation paths green.

## Deviations

None. All three tasks executed per plan.

## Self-Check: PASSED

- All acceptance criteria pass.
- Three contract validation tests pass.
- Test collection succeeds on the full suite (37 unit + 26 integration = 63 tests collected).
- Source skill file unchanged.

## Commits

```
b86e809 feat(03-01): add Work Item Orchestrator pydantic contracts
469dd66 test(03-01): Wave 0 test stubs for WORC-01..05 + CLIR-01..05
3143be1 feat(03-01): migrate task-orchestration SKILL.md
```

## Hand-off to Plan 03-02

Plan 02 implements `src/hsb/agents/work_item_orchestrator.py` against:

- The pydantic contracts in `src/hsb/contracts/orchestrator.py`
- The Wave 0 stub function names in `tests/unit/test_orchestrator.py` (must
  flip from `pytest.fail("Wave 0 stub …")` to real assertions)
- The migrated `.claude/skills/task-orchestration/SKILL.md` (read by the SDK
  session at startup; body is the canonical orchestration spec)
