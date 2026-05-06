---
phase: 03-work-item-orchestrator-and-single-cycle-mvp
plan: 03
status: complete
completed: 2026-05-06
self_check: PASSED
---

# Plan 03-03 — Phase 3 CLI Extensions + run_loop.py

## Objective

Wire the Work Item Orchestrator (Plan 02) into the operator-facing CLI. Three
new Typer subcommands (`hsb run-next-step`, `hsb show-state`,
`hsb show-next-action`) and a repo-root `run_loop.py` thin wrapper. Every CLI
invocation is a standalone `asyncio.run()` boundary — no process-level state
shared between cycles.

## Files Modified / Created

| Path | Change | LOC |
|------|--------|-----|
| `src/hsb/cli/main.py` | Modified — appended 3 new commands + 2 helpers | +195 |
| `tests/unit/test_cli.py` | Modified — Wave 0 stubs flipped to assertions | +110 / -37 |
| `run_loop.py` | Created at repo root | 65 |

## Key Files

- `src/hsb/cli/main.py`
- `run_loop.py`
- `tests/unit/test_cli.py`

## Commands Added

`hsb --help` now lists (Phase 3 lines highlighted with [P3]):

```
create-issue      Create a Linear issue with correct parent linkage (LINR-01).
update-issue      Update a Linear issue's status, qa_status, uat_status...
add-comment       Add a structured comment to a Linear issue (LINR-03).
link-pr           Link a GitHub PR URL to a Linear work item (LINR-04).
[P3] run-next-step     Trigger one orchestration cycle — a single work item progresses
                       exactly one lifecycle step (CLIR-01).
[P3] show-state        Render current system state: EPICs, tasks, QA status, PR links
                       (CLIR-02, D-08).
[P3] show-next-action  Display next recommended action without executing it
                       (CLIR-03). No side effects.
backlog           Backlog Planning Agent commands
builder           Builder Agent commands
git               Git/PR Management Agent commands
qa                QA Review Agent commands
```

## Verification Results

| Check | Target | Actual | Status |
|-------|--------|--------|--------|
| 3 new `@app.command(...)` decorators | yes | yes (run-next-step, show-state, show-next-action) | PASS |
| All 3 handlers sync (CLIR-05) | True | True for all 3 (`asyncio.iscoroutinefunction` False) | PASS |
| Each handler wraps work in `asyncio.run(` | yes | 3 occurrences in handlers + 1 helper | PASS |
| 6 D-08 columns in show-state | EPIC / Task / Status / QA Status / QA Cycles / PR Link | All 6 present | PASS |
| show-next-action produces no Linear writes | yes | unit test mocks `run_validated_linear_agent` and asserts every call has operation='read' | PASS |
| Existing Phase 1/2 commands still listed | yes | create-issue, update-issue, add-comment, link-pr, backlog, builder, git, qa all present | PASS |
| `tests/unit/test_cli.py` pass | all | 7/7 passing (no remaining "Wave 0 stub") | PASS |
| Full unit suite still green | all | 42/42 passing | PASS |
| `run_loop.py` exists at repo root | yes | yes (65 lines) | PASS |
| `run_loop.py` has Pitfall 5 returncode check | yes | yes (`result.returncode != 0` → `sys.exit`) | PASS |
| `run_loop.py` does NOT import the orchestrator directly (CLIR-05) | True | True (subprocess.run only) | PASS |
| `run_loop.py` handles KeyboardInterrupt | yes | yes (clean print on SIGINT) | PASS |

### Pytest evidence

```
tests/unit/test_cli.py::test_show_state_renders_table PASSED
tests/unit/test_cli.py::test_show_state_renders PASSED
tests/unit/test_cli.py::test_show_next_action_no_side_effects PASSED
tests/unit/test_cli.py::test_run_next_step_uses_asyncio_run PASSED
tests/unit/test_cli.py::test_show_state_uses_asyncio_run PASSED
tests/unit/test_cli.py::test_show_next_action_uses_asyncio_run PASSED
tests/unit/test_cli.py::test_no_process_state PASSED
7 passed in 0.50s
```

Full unit suite: `42 passed in 0.55s`.

## Design Notes

1. **CLIR-05 subprocess boundary in `run_loop.py`.** The plan explicitly
   chose `subprocess.run(["hsb", "run-next-step"])` instead of an in-process
   import of `run_orchestration_cycle`. The subprocess boundary is the
   strongest possible guarantee that no Python module state survives between
   iterations — Linear is the entire state store between cycles (D-07).

2. **`_parse_epics_from_linear_output` is intentionally permissive.** The
   Phase 1 `LinearEntity` schema only guarantees `id`, `type`, `url` — extra
   fields like `title`, `status`, `qa_status` arrive only when Linear MCP
   `read` returns richer payloads. The helper coerces entities via
   `model_dump()`, falls back to dict access, and uses `.get(..., "—")` so
   show-state never crashes on a sparse response. Plan 04 will refine the
   parser against the live workspace.

3. **show-next-action decision logic is local.** All branching is computed
   from the read result fields (`status`, `qa_status`, `qa_cycle_count`).
   No write call is ever issued — the unit test asserts this via mock.

## Pitfalls Encountered

None — followed 03-PATTERNS.md verbatim. The Pitfall 5 returncode check is
explicit in `main()` and exercised only at the integration level (Plan 04).

## Self-Check: PASSED

- 3 new commands wired and listed in `hsb --help`.
- All 3 handlers synchronous (CLIR-05).
- show-state renders all 6 D-08 columns.
- show-next-action passes the no-write mock assertion.
- run_loop.py at repo root with returncode check + KeyboardInterrupt handler.
- 7/7 CLI unit tests + 42/42 full unit suite passing.

## Commits

```
7ef8d46 feat(03-03): add Phase 3 CLI commands (run-next-step, show-state, show-next-action)
618ead3 feat(03-03): add run_loop.py thin wrapper at repo root
```

## Hand-off to Plan 03-04

Plan 04 converts the integration-test stubs (created as Wave 0 stubs in
Plan 01) into live assertions against the real Linear test workspace + the
`hsb-test-fixture` GitHub repo (Phase 2 D-11). The MVP benchmark cycle
exercises:

- `tests/integration/test_orchestrator_e2e.py::test_full_lifecycle_todo_to_done`
- `tests/integration/test_orchestrator_e2e.py::test_lifecycle_comment_persisted`
- `tests/integration/test_cli.py::test_run_next_step_triggers_lifecycle`
- `tests/integration/test_run_loop.py::test_loop_terminates_when_no_ready_tasks`

Plan 04 is ``autonomous: false`` — it requires a human checkpoint for the
live Linear OAuth + workspace setup before the MVP benchmark can run.
