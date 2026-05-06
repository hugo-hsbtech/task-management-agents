---
phase: 05-enhancement-agents
plan: 02
status: complete
wave: 1
completed: 2026-05-06
requirements:
  - RISK-01
  - RISK-02
  - RISK-03
  - RISK-04
---

# Plan 05-02 Summary — Risk Agent + chokepoint module

Wave 1 of Phase 5. Establishes the Phase 5 SDK chokepoint module
(`_sdk_options.py`) and the deterministic Risk Agent (skills 12+13) plus the
isolated skill 14 SDK call. Wires the G5 stack-inspection decorator onto
the Phase 1 LinearAgent write dispatch path.

## Tasks Completed

| Task | Commit |
|------|--------|
| 1: contracts + _sdk_options + 3 SKILL.md + conftest fixture + factory tests | 7cd5cee |
| 2: RiskAgent class + 4 unit-test files (RISK-01..04 + SC-5 positive path) | (this wave) |
| 3: linear_agent.py G5 wiring + linear_write_guard tests | (this wave) |

## Key Files Created

| Path | Lines |
|------|-------|
| `src/hsb/contracts/risk.py` | 43 |
| `src/hsb/agents/_sdk_options.py` | 226 |
| `src/hsb/agents/risk_agent.py` | 230 |
| `.claude/skills/quality-scoring-risk-analysis/SKILL.md` | 177 |
| `.claude/skills/adaptive-prioritization/SKILL.md` | 125 |
| `.claude/skills/auto-improvement-triggers/SKILL.md` | 170 |
| `tests/unit/test_sdk_options_factory.py` | 145 |
| `tests/unit/test_risk_agent_quality_score.py` | 90 |
| `tests/unit/test_risk_agent_priority_queue.py` | 61 |
| `tests/unit/test_risk_agent_triggers.py` | 161 |
| `tests/unit/test_risk_agent_skill14_config.py` | 119 |
| `tests/unit/test_linear_write_guard_g5.py` | 121 |

## Files Modified

| Path | Change |
|------|--------|
| `src/hsb/agents/linear_agent.py` | imports `linear_write_guard`; wraps WRITE-operation dispatch through `_run_validated_linear_agent_write` (G5). READ ops bypass the guard. Phase 1 retry/validation logic preserved. |
| `tests/conftest.py` | session-scoped autouse `_gsd_clear_api_key` fixture appended (G1 defensive pairing). Phase 1 fixtures untouched. |
| `pyproject.toml` | `hypothesis>=6.100.0` added to `[project.optional-dependencies].dev`. |

## RISK-04 Defense-in-Depth Layers

| Layer | Mechanism | Evidence |
|-------|-----------|----------|
| 1 (structural) | Skill 14 SDK call has `allowed_tools=[]` and `mcp_servers=None` | `risk_agent.py:177` `make_options(...)` call with frozen knobs; `test_skill14_options_has_empty_tools_and_no_mcp` |
| 2 (parse-time) | `AutoImprovementTrigger.linear_state` is `Literal["suggested"]` | `risk.py:39`; verified by `python -c "AutoImprovementTrigger(..., linear_state='created')"` raises ValidationError |
| 3 (import-time) | `risk_agent.py` does NOT import `linear_agent` | `test_risk_agent_does_not_import_linear_agent` |
| 4 (runtime) | `linear_write_guard` decorator on LinearAgent write dispatcher | `linear_agent.py:181-189` `@linear_write_guard async def _run_validated_linear_agent_write`; `test_g5_denies_caller_from_risk_agent_path` |

## Guardrail Enforcement Surface

- **G1 (OAuth2 only):** Function-entry guard `assert_oauth2_only()` in
  `_sdk_options.py:32`, called from `make_options()` at every SDK
  construction site. NO module-top assertion in either `_sdk_options.py`
  or `risk_agent.py`. Defensive pairing: session-scoped autouse
  `_gsd_clear_api_key` fixture in `tests/conftest.py:11-19`.
