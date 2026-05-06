---
phase: 01-foundation-and-linear-integration
plan: 05
subsystem: cli-and-integration
tags: [typer, cli, integration-tests, oauth, linear-mcp, FOUND-01, LINR-01, LINR-02, LINR-03, LINR-04]

requires:
  - phase: 01-01
    provides: scaffolded src/hsb/cli/main.py stub, .mcp.json with Linear server, .gitignore for .env
  - phase: 01-02
    provides: LinearOutput pydantic model
  - phase: 01-04
    provides: run_validated_linear_agent (validation-gated entry point)
provides:
  - 4 typer commands (create-issue, update-issue, add-comment, link-pr) wired to run_validated_linear_agent via asyncio.run() at the CLI boundary
  - tests/test_cli.py — 5 CliRunner smoke tests with AsyncMock-mocked agent
  - tests/test_integration.py — 9 live-MCP integration tests gated by `@pytest.mark.integration` and env vars
  - .planning/phases/01-foundation-and-linear-integration/HUMAN-SETUP.md — step-by-step operator guide (API key, OAuth warmup, team ID, sandbox issue, integration run, manual UI verification of LINR-02)
affects: [Phase 2 — operator already has working CLI for ad-hoc Linear ops; integration test pattern reused for per-agent suites]

tech-stack:
  added: []
  patterns:
    - "typer command + asyncio.run boundary pattern (sync typer body calls asyncio.run; never inside coroutines)"
    - "CliRunner + patch.object for sync-side smoke testing of CLI -> async agent dispatch"
    - "@pytest.mark.integration module-level marker + _require_env() skip helper for env-gated live tests"

key-files:
  created:
    - tests/test_cli.py
    - tests/test_integration.py
    - .planning/phases/01-foundation-and-linear-integration/HUMAN-SETUP.md
  modified:
    - src/hsb/cli/main.py (replaced Plan 01 stub with full 4-command implementation)

key-decisions:
  - "asyncio.run() ONLY in _dispatch helper (sync) — never in command body or async function (Pitfall 5 mitigation)"
  - "update-issue strips None values before dispatch — passing None to Linear MCP would clear the field (data loss risk)"
  - "Integration suite skipped by default; only runs with -m integration AND env vars set"
  - "Step 5b (manual UI verification) included so operator visually confirms qa_status / uat_status / assigned_orchestrator landed in Linear UI per OQ1 resolution"

patterns-established:
  - "Pattern 1: Sync CLI command body → _dispatch helper → asyncio.run(run_validated_*_agent(...)) — single asyncio.run() call site per command"
  - "Pattern 2: Integration tests gated by env vars + module-level marker — skip cleanly in CI without secrets"
  - "Pattern 3: Test issue title prefix [PHASE-1-INTEGRATION] for filterable cleanup in Linear UI"

requirements-completed:
  - LINR-01
  - LINR-02
  - LINR-03
  - LINR-04
  - FOUND-01

requirements-pending-human-verification:
  - "FOUND-01, LINR-01, LINR-02, LINR-03, LINR-04 — automated CLI scaffolding and unit tests pass; live verification via Step 5 + 5b of HUMAN-SETUP.md is the operator's responsibility (Task 3 checkpoint)"

duration: 8min
completed: 2026-05-06
human_checkpoint_status: pending
---

# Phase 01-05: Typer CLI + Live MCP Integration Suite Summary

**4-command typer CLI shipped (`hsb create-issue|update-issue|add-comment|link-pr`) wired to the validated Linear Agent. 5 CliRunner smoke tests pass; 9 integration tests collected and gated by `@pytest.mark.integration`. HUMAN-SETUP.md guides the operator through one-time OAuth setup. Live verification (Task 3) requires browser OAuth and is pending operator action.**

## Performance

- **Duration:** ~8 min (Tasks 1 + 2; Task 3 pending operator)
- **Started:** 2026-05-06
- **Completed:** 2026-05-06 (autonomous tasks)
- **Tasks:** 2 of 3 complete (Task 3 = human checkpoint, blocked on browser OAuth)
- **Files modified:** 4 (1 modified, 3 created)

## Accomplishments
- Replaced Plan 01's `src/hsb/cli/main.py` stub with full 4-command implementation
- All commands route through `_dispatch(operation, payload)` helper that owns the single `asyncio.run()` call site (Pitfall 5 mitigation)
- `update-issue` exposes all 4 LINR-02 fields (`--status`, `--qa-status`, `--uat-status`, `--assigned-orchestrator`) and strips None values before dispatch
- 5 CliRunner smoke tests verify each command's payload structure and the failure path (exit code 1 on agent error)
- 9 integration tests cover FOUND-01 (1) + LINR-01 full 4-level hierarchy (4: epic / user_story / task / subtask) + LINR-02 status + LINR-02 custom fields + LINR-03 + LINR-04
- HUMAN-SETUP.md walks the operator through API key (Step 1), OAuth warmup (Step 2), team ID (Step 3), sandbox issue (Step 4), live integration run (Step 5), and manual UI verification of LINR-02 custom fields (Step 5b)
- Wave-merge gate (`pytest tests/ -x --ignore=tests/test_integration.py`) — 35 passed

## Task Commits

