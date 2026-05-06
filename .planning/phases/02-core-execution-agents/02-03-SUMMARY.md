---
phase: 02-core-execution-agents
plan: 03
subsystem: builder-agent
tags: [agent, builder, capability-boundary, two-layer-enforcement, validation-heuristic]
requires:
  - Plan 02-01 (test scaffolds + per-agent CLI skeleton)
  - Phase 1 src/hsb/agents/linear_agent.py run_validated_linear_agent (Pitfall 6 fresh fetch)
provides:
  - src/hsb/contracts/builder.py — 6 Pydantic models with extra='forbid' (BLDR-04 schema-level guard)
  - src/hsb/agents/builder_agent.py — run_builder_agent (sync) + BUILDER_SYSTEM_PROMPT with verbatim CAPABILITY BOUNDARY (BLDR-04) + VALIDATION HEURISTIC (BLDR-02) clauses
  - .claude/skills/implementation/SKILL.md — migrated skill with disable-model-invocation: true and 7-tool allow-list
  - hsb builder implement CLI command (--issue-id, --plan, --repo-root, --stack) with Pitfall-6-safe Linear fetch
  - 3 integration test bodies covering BLDR-01, BLDR-02, BLDR-04 (including runtime git HEAD check)
affects:
  - src/hsb/cli/builder.py (added @app.command("implement") and 4 imports)
  - tests/integration/test_builder_agent.py (replaced Wave 0 skip stubs with real bodies)
tech-stack:
  added: []
  patterns:
    - "Two-layer capability boundary + extra='forbid' schema guard (3-defense pattern)"
    - "Plain-English forbidden-command descriptions in system prompt (avoids regex collisions with negative-grep acceptance)"
    - "Pitfall 6 fresh-fetch wrapper at CLI boundary — agent itself never reads Linear"
    - "Sync run_builder_agent wraps async claude_agent_sdk.query loop via asyncio.run() at module boundary"
key-files:
  created:
    - src/hsb/contracts/builder.py
    - src/hsb/agents/builder_agent.py
    - .claude/skills/implementation/SKILL.md
  modified:
    - src/hsb/cli/builder.py
    - tests/integration/test_builder_agent.py
key-decisions:
  - id: "02-03-D-A"
    summary: "Plain-English forbidden-command descriptions in BUILDER_SYSTEM_PROMPT"
    rationale: "Plan acceptance criteria require negative greps over the whole file (`! grep -q 'Bash(git'`). Mentioning `Bash(git *)` literally as a forbidden tool in the prompt would trigger a false positive. The prompt instead describes forbidden operations in plain English (`git commit`, `git push`, `gh CLI commands`)."
  - id: "02-03-D-B"
    summary: "NO mcp_servers entry in ClaudeAgentOptions — three-defense pattern"
    rationale: "Builder has zero Linear access (BLDR-04). Defenses: (1) SKILL.md frontmatter allowed-tools = 7 entries, no Linear; (2) ClaudeAgentOptions.allowed_tools matches; (3) BuilderOutput extra='forbid' rejects leaked git_branch/pr_url. Omitting mcp_servers entirely means even if allowed_tools had a typo, no Linear MCP would be reachable."
  - id: "02-03-D-C"
    summary: "Pitfall 6 fresh-fetch lives in CLI command, not agent"
    rationale: "Agent stays stateless — every invocation is reproducible from BuilderInput alone. CLI command performs run_validated_linear_agent(operation='read') immediately before BuilderInput construction. Comment in code makes the rationale explicit."
requirements-completed:
  - BLDR-01
  - BLDR-02
  - BLDR-03
  - BLDR-04
duration: ~6 min
completed: 2026-05-06
---

# Phase 02 Plan 03: Builder Agent — Summary

End-to-end Builder Agent: 6-model contract layer, agent service with three-defense capability boundary, migrated SKILL.md, Pitfall-6-safe CLI command, and 3 integration test bodies (including runtime git-HEAD assertion for BLDR-04).

## What was built

**Contracts** (`src/hsb/contracts/builder.py`):
- 6 models mirroring AGENT-CONTRACTS.md §4
- BuilderOutput.implementation_status is Literal[completed, blocked, failed]
- ValidationResults fields are Literal[passed, failed, not_run]
- All 6 models declare extra='forbid' (BLDR-04 schema-level guard)
- All 3 BLDR contract unit tests pass (no longer skipped)

