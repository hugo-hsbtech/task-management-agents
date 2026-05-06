---
phase: 01-foundation-and-linear-integration
plan: 04
subsystem: linear-agent
tags: [claude-agent-sdk, query, mcp, linear, validation, optimistic-lock, LINR-05]

requires:
  - phase: 01-01
    provides: src/hsb/agents/, claude-agent-sdk + python-dotenv deps, .mcp.json
  - phase: 01-02
    provides: LinearOutput, LinearInput pydantic contracts with extra=forbid + regex constraints
  - phase: 01-03
    provides: LINEAR_HOOKS dict (PostToolUseFailure, PostToolUse, PreCompact, PreToolUse)
provides:
  - run_linear_agent(prompt) — async wrapper around claude_agent_sdk.query with Linear MCP server, all 4 hooks, mcp__linear__* allowed_tools, max_turns=20
  - run_validated_linear_agent(operation, payload) — pydantic-validated entry point with up to 3 self-correction retries on JSON-parse or ValidationError
  - LINEAR_SYSTEM_PROMPT — encodes LINR-05 optimistic-lock procedure (read updatedAt → write → re-read updatedAt → verify post>pre), filter rule, no-reparenting rule, JSON-only output
  - MAX_VALIDATION_RETRIES = 3 module constant
  - tests/test_linear_agent.py — 6 unit tests covering happy path, markdown extraction, retry recovery, MAX cap, pydantic validation failure, None handling
affects: [01-05 (CLI imports run_validated_linear_agent), all phase 2+ agent plans (template for ClaudeAgentOptions wiring)]

tech-stack:
  added: []
  patterns:
    - "ClaudeAgentOptions with MCP server + allowed_tools + hooks + system_prompt + max_turns"
    - "Async generator iteration over query() yields SystemMessage(init), AssistantMessage(streamed blocks), ResultMessage(success|error)"
    - "MCP connectivity gate at SystemMessage(subtype='init') — raise if any server status != connected"
    - "Validation-retry loop: parse JSON, validate against pydantic, on failure inject error details into next prompt for self-correction"
    - "Markdown JSON extraction: result_text.index('{') → result_text.rindex('}')+1 (handles ```json wrapping)"

key-files:
  created:
    - src/hsb/agents/linear_agent.py
    - tests/test_linear_agent.py
  modified: []

key-decisions:
  - "Used model='claude-sonnet-4-6' — AI-SPEC.md mandate for tool-heavy agents (not haiku/opus)"
  - "permission_mode='acceptEdits' KEPT alongside allowed_tools=['mcp__linear__*'] — both required since acceptEdits doesn't cover MCP (Pitfall 2)"
  - "load_dotenv() at module level — picks up ANTHROPIC_API_KEY from .env without explicit caller setup"
  - "asyncio.run() ONLY in __main__ smoke block — never inside coroutine (Pitfall 5)"

patterns-established:
  - "Pattern 1: Two-tier agent entry point — raw run_*_agent for query loop + run_validated_*_agent for pydantic-gated boundary"
  - "Pattern 2: Inject ValidationError.json(indent=2) into the next-attempt prompt for self-correction"
  - "Pattern 3: Stream tool calls and assistant text to stdout for operator visibility during long-running queries"

requirements-completed:
  - LINR-05

duration: 7min
completed: 2026-05-06
---

# Phase 01-04: Linear Agent Service Layer Summary

**LINR-05 fully delivered: `run_linear_agent` wires the Linear MCP server, all 4 hooks, and the optimistic-lock system prompt into one Claude Agent SDK query loop; `run_validated_linear_agent` adds pydantic-gated self-correction with a 3-retry cap. 6 unit tests pass; combined Wave 3 gate (30 tests) green.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-06
- **Completed:** 2026-05-06
- **Tasks:** 1
- **Files modified:** 2 (all created)

## Accomplishments
- `run_linear_agent` builds `ClaudeAgentOptions` with model="claude-sonnet-4-6", mcp_servers={"linear": npx-mcp-remote}, allowed_tools=["mcp__linear__*"], permission_mode="acceptEdits", system_prompt=LINEAR_SYSTEM_PROMPT, max_turns=20, hooks=LINEAR_HOOKS
- SystemMessage(subtype="init") connectivity gate raises RuntimeError if any MCP server status != connected (T-04-01 mitigation)
- AssistantMessage streams text and tool names for operator visibility
- ResultMessage success-only path captures result_text; non-success raises RuntimeError
- `run_validated_linear_agent` loops up to MAX_VALIDATION_RETRIES=3, extracting JSON via index/rindex slicing (handles markdown wrapping), validating with `LinearOutput.model_validate`, and on failure appending the parse error or `ValidationError.json(indent=2)` to the next prompt
- `LINEAR_SYSTEM_PROMPT` explicitly instructs the 4-step optimistic-lock sequence (read updatedAt → write → re-read updatedAt → verify post>pre), forbids unfiltered list_issues, forbids reparenting, and requires JSON-only output
- 6 unit tests pass (happy, markdown extraction, recover-after-2-bad-attempts, MAX-retry cap, pydantic validation failure, None handling)
- Wave 3 combined gate: `pytest tests/test_contracts.py tests/test_hooks.py tests/test_linear_agent.py -x` → 30 passed

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement run_linear_agent and run_validated_linear_agent in src/hsb/agents/linear_agent.py** - `20fb1b5` (feat)

