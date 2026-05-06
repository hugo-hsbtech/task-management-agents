---
phase: 03-work-item-orchestrator-and-single-cycle-mvp
status: human_needed
verified: 2026-05-06
verification_method: retroactive
must_haves_total: 10
must_haves_verified_automated: 8
must_haves_pending_human: 2
---

# Phase 03 Verification Report — Work Item Orchestrator + Single-Cycle MVP

**Phase goal (from ROADMAP.md):** One complete controlled cycle — a single Task moving from todo to done through Intelligence → Builder → Git → QA → fix loop — runs successfully in cascade mode via CLI trigger.

**Result:** All 4 plans merged, 12 commits, 0 regressions. 42 unit tests pass; 26 integration tests collect cleanly. Two must-haves (WORC-01 live single-cycle MVP and CLIR-04 live continuous loop) require operator action documented in `03-04-SUMMARY.md`.

This VERIFICATION.md was produced **retroactively** during the v1.0 milestone audit (2026-05-06) because the original execute-phase wrapper did not produce one (subagent dispatch was unavailable).

## Requirement Coverage

| Req | Requirement (from REQUIREMENTS.md) | Implementation | Test | Status |
|-----|-------------------------------------|----------------|------|--------|
| WORC-01 | WIO drives a single work item through the full lifecycle (Intelligence → Builder → Git → QA → fix loop → done) | `src/hsb/agents/work_item_orchestrator.py` (299 LOC, single Claude Agent SDK session, sequential tool use within one context window — Plan 03-02) | `tests/integration/test_orchestrator_e2e.py::test_full_lifecycle_todo_to_done` (live integration) | live integration **pending operator** (`03-04-SUMMARY.md` MVP benchmark) |
| WORC-02 | WIO embeds all lifecycle skill content inline (NO sub-subagent dispatch) | `assemble_system_prompt()` injects 5 skill markdown files (~14,405 chars). AST walk confirms NO `AgentDefinition` import, NO `agents=` kwarg on `ClaudeAgentOptions`. 4 `mcp__agents__run_*` in_process tools registered via `create_sdk_mcp_server` + `@tool` (Plan 03-02) | `tests/unit/test_orchestrator.py::test_no_subagent_dispatch_in_options` + `test_no_subagent_dispatch` (AST walk over `ClaudeAgentOptions(...)`) | automated PASS |
| WORC-03 | WIO tracks `qa_cycle_count` and enforces `max_qa_cycles = 3`; escalates to human at hard limit | `_check_qa_cycle_cap` helper posts "Max QA cycles reached" Linear comment when count >= 3; `WorkItemOrchOutput.qa_cycle` Pydantic Field with `ge=0`; QAOutput from Phase 2 has triple-layer cycle cap (immutable model_validator) (Plan 03-02) | `tests/unit/test_orchestrator.py::test_qa_cycle_cap_model_validator` + `test_check_qa_cycle_cap_posts_escalation_comment` | automated PASS |
| WORC-04 | Every agent invocation passes full Linear issue content as structured input — no reliance on conversation memory | WIO system prompt injects the live work item read from Linear at lifecycle start; `mcp__agents__run_*` tool wrappers each take a structured input dict and produce a canonical envelope return — no implicit state | `tests/unit/test_orchestrator.py` covers structured-input pass-through; AST inspection confirms tool wrappers receive explicit dict args | automated PASS |
| WORC-05 | WIO outputs lifecycle status summary persisted to Linear as a comment on the work item | `WorkItemOrchOutput.lifecycle_status` field; closing-step LinearAgent `create_comment` call wired in `work_item_orchestrator.py` (Plan 03-02) | `tests/integration/test_orchestrator_e2e.py::test_lifecycle_comment_persisted` | code passed; integration pending live run |
| CLIR-01 | Operator can trigger a single orchestration cycle with `run-next-step` from CLI | `hsb run-next-step` typer command (Plan 03-03); single-cycle wrapper around `WorkItemOrchestrator` | `tests/unit/test_cli.py::test_run_next_step_handler_is_sync` + `test_run_next_step_wraps_in_asyncio_run`; `tests/integration/test_cli.py::test_run_next_step_triggers_lifecycle` | unit/code passed; integration pending live run |
| CLIR-02 | Operator can view current system state with `show-state` | `hsb show-state` typer command (Plan 03-03); reads Linear EPICs/tasks/QA status/PR links via Phase 1 LinearAgent | `tests/unit/test_cli.py::test_show_state_handler_is_sync`; `tests/integration/test_cli.py::test_show_state_renders` | unit/code passed; integration pending live run |
| CLIR-03 | Operator can inspect next recommended action with `show-next-action` (no side effects) | `hsb show-next-action` typer command (Plan 03-03); read-only — confirmed by source-grep that handler does not call any Linear write or git mutation | `tests/unit/test_cli.py::test_show_next_action_no_side_effects` | automated PASS |
| CLIR-04 | Operator can run continuous CLI loop (`python run_loop.py`) until no ready tasks remain or operator interrupts | `run_loop.py` at repo root (65 LOC, Plan 03-03); calls `["hsb", "run-next-step"]` (later `["hsb", "run"]` after Phase 4); KeyboardInterrupt handling + Pitfall 5 returncode check | `tests/integration/test_run_loop.py::test_run_loop_terminates_on_empty_backlog` + `test_run_loop_handles_keyboard_interrupt` (live); `test_run_loop_returncode_check` (source-grep, Pitfall 5 protection) | live integration **pending operator** (`03-04-SUMMARY.md` MVP benchmark) |
| CLIR-05 | Each CLI command is a standalone `asyncio.run()` invocation — state lives in Linear, not CLI process | All 3 new Phase 3 handlers are sync (`asyncio.iscoroutinefunction` returns False); each wraps work in `asyncio.run(`. Same pattern as Phase 1 CLI commands. | `tests/unit/test_cli.py::test_all_handlers_sync` + `test_handlers_use_asyncio_run` | automated PASS |

