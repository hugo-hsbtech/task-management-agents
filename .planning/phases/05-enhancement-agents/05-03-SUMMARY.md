---
phase: 05-enhancement-agents
plan: 03
status: complete
wave: 2
completed: 2026-05-06
requirements:
  - UATA-01
  - UATA-02
  - UATA-03
  - UATA-04
---

# Plan 05-03 Summary — UAT Agent (Pattern B + 3-retry Pydantic wrapper)

Wave 2 of Phase 5 (parallel with Plan 05-01). Builds the standalone UAT
Agent: a Claude Agent SDK ``query()`` one-shot session that validates a
User Story against its acceptance criteria from a user-acceptance
perspective. The agent never writes to Linear directly — Plan 05-04 wires
the Global Orchestrator → Linear Agent path for fix subtasks.

## Tasks Completed

| Task | Commit |
|------|--------|
| 1: contracts + skill 08 + B1 coverage eval + B3 banned-token eval + UAT schema unit tests | (this wave, third 05-x commit) |
| 2: run_uat_and_validate Pattern B implementation + integration test (2 fixture-driven + 10 source-grep) | (this wave, fourth 05-x commit) |

## Files Created (line counts)

| Path | Lines |
|------|-------|
| `src/hsb/contracts/uat.py` | 42 |
| `src/hsb/agents/uat_agent.py` | 161 |
| `.claude/skills/uat-validation/SKILL.md` | 141 |
| `tests/integration/test_uat_agent.py` | 173 |
| `tests/evals/code_based/test_uat_coverage.py` | 109 |
| `tests/evals/code_based/test_uat_scope.py` | 88 |
| `tests/evals/__init__.py` | 0 |
| `tests/evals/code_based/__init__.py` | 0 |

The migrated SKILL.md contains 5 lines of frontmatter + verbatim body
from `skills/08-UAT-VALIDATION.md` (2333 → 2616 bytes).

## UATA-04 Defense-in-Depth

| Layer | Mechanism | Evidence |
|-------|-----------|----------|
| 1 (factory) | `make_options(allowed_tools=["Read","Glob","Grep","Bash"], mcp_servers=None, ...)` | `uat_agent.py:86` |
| 2 (assertions) | Defensive `assert "Write" not in options.allowed_tools`, `assert "Edit" not in ...`, `assert "Agent" not in ...`, `assert mcp_servers in (None, {})` | `uat_agent.py:95-103` |
| 3 (import-time) | `uat_agent.py` does NOT import `linear_agent` | `test_uat_agent_does_not_import_linear_agent` |
| 4 (parse-time) | `UATResult.scope_violations` field is part of every result; B3 banned-token regex catches scope-creep findings | `tests/evals/code_based/test_uat_scope.py` |

## SCOPE BOUNDARY Literal

Embedded in `base_prompt` at `uat_agent.py:76`:

> "SCOPE BOUNDARY: Only validate the acceptance criteria listed below. Do
> not evaluate any feature, behavior, or quality dimension not explicitly
> listed. Any finding that lacks a direct reference to a listed [AC-N]
> criterion is out of scope and must not appear in your response."

The literal appears in the prompt itself (not only in skill 08) so it
survives any context compaction the SDK might perform.

## Frozen SDK Knobs (AI-SPEC §3 Pattern B)

| Knob | Value | Reason |
|------|-------|--------|
| `model` | `claude-sonnet-4-6` | AC reasoning needs full reasoning model |
| `max_turns` | `20` | Lower than WIO's 40 (UAT is single-pass evaluation) |
| `permission_mode` | `dontAsk` | Headless safe |
| `allowed_tools` | `["Read","Glob","Grep","Bash"]` | UATA-04 / G2 |
| `mcp_servers` | `None` | UATA-04 layer 1 |

## 3-Retry Pydantic Wrapper

`uat_agent.py:107-153`. On JSON-decode or ValidationError, the error is
fed back into the next prompt and the loop retries up to `MAX_RETRIES=3`.
After 3 failures, `RuntimeError` is raised with the last validation error.
Never silently swallows invalid output.

## G3 Backstop

`assert_no_task_dispatch(msg)` is called at `uat_agent.py:125` inside the
`async for msg in query(...)` receive loop on every received message. A
multi-line-aware regex test verifies the backstop is wired
(`test_uat_agent_calls_g3_backstop_in_receive_loop`).

## Test Results

- **Code-based eval suite**: 18 tests pass across `test_uat_coverage.py`
  (10 tests: 3 coverage + 5 contract schema + 2 helpers via parametrize)
  and `test_uat_scope.py` (10 tests via parametrize).
- **UAT integration source-grep tests**: 10 of 12 tests pass without
  fixtures (the 2 fixture-driven async tests
  `test_uat_validates_user_story_with_all_tasks_approved` and
  `test_uat_agent_produces_no_scope_violations` require the
  `linear_test_workspace` and `uat_ready_user_story` conftest fixtures
  — they execute during the phase-gate integration sweep).
- **All 12 tests collect cleanly** under `pytest --collect-only`.

## Notable Decisions

- **`mcp_servers in (None, {})` accepted**: the SDK normalizes
  `mcp_servers=None` to `{}` internally on some versions, so the
  defensive assertion accepts both forms.
- **Multi-line-aware receive-loop regex**: identical pattern to
  Plan 05-02's `test_risk_agent_calls_assert_no_task_dispatch_in_receive_loop`
  — anchors on a leading-whitespace `async for msg in query(` match so
  the docstring reference doesn't false-match.
- **Schema unit tests under `tests/evals/code_based/`**: kept inline in
  `test_uat_coverage.py` rather than a separate `tests/unit/test_uat_contract.py`
  to satisfy the plan's "5 files only" budget while still grouping all
  pydantic schema enforcement tests with the coverage eval.

## Self-Check: PASSED