## Files Created/Modified

- `src/hsb/agents/linear_agent.py` — 168 lines; module-level constants, LINEAR_SYSTEM_PROMPT (~17 lines), `run_linear_agent` (45 lines async generator iteration), `run_validated_linear_agent` (50 lines retry loop), `__main__` smoke entry (10 lines)
- `tests/test_linear_agent.py` — 113 lines; 6 async tests with `patch.object(linear_agent, "run_linear_agent", new=AsyncMock(...))` to mock the SDK boundary

## Decisions Made

None — followed plan as specified. All four "DO NOT" constraints honored:
- No `mcp__claude_ai_Linear__` prefix anywhere (Pitfall 1)
- `allowed_tools=["mcp__linear__*"]` set alongside `permission_mode="acceptEdits"` (Pitfall 2)
- `model="claude-sonnet-4-6"` as required by AI-SPEC §4
- `asyncio.run()` only in `__main__` smoke block (Pitfall 5)

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `python3 -c "from hsb.agents.linear_agent import run_linear_agent, run_validated_linear_agent, MAX_VALIDATION_RETRIES, LINEAR_SYSTEM_PROMPT"` — exits 0
- All acceptance grep checks pass:
  - `from hsb.agents.hooks import LINEAR_HOOKS` ✓
  - `from hsb.contracts.linear import LinearOutput` ✓
  - `MAX_VALIDATION_RETRIES = 3` ✓
  - `model="claude-sonnet-4-6"` ✓
  - `allowed_tools=["mcp__linear__*"]` ✓
  - `max_turns=20` ✓
  - `hooks=LINEAR_HOOKS` ✓
  - `updatedAt` in system prompt ✓
  - `mcp-remote` and `https://mcp.linear.app/mcp` ✓
  - `! grep mcp__claude_ai_Linear__` (NEGATIVE) ✓
  - `load_dotenv()` ✓
  - `permission_mode="acceptEdits"` ✓
- `pytest tests/test_linear_agent.py -x` — 6 passed
- `pytest tests/test_contracts.py tests/test_hooks.py tests/test_linear_agent.py -x` — 30 passed (Wave 3 commit gate)

## Threats Mitigated

| Threat ID | Status | Verification |
|-----------|--------|--------------|
| T-04-01 (wrong MCP prefix → silent tool-not-found) | Mitigated | Negative grep + SystemMessage(init) connectivity gate raises RuntimeError if mcp_server status != connected |
| T-04-02 (apparent success with empty linear_entities) | Mitigated | LinearOutput regex on id/url + extra=forbid; system prompt requires post-write re-read |
| T-04-03 (stale updatedAt — concurrent overwrite) | Mitigated | LINEAR_SYSTEM_PROMPT prescribes immediate-before-write read; audit log (Plan 03) records every call |
| T-04-04 (permission_mode misread to cover MCP) | Mitigated | allowed_tools explicitly set; tested by acceptance grep |
| T-04-05 (ValidationError text injection) | Accepted | Internal operator tool; pydantic output is structured |
| T-04-06 (failure with no captured result) | Mitigated | Each attempt logs WARNING; final failure raises ValueError with last_error included; audit log captures every Linear call |
| T-04-07 (unbounded validation-retry loop) | Mitigated | MAX_VALIDATION_RETRIES=3 hard cap; tested by `test_validated_agent_raises_after_max_retries_invalid_json` |

## Next Phase Readiness

- Plan 01-05 can now `from hsb.agents.linear_agent import run_validated_linear_agent` and call it from each typer command (create-issue, update-issue, add-comment, link-pr)
- Plan 01-05's integration test will exercise `run_linear_agent` end-to-end with the live Linear MCP server (one-time OAuth via human checkpoint)
- Phase 2 plans can copy this module's shape (ClaudeAgentOptions wiring + validation-retry wrapper) for builder_agent.py, qa_agent.py, etc.

## Self-Check: PASSED