- **G2 (no Agent tool):** `make_options()` raises `ValueError` if
  `"Agent"` is in `allowed_tools`. `_sdk_options.py:67`.
- **G3 (runtime backstop):** `assert_no_task_dispatch(msg)` is called
  per-message inside the `async for msg in query(...)` loop at
  `risk_agent.py:209`.
- **G4 (skill 14 isolation):** `make_options(allowed_tools=[],
  mcp_servers=None, model="claude-haiku-4-5", max_turns=3,
  max_budget_usd=0.05)` at `risk_agent.py:177`. Defensive asserts
  immediately follow.
- **G5 (LinearAgent write guard):** `linear_write_guard` decorator
  applied to `_run_validated_linear_agent_write` at
  `linear_agent.py:181`. WRITE operations
  (`{"create","update","create_comment","create_subtasks","create_issue","update_issue"}`)
  flow through the guarded shim; READ operations bypass the guard.

## LinearAgent Write Surface (G5 Decoration)

Phase 1 exposes `run_validated_linear_agent(operation, payload)` as the
single Linear MCP entry point. Phase 5 wires G5 by:

1. Adding the WRITE-operation set `_WRITE_OPERATIONS` near the top of
   `linear_agent.py`.
2. Renaming the original implementation to
   `_run_validated_linear_agent_impl` (untouched body).
3. Adding `_run_validated_linear_agent_write` decorated with
   `@linear_write_guard` that delegates to the impl after the
   stack-inspection check.
4. Re-introducing the public `run_validated_linear_agent` as a thin
   dispatcher that routes WRITE ops through the guarded shim and READ
   ops directly.

## Test Results

- **29 unit tests pass** across the 6 new Phase 5 unit-test files.
- **Phase 1 regression**: `pytest tests/unit/ -k linear` → 7 passed (no
  regression on the existing LinearAgent contract tests).
- **Hypothesis**: `test_quality_score_deterministic_formula` runs the
  default 100-example budget across the 4-axis input space
  (qa_failures∈[0,10], fix_subtasks∈[0,10], uat_failed∈{T,F},
  rework_cycles∈[0,5]). The arithmetic invariant uses a clamp-aware
  branch: when `100 - sum(penalties) >= 0`, equality holds; when penalties
  exceed 100, the score is clamped to 0 and the breakdown still records
  the full unclamped penalties (audit-trail behavior).

## SC-5 Automated Verification

`tests/unit/test_risk_agent_triggers.py::test_sc5_positive_path_returns_trigger_for_seeded_qa_history`
provides the AUTOMATED verification path that Plan 05-04's SC-5
human-checkpoint cites:

- Seeded `qa_history` = 3 changes_required findings in the same `auth`
  category.
- Stubbed SDK returns one valid trigger payload with
  `pattern_evidence=["LIN-1","LIN-2","LIN-3"]`.
- The fake `query` shim asserts `options.allowed_tools == []` and
  `options.mcp_servers in (None, {})` before yielding (RISK-04 / G4
  defensive-in-test).
- Result: ≥1 `AutoImprovementTrigger` with `linear_state == "suggested"`
  and `len(pattern_evidence) >= 2`. Test passes.

## Notable Decisions

- **`isinstance(msg, ResultMessage)` requires real `ResultMessage`
  instances**: the original plan suggested a duck-typed `_StubResult`
  class, but the production code path checks
  `isinstance(msg, ResultMessage)`. Fix: tests now build real
  `ResultMessage(...)` instances via a small `_make_result()` helper.
- **Arithmetic invariant clamp**: the literal plan invariant
  `100.0 - sum(breakdown) == score` does not hold when penalties exceed
  100 (score clamps to 0). The test branches on the unclamped sum and
  asserts the clamp-to-zero contract instead. Documented inline.
- **Multi-line query() regex**: the receive-loop locator now scans
  parenthesis depth to skip over the multi-line `query(...)` call,
  rather than the original single-line regex (which failed against the
  current keyword-heavy call signature).

## Self-Check: PASSED