1. **Task 1: Replace cli/main.py stub with full 4-command implementation + write CLI smoke tests** - `7d8cb10` (feat)
2. **Task 2: Create tests/test_integration.py and HUMAN-SETUP.md** - `a9a7ec6` (feat)
3. **Task 3: Operator runs HUMAN-SETUP.md and verifies live FOUND-01 + LINR-01..04** - PENDING (checkpoint:human-verify; requires browser OAuth)

## Files Created/Modified

- `src/hsb/cli/main.py` — Replaced stub; now 100 lines with `_dispatch` helper, 4 `@app.command` functions, rich console output, and `typer.Exit(code=1)` failure path
- `tests/test_cli.py` — 5 CliRunner smoke tests with AsyncMock-mocked `run_validated_linear_agent`
- `tests/test_integration.py` — 9 async tests with `pytestmark = pytest.mark.integration` and `_require_env()` skip helper
- `.planning/phases/01-foundation-and-linear-integration/HUMAN-SETUP.md` — 5 setup steps + Step 5b (manual UI verification) + Troubleshooting

## Decisions Made

- **Task 3 deferred**: Task 3 is a `checkpoint:human-verify` gate that requires the operator to (a) add a real `ANTHROPIC_API_KEY` to `.env`, (b) complete one-time browser-based OAuth login for Linear MCP, and (c) run the integration test suite against a live Linear workspace. None of these are possible from an autonomous orchestrator running in the background. The plan was executed up to the checkpoint and the live verification is queued for the operator. After the operator completes Steps 1-5b in `HUMAN-SETUP.md` and types "approved", Phase 1 verification can proceed. If any of the 9 acceptance criteria fail, gap closure is triggered (root-cause hints documented in the plan).

## Deviations from Plan

None in Tasks 1 and 2 — both executed exactly as written. Task 3 not executed (correctly: it is a human checkpoint by design).

## Verification

- `hsb --help` lists all 4 commands ✓
- `hsb create-issue --help` shows `--parent-id` ✓
- `hsb update-issue --help` shows `--qa-status`, `--uat-status`, `--assigned-orchestrator` ✓
- `pytest tests/test_cli.py -x` — 5 passed ✓
- `pytest tests/test_integration.py --collect-only -q` — 9 tests collected ✓
- `pytest tests/ -x --ignore=tests/test_integration.py` (Wave-merge gate) — 35 passed ✓
- All grep acceptance checks pass:
  - `@app.command` count ≥ 4 ✓
  - `asyncio.run(run_validated_linear_agent` ✓
  - `--qa-status`, `--uat-status`, `--assigned-orchestrator` ✓
  - `typer.Exit(code=1)` ✓
  - `pytestmark = pytest.mark.integration` ✓
  - `Step 5b` in HUMAN-SETUP.md ✓
  - `mcp.linear.app` in HUMAN-SETUP.md ✓

## Threats Mitigated (CLI surface)

| Threat ID | Status | Verification |
|-----------|--------|--------------|
| T-05-01 (CLI stdout payload disclosure) | Accepted | Internal operator tool; pprint output local-only |
| T-05-02 (accidental production mutation) | Mitigated | HUMAN-SETUP.md uses LINEAR_TEST_TEAM_ID for tests; CLI prints result |
| T-05-03 (semantic misuse — parent on epic) | Mitigated | Linear Agent system prompt forbids reparenting; verified in checkpoint Step 6 |
| T-05-04 (test pollution of real workspace) | Mitigated | All test issue titles prefixed `[PHASE-1-INTEGRATION]` |
| T-05-05 (silent prefix mismatch) | Mitigated | `test_mcp_connection_and_tool_prefix` runs first; checkpoint Step 8 negative grep |
| T-05-06 (OAuth token exfiltration) | Accepted | Token storage handled by mcp-remote; user-OS-level concern |

## Pending Human Action — Task 3 (Live Verification)

The operator must complete the following before Phase 1 can be marked fully verified:

1. Add `ANTHROPIC_API_KEY=sk-ant-...` to `.env`
2. Run the OAuth one-liner from HUMAN-SETUP.md Step 2 in a browser-available shell
3. Export `LINEAR_TEST_TEAM_ID` and `LINEAR_TEST_ISSUE_ID` env vars
4. Run `pytest tests/test_integration.py -x -m integration -v` — expect 9 passed
5. Visually confirm in Linear UI per HUMAN-SETUP.md Step 5b that qa_status / uat_status / assigned_orchestrator are visible (custom field, label, or structured comment)
6. (Optional) Manual smoke `hsb create-issue ...`
7. Inspect `.claude/linear_audit.log` (JSON lines per op)
8. Confirm negative grep `! grep -r "mcp__claude_aiL_inear__" src/ .claude/ tests/`

If all 8 succeed: type "approved" in chat — Phase 1 is verifiably complete.
If any fail: root cause hints in Plan 01-05 Task 3 `<action>`.

## Next Phase Readiness

- After operator approval: `pytest tests/ -x` (full suite including integration) passes 100% — phase verifier can run
- Phase 2 plans can use `hsb create-issue` ad-hoc to seed test data; integration test pattern is the template for per-agent suites in Phase 2

## Self-Check: PASSED (autonomous tasks); HUMAN-CHECKPOINT-PENDING (Task 3)
