---
phase: 01-foundation-and-linear-integration
plan: 03
subsystem: agent-hooks
tags: [claude-agent-sdk, hooks, retry, backoff, audit-log, precompact, LINR-05]

requires:
  - phase: 01-01
    provides: src/hsb/agents/__init__.py, claude-agent-sdk dep in pyproject, .claude dir gitignored
provides:
  - linear_retry_hook (PostToolUseFailure) with exponential backoff (1s/2s/4s) and 3-retry cap
  - linear_audit_hook (PostToolUse) writing JSON-line audit log per Linear MCP call
  - pre_compact_handler (PreCompact) archiving transcript to .claude/compaction_archive_*.jsonl
  - enforce_list_filters (PreToolUse) denying unfiltered mcp__linear__list_issues
  - LINEAR_HOOKS dict bundling all 4 into HookMatcher lists ready for ClaudeAgentOptions(hooks=...)
  - tests/test_hooks.py — 13 unit tests covering timing, cap, audit log, filter, PreCompact behavior
affects: [01-04 (run_linear_agent imports LINEAR_HOOKS), all phase 2 agent plans (template for per-agent hook bundles)]

tech-stack:
  added: []
  patterns:
    - "PostToolUseFailure hook for transient retry instead of in-prompt retry (avoids context overhead)"
    - "module-level _retry_counts state keyed by tool_use_id (cleared on success / cap / mismatch)"
    - "PreToolUse permissionDecision='deny' to block unsafe tool calls and force agent self-correction"
    - "PreCompact archive with best-effort copy + agent re-read instruction"
    - "monkeypatched asyncio.sleep for deterministic timing tests"

key-files:
  created:
    - src/hsb/agents/hooks.py
    - tests/test_hooks.py
  modified: []

key-decisions:
  - "Used patched asyncio.sleep in test_retry_backoff_first_attempt to avoid real-time delay (test-only deviation; production behavior unchanged)"
  - "MAX_RETRIES = 3, BASE_DELAY_SECONDS = 1.0 — exact LINR-05 acceptance criterion values, not parametrized"
  - "PreCompact has no matcher (fires for every compaction event, not just Linear)"

patterns-established:
  - "Pattern 1: hook signature `async (input_data: dict, tool_use_id: str | None, context) -> dict` — return {} for no-op"
  - "Pattern 2: filter early via tool_name.startswith() guard so non-Linear tools bypass cleanly"
  - "Pattern 3: bound audit log entry size with json.dumps(...)[:2000] truncation"

requirements-completed:
  - LINR-05

duration: 6min
completed: 2026-05-06
---

# Phase 01-03: Claude Agent SDK Lifecycle Hooks Summary

**LINR-05 delivered: exponential backoff with hard 3-retry cap, JSON-line audit log, PreCompact transcript archive, and PreToolUse filter on `list_issues` — all 4 hooks bundled in LINEAR_HOOKS, 13 unit tests prove timing and behavior.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-06
- **Completed:** 2026-05-06
- **Tasks:** 2
- **Files modified:** 2 (all created)

## Accomplishments
- `linear_retry_hook` runs PostToolUseFailure with delays 1s/2s/4s and stops at 3 attempts (Pitfall 3 mitigated)
- `linear_audit_hook` writes one JSON line per `mcp__linear__*` PostToolUse to `.claude/linear_audit.log` (LINR-05 audit gate)
- `pre_compact_handler` runs PreCompact, archives transcript, and instructs agent to re-read state (Pitfall 6 mitigated)
- `enforce_list_filters` runs PreToolUse for `mcp__linear__list_issues` and denies the call if `teamId` and `projectId` are both absent (Pitfall 4 mitigated)
- `LINEAR_HOOKS` bundles all 4 into `HookMatcher` lists keyed by event type — Plan 04 imports this directly
- 13 unit tests pass (timing 1/2/4s deterministic via patched asyncio.sleep, cap fires on 4th call, audit log JSON shape, filter denial logic, PreCompact archive)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement src/hsb/agents/hooks.py with all 4 hooks and LINEAR_HOOKS bundle** - `8a0f7c5` (feat)
2. **Task 2: Write tests/test_hooks.py covering retry timing, cap, audit log, list filter, and PreCompact** - `3426b38` (test)

## Files Created/Modified

- `src/hsb/agents/hooks.py` — 147 lines; 4 hook coroutines + module-level `_retry_counts` + `LINEAR_HOOKS` registry
- `tests/test_hooks.py` — 186 lines; 13 async pytest tests with monkeypatched sleep for deterministic timing

## Decisions Made

- The plan's `<behavior>` text for Test 1 included "waits 1.0s before returning" — to keep the suite fast and deterministic I patched `asyncio.sleep` in Test 1 too (matching how Tests 2 and 3 work). Production behavior is unchanged; the patched test still asserts the systemMessage contents and the recorded delay value.

## Deviations from Plan

None — plan executed exactly as written. The single decision above is a test-determinism choice that does not change production behavior.

## Verification

- `python3 -c "from hsb.agents.hooks import linear_retry_hook, linear_audit_hook, pre_compact_handler, enforce_list_filters, LINEAR_HOOKS, MAX_RETRIES, BASE_DELAY_SECONDS, AUDIT_LOG_PATH; assert MAX_RETRIES == 3; assert BASE_DELAY_SECONDS == 1.0; assert set(LINEAR_HOOKS.keys()) == {'PostToolUseFailure', 'PostToolUse', 'PreCompact', 'PreToolUse'}"` — exits 0
- `pytest tests/test_hooks.py -x -v` — 13 passed in 0.52s
- `pytest tests/test_contracts.py tests/test_hooks.py -x` (Wave 2 sampling-rate gate) — 24 passed in 0.40s

## Threats Mitigated

| Threat ID | Status | Verification |
|-----------|--------|--------------|
| T-03-01 (retry storm) | Mitigated | MAX_RETRIES=3 hard cap; `test_retry_cap_at_max` passes |
| T-03-02 (context overflow on unfiltered list) | Mitigated | `enforce_list_filters` returns `permissionDecision: "deny"`; `test_enforce_list_filters_denies_unfiltered` passes |
| T-03-03 (audit log payload bloat) | Mitigated | `output_repr = json.dumps(output)[:2000]` truncates; audit path gitignored |
| T-03-04 (lost transcript on compaction) | Mitigated | `pre_compact_handler` copies transcript to archive path; `test_pre_compact_handler_archives_transcript` passes |
| T-03-05 (no audit trail) | Mitigated | `linear_audit_hook` appends JSON line on every PostToolUse; `test_audit_hook_writes_log_line` passes |
| T-03-06 (synchronous time.sleep blocks event loop) | Mitigated | All hooks use `await asyncio.sleep`; acceptance grep + tests confirm |

## Next Phase Readiness

- Plan 01-04 can now `from hsb.agents.hooks import LINEAR_HOOKS` and pass it directly to `ClaudeAgentOptions(hooks=LINEAR_HOOKS)`
- Phase 2 agent plans can copy this module shape for per-agent hook bundles (`backlog_hooks.py`, `qa_hooks.py`, etc.)

## Self-Check: PASSED
