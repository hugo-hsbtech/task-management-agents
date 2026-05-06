---
phase: 02-core-execution-agents
plan: 02
subsystem: backlog-agent
tags: [agent, backlog, linear, idempotency, two-layer-capability-boundary]
requires:
  - Plan 02-01 (test scaffolds + per-agent CLI skeleton)
  - Phase 1 src/hsb/agents/hooks.py LINEAR_HOOKS export
provides:
  - src/hsb/contracts/backlog.py — 7 Pydantic models (BacklogInput/Output, ProjectContext, EpicItem, UserStory, TaskItem, BacklogTraceability) with extra='forbid'
  - src/hsb/agents/backlog_agent.py — run_backlog_agent (sync) + _run_backlog_agent_async + BACKLOG_SYSTEM_PROMPT with IDEMPOTENCY RULE clause
  - .claude/skills/backlog-planning/SKILL.md — migrated skill with disable-model-invocation: true and 4-tool allow-list
  - hsb backlog create CLI command (--plan, --project-name, --repository, --stack)
  - 5 integration test bodies covering BKPK-01..05
affects:
  - src/hsb/cli/backlog.py (added @app.command("create") and 3 imports)
  - tests/integration/test_backlog_agent.py (replaced Wave 0 skip stubs with real bodies)
tech-stack:
  added: []
  patterns:
    - "Two-layer capability boundary: SKILL.md frontmatter allowed-tools mirrors ClaudeAgentOptions.allowed_tools exactly"
    - "IDEMPOTENCY system-prompt clause: 'Before creating any EPIC, call mcp__linear__list_issues' (Pitfall 1, BKPK-05)"
    - "Sync wrapper around async claude_agent_sdk.query loop via asyncio.run() at module boundary"
key-files:
  created:
    - src/hsb/contracts/backlog.py
    - src/hsb/agents/backlog_agent.py
    - .claude/skills/backlog-planning/SKILL.md
  modified:
    - src/hsb/cli/backlog.py
    - tests/integration/test_backlog_agent.py
key-decisions:
  - id: "02-02-D-A"
    summary: "EPIC title prefix '[EPIC] ' enforced in system prompt, not Pydantic regex"
    rationale: "LLM-generated titles vary across attempts; a regex on EpicItem.title would block valid recovery output during the 3-attempt validation/retry loop. The system prompt is the right enforcement layer because retries can recover from format issues."
  - id: "02-02-D-B"
    summary: "Synchronous run_backlog_agent wraps async core via asyncio.run() at boundary"
    rationale: "Mirrors Phase 1 Linear Agent pattern (D-04). Typer CLI is synchronous; integration tests are sync. asyncio.run is invoked exactly once at the module boundary — no nested event loops."
requirements-completed:
  - BKPK-01
  - BKPK-02
  - BKPK-03
  - BKPK-04
  - BKPK-05
duration: ~5 min
completed: 2026-05-06
---

# Phase 02 Plan 02: Backlog Agent — Summary

End-to-end Backlog Agent: Pydantic contracts, agent service with two-layer capability boundary, migrated SKILL.md with disable-model-invocation, CLI subcommand, and 5 integration test bodies.

## What was built

**Contracts** (`src/hsb/contracts/backlog.py`):
- 7 models mirroring AGENT-CONTRACTS.md §1
- BacklogOutput.epics has min_length=1
- All models declare extra='forbid'
- All 5 BKPK contract unit tests pass (no longer skipped)

**Agent service** (`src/hsb/agents/backlog_agent.py`):
- `run_backlog_agent(input: BacklogInput) -> BacklogOutput` synchronous entry point
- BACKLOG_SYSTEM_PROMPT contains the IDEMPOTENCY RULE clause: "Before creating any EPIC, call mcp__linear__list_issues" (verbatim, Pitfall 1 mitigation)
- ClaudeAgentOptions: model=`claude-opus-4-7`, mcp_servers={linear}, allowed_tools=[create_issue, list_issues, get_issue, Read], permission_mode=acceptEdits, max_turns=80, hooks=LINEAR_HOOKS
- 3-attempt validation/retry loop using BacklogOutput.model_validate

**Skill spec** (`.claude/skills/backlog-planning/SKILL.md`):
- Frontmatter: `disable-model-invocation: true` (Pitfall 5 mitigation)
- allowed-tools list mirrors ClaudeAgentOptions.allowed_tools exactly (4 entries)
- Body: verbatim copy of `skills/01-BACKLOG-PLANNING.md`

**CLI command** (`src/hsb/cli/backlog.py`):
- `hsb backlog create --plan <path> --project-name <name> --repository <url> [--stack ...]`
- Constructs BacklogInput, invokes run_backlog_agent, pretty-prints model_dump

**Integration tests** (`tests/integration/test_backlog_agent.py`):
- 5 real bodies (no longer skip stubs): test_parse_plan, test_create_epics, test_create_user_stories, test_create_tasks, test_idempotency
- Sample plan fixture with user-facing acceptance criteria
- Idempotency test: runs agent twice, asserts EPIC titles and count unchanged

## Two-layer capability boundary (verified)

Both layers list exactly: `mcp__linear__create_issue`, `mcp__linear__list_issues`, `mcp__linear__get_issue`, `Read`.

Forbidden tokens absent from `src/hsb/agents/backlog_agent.py`:
- `mcp__linear__update_issue` — absent
- `mcp__linear__*` wildcard — absent
- `"Edit"`, `"Write"` — absent
- `"Bash(...)"` — absent

Same set absent from `.claude/skills/backlog-planning/SKILL.md`.

## Verification results

| Check | Result |
|-------|--------|
| `pytest tests/unit/test_backlog_contract.py -v` | 5 passed |
| `from hsb.agents.backlog_agent import run_backlog_agent` | imports ok |
| `from hsb.contracts.backlog import ...` (7 exports) | imports ok |
| `from hsb.cli.backlog import app` | imports ok |
| `hsb backlog create --help` | resolves with 4 options + docstring |
| `pytest tests/ -m "not integration" -x` | 40 passed, 3 skipped, 23 deselected |
| `pytest tests/integration/test_backlog_agent.py --collect-only` | 5 tests collected |

## Deviations from Plan

None — all three tasks executed as written. Minor clarifying edit to docstring in `backlog_agent.py` to avoid the literal token `mcp__linear__update_issue` appearing as documentation (the negative-grep acceptance criterion would otherwise produce a false positive). Documentation now references "Linear update/delete" generically instead.

## Operator next steps

To run the full integration suite against a real Linear test workspace:

```bash
export ANTHROPIC_API_KEY=...
# Linear MCP token already configured by Phase 1 mcp-remote OAuth flow
pytest tests/integration/test_backlog_agent.py -v -m integration
```

Idempotency test (`test_idempotency`) creates EPICs in the configured Linear test team — operators should run it against a workspace they're willing to clean up afterward.

## Self-Check: PASSED

- Every BKPK requirement (01..05) has an implementation: contract field + agent behavior + system-prompt clause + integration test body
- Two-layer capability boundary verified by negative greps in both backlog_agent.py and SKILL.md
- IDEMPOTENCY RULE clause present in BACKLOG_SYSTEM_PROMPT verbatim
- disable-model-invocation: true in SKILL.md frontmatter
- All Phase 1 tests still pass (no regressions)