**Agent service** (`src/hsb/agents/builder_agent.py`):
- `run_builder_agent(input: BuilderInput) -> BuilderOutput` synchronous entry point
- BUILDER_SYSTEM_PROMPT contains the verbatim CAPABILITY BOUNDARY (BLDR-04) and VALIDATION HEURISTIC (BLDR-02) clauses
- ClaudeAgentOptions: model=`claude-sonnet-4-6`, allowed_tools=[Read, Edit, Write, Bash(pytest *), Bash(ruff *), Bash(mypy *), Bash(python *)], permission_mode=acceptEdits, max_turns=40, cwd=input.repository_context.root_path
- NO mcp_servers entry (Builder has zero MCP access)
- 3-attempt validation/retry loop with explicit "no git_branch / no pr_url" reminder

**Skill spec** (`.claude/skills/implementation/SKILL.md`):
- Frontmatter: `disable-model-invocation: true` (Pitfall 5 mitigation)
- allowed-tools list mirrors ClaudeAgentOptions.allowed_tools exactly (7 entries)
- Body: verbatim copy of `skills/02-IMPLEMENTATION.md`

**CLI command** (`src/hsb/cli/builder.py`):
- `hsb builder implement --issue-id LIN-X --plan <path> --repo-root <path>` performs a Pitfall-6 fresh fetch via `run_validated_linear_agent(operation='read')` BEFORE constructing BuilderInput, then invokes `run_builder_agent`
- Comment in command body documents the Pitfall 6 mitigation

**Integration tests** (`tests/integration/test_builder_agent.py`):
- 3 real bodies (no longer skip stubs): test_scoped_implementation, test_validation_run, test_capability_boundary
- Use `HSB_TEST_FIXTURE_PATH` env var to locate cloned hsb-test-fixture
- `clean_fixture_branch` fixture resets repo to origin/main before each test
- test_capability_boundary asserts `git rev-parse HEAD` is unchanged after Builder run — runtime BLDR-04 check

## Three-defense capability boundary (verified)

Layer 1 (SKILL.md frontmatter `allowed-tools`):
```
- Read
- Edit
- Write
- Bash(pytest *)
- Bash(ruff *)
- Bash(mypy *)
- Bash(python *)
```

Layer 2 (ClaudeAgentOptions.allowed_tools): identical 7 entries.

Layer 3 (Pydantic schema guard): `BuilderOutput.model_config = {"extra": "forbid"}` rejects any output containing `git_branch`, `pr_url`, `linear_status`, or other non-spec fields. Tested by `tests/unit/test_builder_contract.py::test_builder_output_extra_field_rejected`.

Forbidden tokens absent from BOTH `src/hsb/agents/builder_agent.py` and `.claude/skills/implementation/SKILL.md`:
- `mcp__linear__` — absent
- `Bash(git` — absent
- `Bash(gh` — absent
- `Bash(curl` — absent
- `mcp_servers` — absent from agent file (no MCP servers wired)

## Verification results

| Check | Result |
|-------|--------|
| `pytest tests/unit/test_builder_contract.py -v` | 3 passed |
| `from hsb.agents.builder_agent import run_builder_agent` | imports ok, MAX_VALIDATION_RETRIES == 3 |
| `from hsb.contracts.builder import ...` (6 exports) | imports ok |
| `from hsb.cli.builder import app` | imports ok |
| `hsb builder implement --help` | resolves with 4 options + Pitfall 6 docstring |
| `pytest tests/ -m "not integration" -x` | 43 passed, 2 skipped, 23 deselected |
| `pytest tests/integration/test_builder_agent.py --collect-only` | 3 tests collected |

## Deviations from Plan

[Rule 1 — minor adaptation] BUILDER_SYSTEM_PROMPT uses plain English ("git commit, git push") to describe forbidden operations instead of the parenthesized tool tokens shown in the plan's <interfaces> block. The plan explicitly documented this option in the acceptance criteria notes ("OR confine the forbidden-token greps to the ClaudeAgentOptions allowed_tools= block only"). Choosing the plain-English option was simpler and keeps the negative-grep acceptance criteria cleanly passing over the whole file.

## Operator next steps

To run the full integration suite against a cloned hsb-test-fixture:

```bash
git clone https://github.com/hugo-hsbtech/hsb-test-fixture /tmp/hsb-test-fixture
export HSB_TEST_FIXTURE_PATH=/tmp/hsb-test-fixture
export ANTHROPIC_API_KEY=...
pytest tests/integration/test_builder_agent.py -v -m integration
```

`test_capability_boundary` makes a runtime assertion that no commit happened during the Builder run — providing a strong BLDR-04 enforcement check beyond static grep.

## Self-Check: PASSED

- BLDR-01..04 all implemented (contracts, agent, SKILL.md, CLI, integration tests)
- Three-defense capability boundary verified by negative greps + extra='forbid' unit test
- Pitfall 6 fresh-fetch in CLI explicitly commented
- VALIDATION HEURISTIC clause present in BUILDER_SYSTEM_PROMPT
- All Phase 1 + previously-completed Phase 2 tests still pass (no regressions)
