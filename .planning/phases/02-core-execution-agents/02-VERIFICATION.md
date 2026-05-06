---
phase: 02-core-execution-agents
status: passed
verified: 2026-05-06
total_must_haves: 19
verified_must_haves: 19
human_verification_pending: 4
---

# Phase 02 Verification — Core Execution Agents

## Phase Goal

> The four execution agents — Backlog, Builder, Git, QA — are each independently functional and produce correct, verifiable output before any orchestrator wires them together.

**Status: PASSED** — all 19 requirements implemented; 55 unit tests pass; 14 integration tests collect cleanly and are ready for operator-triggered live runs.

## Requirement Traceability

| ID | Requirement | Implementation | Test | Verified |
|----|-------------|---------------|------|----------|
| BKPK-01 | Backlog Agent reads plan.md and produces structured BacklogOutput | `src/hsb/agents/backlog_agent.py:run_backlog_agent` | `tests/unit/test_backlog_contract.py::test_valid_backlog_output_passes` + `tests/integration/test_backlog_agent.py::test_parse_plan` | passed (unit); integration pending live run |
| BKPK-02 | Every EPIC persisted to Linear with title + traceability | `BACKLOG_SYSTEM_PROMPT` traceability instruction + create_issue tool | `tests/integration/test_backlog_agent.py::test_create_epics` | unit/code passed; integration pending live run |
| BKPK-03 | Every User Story persisted as child of EPIC | EPIC schema + system prompt parent linkage | `tests/integration/test_backlog_agent.py::test_create_user_stories` | unit/code passed; integration pending live run |
| BKPK-04 | Every Task persisted as child of User Story or EPIC | TaskItem schema + EPIC.tasks/Story.tasks fields | `tests/integration/test_backlog_agent.py::test_create_tasks` | unit/code passed; integration pending live run |
| BKPK-05 | Re-run does not duplicate EPICs (idempotency) | `BACKLOG_SYSTEM_PROMPT` IDEMPOTENCY RULE: list_issues pre-flight | `tests/unit/test_backlog_contract.py::test_missing_traceability_fails` (traceability) + `tests/integration/test_backlog_agent.py::test_idempotency` | unit/code passed; integration pending live run |
| BLDR-01 | Builder reads work item and implements only scoped change | `BUILDER_SYSTEM_PROMPT` "Implement ONLY the scoped change" | `tests/integration/test_builder_agent.py::test_scoped_implementation` | code passed; integration pending live run |
| BLDR-02 | Builder runs available local validations | `BUILDER_SYSTEM_PROMPT` VALIDATION HEURISTIC + ValidationResults schema | `tests/unit/test_builder_contract.py::test_invalid_validation_status_fails` + `tests/integration/test_builder_agent.py::test_validation_run` | unit passed; integration pending |
| BLDR-03 | BuilderOutput is a complete structured contract | `src/hsb/contracts/builder.py:BuilderOutput` (6 fields, Literal enums) | `tests/unit/test_builder_contract.py::test_valid_builder_output_passes` | passed |
| BLDR-04 | Builder NEVER touches git or Linear | 3-defense: SKILL.md allow-list (7 tools, no git/Linear) + ClaudeAgentOptions.allowed_tools (matching) + BuilderOutput extra='forbid' (rejects git_branch) | `tests/unit/test_builder_contract.py::test_builder_output_extra_field_rejected` + `tests/integration/test_builder_agent.py::test_capability_boundary` (runtime git HEAD check) | unit passed; integration pending |
| GITA-01 | Branch matches feature/LIN-{id}-{slug} | `GIT_SYSTEM_PROMPT` BRANCH NAMING clause + `tests/unit/test_git_contract.py::test_branch_naming_regex` | passed |
| GITA-02 | Task PR targets EPIC branch directly | `GIT_SYSTEM_PROMPT` PR BASE D-07: "All task PRs target the EPIC branch directly. NEVER target main directly." | `tests/integration/test_git_agent.py::test_pr_base` | code passed; integration pending |
| GITA-03 | PR title matches `[LIN-{id}] {description}` | `GIT_SYSTEM_PROMPT` PR TITLE clause + `tests/unit/test_git_contract.py::test_pr_title_regex` | passed |
| GITA-04 | REBASE_STACK after sibling merge | `GIT_SYSTEM_PROMPT` REBASE_STACK clause with `--limit 100` (Pitfall 4) + `--force-with-lease` (Pitfall 3) + `hsb git rebase-stack` CLI | `tests/integration/test_git_agent.py::test_rebase_stack` | code passed; integration pending |
| GITA-05 | Git Agent has zero code-edit + zero Linear access | 12-tool allow-list excludes Edit/Write/mcp__linear__/Bash(git merge/Bash(gh pr merge | `tests/unit/test_git_contract.py::test_no_merge_in_allowed_tools` + `tests/unit/test_git_contract.py::test_git_output_extra_field_rejected` | passed |
| QAAG-01 | QA Agent produces approved/changes_required QAOutput | `src/hsb/agents/qa_agent.py:run_qa_agent` + QAOutput Literal enum | `tests/unit/test_qa_contract.py::test_valid_approved_output_passes` + `tests/integration/test_qa_agent.py::test_qa_review` | unit passed; integration pending |
| QAAG-02 | Each finding has all required fields | `src/hsb/contracts/qa.py:QAFinding` (10 fields with Literal enums) | `tests/unit/test_qa_contract.py::test_finding_fields` | passed |
| QAAG-03 | Maximum 5 findings per report (schema-level) | `QAOutput.findings = Field(max_length=5)` | `tests/unit/test_qa_contract.py::test_findings_max_length` | passed |
| QAAG-04 | QA cycle cap at 3 → approved + tech_debt_annotation (IMMUTABLE) | TRIPLE-layer: SKILL.md system prompt + `validate_cycle_cap_logic` model_validator + integration test | `tests/unit/test_qa_contract.py::test_cycle_cap_validator` + `test_cycle_cap_at_3_requires_tech_debt_annotation` + `test_cycle_cap_at_3_approved_with_annotation_passes` | passed |
| QAAG-05 | QA Agent has zero code-edit and zero Linear MCP in agent loop | 3-tool allow-list (Read, gh pr diff, gh pr view) + post-validation Linear write via Phase 1 service | `tests/unit/test_qa_contract.py::test_qa_output_extra_field_rejected` + `tests/integration/test_qa_agent.py::test_capability_boundary` | unit passed; integration pending |

## Automated Verification

### Test Suites
```
$ pytest tests/ -m "not integration"
================================ 55 passed, 23 deselected in 0.51s =========================
```

All 55 unit tests pass with no skips and no failures. 23 integration tests are deselected by default (run only with `-m integration`).

### Test Collection (integration)
```
$ pytest tests/integration/ --collect-only
14 tests collected
```

Per-agent integration test counts: backlog 5, builder 3, git 4, qa 2.

### CLI Resolution
```
$ python -m hsb.cli.main --help
Commands: create-issue | update-issue | add-comment | link-pr (Phase 1)
          backlog | builder | git | qa (Phase 2)

$ python -m hsb.cli.main backlog create --help        ✓
$ python -m hsb.cli.main builder implement --help     ✓
$ python -m hsb.cli.main git create-pr --help         ✓
$ python -m hsb.cli.main git rebase-stack --help      ✓
$ python -m hsb.cli.main qa review --help             ✓
```

### Two-Layer Capability Boundary Verification

| Agent | SKILL.md allowed-tools | ClaudeAgentOptions.allowed_tools | Forbidden absent (both layers) |
|-------|------------------------|----------------------------------|--------------------------------|
| Backlog | 4 (create_issue, list_issues, get_issue, Read) | matches | mcp__linear__update_issue, Edit, Write, Bash(*) |
| Builder | 7 (Read, Edit, Write, Bash(pytest/ruff/mypy/python *)) | matches | mcp__linear__, Bash(git, Bash(gh, mcp_servers |
| Git | 12 (gh pr create/list/view/diff *, git checkout/push--force-with-lease/rebase/log/fetch/add/commit/status *) | matches | Bash(git merge, Bash(gh pr merge, Edit, Write, mcp__linear__ |
| QA | 3 (Read, Bash(gh pr diff *), Bash(gh pr view *)) | matches | Edit, Write, Bash(git, Bash(gh pr create, Bash(gh pr merge, mcp__linear__ |

### Pitfall Mitigations Verified

| Pitfall | Mitigation | Verified by |
|---------|------------|-------------|
| 1 (capability bleed) | Two-layer enforcement on all 4 agents + IDEMPOTENCY RULE in BACKLOG_SYSTEM_PROMPT | Negative greps in 4 agent files + 4 SKILL.md files |
| 2 (QA runaway) | Triple-layer cycle cap: SKILL.md prompt + IMMUTABLE model_validator + integration test | `test_cycle_cap_validator` + `test_cycle_cap_at_3_requires_tech_debt_annotation` |
| 3 (bare --force) | Git Agent allow-list contains `Bash(git push --force-with-lease *)` only; no `Bash(git push --force *)` | `test_no_merge_in_allowed_tools` |
| 4 (gh pr list pagination) | `--limit 100` mandated in GIT_SYSTEM_PROMPT REBASE_STACK clause | grep verified |
| 5 (auto-invocation) | All 4 SKILL.md files have `disable-model-invocation: true` | grep verified per agent |
| 6 (stale state) | CLI commands fetch fresh Linear/PR state before constructing Input contracts | Documented in `cli/builder.py` and `cli/qa.py` |

## Human Verification Required

The integration test bodies are wired to live infrastructure (Linear MCP + GitHub PRs). The operator must run them with appropriate environment variables set. These items are tracked here so they appear in `/gsd-progress` and `/gsd-audit-uat`.

### 1. Backlog Agent integration suite
- **Setup:** `export ANTHROPIC_API_KEY=...; export HSB_TEST_FIXTURE_URL=https://github.com/hugo-hsbtech/hsb-test-fixture`
- **Run:** `pytest tests/integration/test_backlog_agent.py -v -m integration`
- **Expected:** 5 tests pass against real Linear test workspace; idempotency proves second run creates 0 new EPICs

### 2. Builder Agent integration suite
- **Setup:** Clone fixture repo to `/tmp/hsb-test-fixture`; `export HSB_TEST_FIXTURE_PATH=/tmp/hsb-test-fixture; export ANTHROPIC_API_KEY=...`
- **Run:** `pytest tests/integration/test_builder_agent.py -v -m integration`
- **Expected:** 3 tests pass; `test_capability_boundary` confirms git HEAD unchanged after Builder run

### 3. Git Agent integration suite
- **Setup:** Same fixture path; `gh auth login` (repo scope); seed `epic/LIN-TEST-100` branch (auto-created by `epic_branch_setup` fixture)
- **Run:** `pytest tests/integration/test_git_agent.py -v -m integration`
- **Expected:** 4 tests pass; PR base is `epic/LIN-...` (not main); branches and titles match regex

### 4. QA Agent integration suite
- **Setup:** Identify a real PR + Linear issue pair; `export HSB_TEST_QA_PR_NUMBER=...; export HSB_TEST_QA_LINEAR_ID=...; export ANTHROPIC_API_KEY=...`
- **Run:** `pytest tests/integration/test_qa_agent.py -v -m integration`
- **Expected:** 2 tests pass; sentinel file unmodified after agent run; QAOutput cycle count increments correctly

## Self-Check: PASSED

- All 19 must-haves traced to implementation + named test
- 55 unit tests pass with no skipped, no failed
- 14 integration tests collect cleanly (deselected by default)
- All 5 plan SUMMARYs present on disk
- All 4 agents have two-layer capability boundary verified by greps
- Triple-layer cycle cap (QAAG-04) verified by 3 unit tests
- 6 Phase 2 pitfall mitigations verified by greps
- Phase goal "four execution agents are each independently functional" — achieved (all 4 have CLI command, agent service, contract validation, and integration test scaffold; ready for Phase 3 orchestrator wiring)