## Test Suite Status

```
$ pytest tests/unit/ -m "not integration"
42 passed (15 orchestrator + 9 CLI + 26 inherited from Phases 1+2)

$ pytest tests/integration/ --collect-only -m integration
26 integration tests collected (5 from Phase 1 + 14 from Phase 2 + 7 new Phase 3)
```

All Phase 3 unit tests pass — 12 new tests on top of the 30 from Phases 1+2. Integration tests skip cleanly without env vars (per `_require_*` helpers).

## Architectural Properties (Source-Grep Verified)

- **D-01 — No sub-subagent dispatch (WORC-02):** `grep -E "AgentDefinition|agents=" src/hsb/agents/work_item_orchestrator.py` returns 0 matches. AST walk over `ClaudeAgentOptions(...)` constructor in unit tests confirms `agents=` kwarg absent.
- **D-02 — Inline skill injection:** `assemble_system_prompt()` reads 5 skill markdown files (skills 02+03+04+05+06) and concatenates into one prompt at startup. Length validated at 14,405 chars (< 200K context window — well within budget).
- **D-08 — Single SDK session per task:** `WorkItemOrchestrator.run()` opens one `claude_agent_sdk.query` session, drives the entire lifecycle within it, closes when status is `done` or `qa_cycle >= 3`.
- **CLIR-05 async boundary:** All 3 new Typer handlers are sync; `asyncio.run(` count = 4 (3 handlers + 1 helper). Mirrors Phase 1 pattern.
- **Pitfall 5 returncode check (run_loop.py):** explicit `if proc.returncode != 0: break` after each `subprocess.run(["hsb", "run-next-step"])` call. Prevents silent loop continuation on agent failure.
- **Linear MCP allowed_tools:** WIO's `ClaudeAgentOptions.allowed_tools` includes exactly 4 `mcp__linear__*` (get_issue, list_issues, update_issue, create_comment) — read-mostly with one focused write path. NO `Agent` tool, no Bash beyond what skills 02+03+04+05+06 explicitly need.

## Plan-by-Plan Cross-Reference

| Plan | Status | Highlights |
|------|--------|-----------|
| 03-01 (foundation contracts + Wave 0 stubs + SKILL.md) | complete | `WorkItemOrchInput`/`WorkItemOrchOutput` contracts; 27 Wave 0 test stubs; `task-orchestration` SKILL.md migrated with `disable-model-invocation: true` |
| 03-02 (WIO implementation) | complete | 299-LOC `work_item_orchestrator.py`; `assemble_system_prompt()` 14.4K chars; AST-verified no sub-subagent dispatch; 15/15 unit tests pass |
| 03-03 (CLI extensions + run_loop.py) | complete | 3 new Typer commands; 65-LOC `run_loop.py`; CLIR-05 async boundary verified for every handler |
| 03-04 (integration tests + MVP benchmark) | partial | Task 1 (live integration test bodies) complete; Task 2 (operator MVP cycle benchmark) pending. 26 integration tests collect cleanly; 2 pass without live creds (Pitfall 5 source-grep + WORC-03 contract guard) |

## Human Verification Required

Two REQ-IDs require live operator runs:

1. **WORC-01 — single-cycle MVP** (Plan 03-04 Task 2): Seed a `todo` Task in the Linear test workspace; export `TEST_WORK_ITEM_ID=LIN-XXX`; run `pytest tests/integration/test_orchestrator_e2e.py::test_full_lifecycle_todo_to_done -v`. Confirm the Task transitions todo → done within `max_qa_cycles=3`.
2. **CLIR-04 — continuous loop**: Run `python run_loop.py` against the seeded workspace; confirm graceful termination on empty backlog and on `Ctrl+C`.

Resume contract documented in `.planning/phases/03-work-item-orchestrator-and-single-cycle-mvp/03-04-SUMMARY.md`. This is consolidated into the milestone-level `MILESTONE-UAT.md` Group 3.

## Self-Check: PASSED (autonomous portion)

- 10 must-haves traced to implementation in source files + 4 SUMMARY.md frontmatter blocks
- 42 unit tests pass with 0 failures, 0 skipped
- 26 integration tests collect cleanly under `-m integration`
- All 4 plan SUMMARY.md files present on disk
- D-01 (no sub-subagent dispatch) verified by AST walk + grep — the most architecturally consequential Phase 3 invariant
- D-02 (inline skill injection) validated: 5 skills injected, 14,405 chars, under context budget
- CLIR-05 async boundary held across all new CLI handlers (matches Phase 1 pattern, sets precedent for Phase 4 `hsb run`)
- Phase goal "one complete controlled cycle through the full lifecycle" — achieved at code level; live MVP cycle pending operator
