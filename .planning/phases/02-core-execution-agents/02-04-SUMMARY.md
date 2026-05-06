---
phase: 02-core-execution-agents
plan: 04
subsystem: git-agent
tags: [agent, git, gh, stacked-pr, rebase-stack, capability-boundary]
requires:
  - Plan 02-01 (test scaffolds + per-agent CLI skeleton)
provides:
  - src/hsb/contracts/git.py — 4 Pydantic models with extra='forbid' (GITA-05 schema-level guard)
  - src/hsb/agents/git_agent.py — run_git_agent + GIT_SYSTEM_PROMPT (D-07/D-08/Pitfall 3/Pitfall 4 mitigations)
  - .claude/skills/git-pr-management/SKILL.md — migrated skill with disable-model-invocation: true and 12-tool allow-list
  - hsb git create-pr CLI command (--issue-id, --epic-id, --impl-output)
  - hsb git rebase-stack CLI command (--epic-branch, --just-merged)
  - 4 integration test bodies covering GITA-01..04
affects:
  - src/hsb/cli/git.py (added 2 @app.command decorators and 4 imports)
  - tests/integration/test_git_agent.py (replaced Wave 0 skip stubs with real bodies)
tech-stack:
  added: []
  patterns:
    - "Two-layer capability boundary with 12 enumerated Bash subcommand patterns (no merge variants, no bare --force)"
    - "Pitfall 3 mitigation: --force-with-lease only (no `git push --force *)` in allowed_tools)"
    - "Pitfall 4 mitigation: --limit 100 mandated in REBASE_STACK gh pr list call"
    - "D-07: All task PRs target EPIC branch directly (not main, not other tasks)"
    - "D-08: REBASE_STACK uses git rebase --onto + git push --force-with-lease per sibling"
key-files:
  created:
    - src/hsb/contracts/git.py
    - src/hsb/agents/git_agent.py
    - .claude/skills/git-pr-management/SKILL.md
  modified:
    - src/hsb/cli/git.py
    - tests/integration/test_git_agent.py
key-decisions:
  - id: "02-04-D-A"
    summary: "Plain-English forbidden-command descriptions in GIT_SYSTEM_PROMPT"
    rationale: "Per Plan 02-03 precedent, plain-English forbidden descriptions ('no gh pr merge, no git merge') avoid false positives in negative-grep acceptance criteria over the whole file. The 12 allowed Bash patterns live exclusively in ClaudeAgentOptions.allowed_tools and SKILL.md frontmatter."
  - id: "02-04-D-B"
    summary: "REBASE_STACK exposed as separate CLI command rather than auto-trigger"
    rationale: "D-08 says REBASE_STACK runs after a sibling merge. Phase 2 has no orchestrator yet, so the operator triggers it manually via `hsb git rebase-stack --epic-branch ... --just-merged ...`. Phase 4 parallel mode will wire the orchestrator to call it automatically."
requirements-completed:
  - GITA-01
  - GITA-02
  - GITA-03
  - GITA-04
  - GITA-05
duration: ~5 min
completed: 2026-05-06
---

# Phase 02 Plan 04: Git Agent — Summary

End-to-end Git Agent: 4-model contract layer, agent service with strict 12-tool capability boundary, migrated SKILL.md with --force-with-lease only, two CLI commands (create-pr + rebase-stack), and 4 integration test bodies.

## What was built

**Contracts** (`src/hsb/contracts/git.py`):
- 4 models mirroring AGENT-CONTRACTS.md §5: GitInput, GitOutput, ExistingPRContext, PullRequest
- All declare extra='forbid' (GITA-05 schema-level guard)
- All 5 GITA contract unit tests pass (including test_no_merge_in_allowed_tools after SKILL.md exists)

**Agent service** (`src/hsb/agents/git_agent.py`):
- `run_git_agent(input: GitInput) -> GitOutput` synchronous entry point
- GIT_SYSTEM_PROMPT contains: BRANCH NAMING (GITA-01), PR TITLE (GITA-03), PR BASE (D-07: target EPIC branch directly, NEVER target main), REBASE_STACK (GITA-04, D-08) with `--limit 100` (Pitfall 4) and `--force-with-lease` (Pitfall 3) mandates, CAPABILITY BOUNDARY (GITA-05)
- ClaudeAgentOptions: model=`claude-sonnet-4-6`, exactly 12 allowed_tools entries, max_turns=30
- 3-attempt validation/retry loop

**Skill spec** (`.claude/skills/git-pr-management/SKILL.md`):
- Frontmatter: `disable-model-invocation: true` (Pitfall 5)
- allowed-tools list mirrors ClaudeAgentOptions exactly (12 entries)
- Body: verbatim copy of `skills/04-GIT-PR-MANAGEMENT.md`

**CLI commands** (`src/hsb/cli/git.py`):
- `hsb git create-pr --issue-id LIN-X --epic-id LIN-Y --impl-output <path>` — reads BuilderOutput JSON, constructs GitInput, runs agent
- `hsb git rebase-stack --epic-branch ... --just-merged ...` — invokes REBASE_STACK pattern with sentinel work_item_id

**Integration tests** (`tests/integration/test_git_agent.py`):
- 4 real bodies: test_branch_naming, test_pr_base, test_pr_title, test_rebase_stack
- `epic_branch_setup` fixture creates `epic/LIN-TEST-100` in fixture repo if absent
- Skip cleanly when `HSB_TEST_FIXTURE_PATH` is unset

## Two-layer capability boundary (verified)

The 12 allowed Bash patterns (identical in both layers):
```
- Bash(gh pr create *)
- Bash(gh pr list *)
- Bash(gh pr view *)
- Bash(gh pr diff *)
- Bash(git checkout *)
- Bash(git push --force-with-lease *)
- Bash(git rebase *)
- Bash(git log *)
- Bash(git fetch *)
- Bash(git add *)
- Bash(git commit *)
- Bash(git status *)
```

Forbidden tokens absent from BOTH `src/hsb/agents/git_agent.py` and `.claude/skills/git-pr-management/SKILL.md`:
- `Bash(git merge` — absent
- `Bash(gh pr merge` — absent
- `Bash(git push --force *)` (bare --force) — absent
- `Bash(git push -f` — absent
- `"Edit"`, `"Write"` — absent
- `mcp__linear__` — absent

## Pitfall 3 + Pitfall 4 mitigations (verified)

- Literal `--limit 100` present in GIT_SYSTEM_PROMPT (gh pr list pagination cap)
- Literal `--force-with-lease` present and is the ONLY push-force variant in the allow-list

## Verification results

| Check | Result |
|-------|--------|
| `pytest tests/unit/test_git_contract.py -v` | 5 passed |
| `from hsb.agents.git_agent import run_git_agent` | imports ok, MAX_VALIDATION_RETRIES == 3 |
| `from hsb.contracts.git import ...` (4 exports) | imports ok |
| `from hsb.cli.git import app` | imports ok |
| `hsb git create-pr --help` | resolves with 3 options + GITA-01..03 docstring |
| `hsb git rebase-stack --help` | resolves with 2 options + Pitfall 3/4 docstring |
| `pytest tests/ -m "not integration" -x` | 48 passed, 1 skipped, 23 deselected |
| `pytest tests/integration/test_git_agent.py --collect-only` | 4 tests collected |

## Deviations from Plan

[Rule 1 — minor adaptation] GIT_SYSTEM_PROMPT uses plain English ("no gh pr merge, no git merge") to describe forbidden operations — same precedent as Plan 02-03 to avoid false positives in negative-grep acceptance criteria. The plan acknowledged this option ("only system prompt mentions them as forbidden in plain English, not as tool tokens").

## Operator next steps

To run the full integration suite against a cloned hsb-test-fixture:

```bash
git clone https://github.com/hugo-hsbtech/hsb-test-fixture /tmp/hsb-test-fixture
export HSB_TEST_FIXTURE_PATH=/tmp/hsb-test-fixture
export ANTHROPIC_API_KEY=...
gh auth login   # ensure repo scope
pytest tests/integration/test_git_agent.py -v -m integration
```

The `epic_branch_setup` fixture creates `epic/LIN-TEST-100` automatically; subsequent tests reuse it. After running, the operator can clean up with `gh pr list --base epic/LIN-TEST-100` and close test PRs.

## Self-Check: PASSED

- GITA-01..05 all implemented (contracts, agent, SKILL.md, 2 CLIs, 4 integration tests)
- Two-layer capability boundary verified by 12 positive greps + 6 negative greps in both files
- Pitfall 3 (--force-with-lease) and Pitfall 4 (--limit 100) mandates verified in system prompt
- D-07 enforcement strings present ("All task PRs target the EPIC branch directly", "NEVER target main directly")
- All 5 unit tests pass; all Phase 1 tests still pass (no regressions)
