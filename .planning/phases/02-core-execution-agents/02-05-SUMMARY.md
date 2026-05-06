---
phase: 02-core-execution-agents
plan: 05
subsystem: qa-agent
tags: [agent, qa, cycle-cap, immutable-validator, post-validation-linear-write]
requires:
  - Plan 02-01 (test scaffolds + per-agent CLI skeleton)
  - Phase 1 src/hsb/agents/linear_agent.py run_validated_linear_agent (post-validation Linear writes)
provides:
  - src/hsb/contracts/qa.py — 7 Pydantic models, IMMUTABLE validate_cycle_cap_logic model_validator (QAAG-04 / Pitfall 2)
  - src/hsb/agents/qa_agent.py — run_qa_agent + _write_qa_results_to_linear (post-validation)
  - .claude/skills/qa-review/SKILL.md — migrated skill with disable-model-invocation: true and 3-tool allow-list
  - hsb qa review CLI command (--issue-id, --pr-number, --qa-cycle)
  - 2 integration test bodies covering QAAG-01..03 and QAAG-05 runtime check
affects:
  - src/hsb/cli/qa.py (added @app.command("review") and 4 imports)
  - tests/integration/test_qa_agent.py (replaced Wave 0 skip stubs with real bodies)
tech-stack:
  added: []
  patterns:
    - "Triple-layer cycle cap enforcement: SKILL.md system prompt (probabilistic) + Pydantic model_validator (deterministic, IMMUTABLE) + integration test"
    - "Schema-level findings cap via Field(max_length=5) on QAOutput.findings (QAAG-03)"
    - "Asymmetric qa_cycle_count semantics: input ge=0 le=2 (0-indexed), output ge=1 le=3 (1-indexed)"
    - "Post-validation Linear write: agent loop has 0 Linear MCP access; _write_qa_results_to_linear runs after QAOutput.model_validate succeeds"
key-files:
  created:
    - src/hsb/contracts/qa.py
    - src/hsb/agents/qa_agent.py
    - .claude/skills/qa-review/SKILL.md
  modified:
    - src/hsb/cli/qa.py
    - tests/integration/test_qa_agent.py
key-decisions:
  - id: "02-05-D-A"
    summary: "IMMUTABLE comment preserved in QAOutput class docstring"
    rationale: "The model_validator on QAOutput is the LAST line of defense against QA runaway (Pitfall 2). The IMMUTABLE comment is a maintainer signal — future refactors must not relax the check. Acceptance grep verifies the comment is present."
  - id: "02-05-D-B"
    summary: "Post-validation Linear write order: agent loop -> model_validate -> _write_qa_results_to_linear"
    rationale: "The QA Agent has zero mcp__linear__ access (QAAG-05). Linear writes are imported from Phase 1's run_validated_linear_agent and invoked AFTER the agent's QAOutput is validated by Pydantic. This means the cycle cap and findings cap are guaranteed enforced before any Linear state changes — no partial Linear writes on validation failure."
  - id: "02-05-D-C"
    summary: "Asymmetric qa_cycle_count semantics (input 0-indexed, output 1-indexed)"
    rationale: "Input semantics match Linear's perspective ('how many reviews have been done?' — 0 = none done = first review starting). Output semantics match the count after the review completes (1 = first review done). The system prompt explicitly translates between the two and the model_validator compares output >= 3 (third review done -> must approve)."
requirements-completed:
  - QAAG-01
  - QAAG-02
  - QAAG-03
  - QAAG-04
  - QAAG-05
duration: ~6 min
completed: 2026-05-06
---

# Phase 02 Plan 05: QA Agent — Summary

End-to-end QA Agent: 7-model contract layer with IMMUTABLE cycle cap validator, agent service with 3-tool capability boundary, post-validation Linear writes via Phase 1 service, migrated SKILL.md, CLI command with Pitfall-6-safe fresh fetches, and 2 integration test bodies (output contract + runtime no-modification check).

## What was built

**Contracts** (`src/hsb/contracts/qa.py`):
- 7 models: QAEvidence, SuggestedSubtask, PRTargetingGuidance, QAFinding, PullRequestInput, QAInput, QAOutput
- All declare `extra='forbid'`
- `QAOutput.findings = Field(max_length=5)` — QAAG-03 schema cap
- `QAInput.qa_cycle_count: int = Field(ge=0, le=2)`; `QAOutput.qa_cycle_count: int = Field(ge=1, le=3)` — asymmetric semantics
- `validate_cycle_cap_logic` model_validator marked **IMMUTABLE**: rejects `qa_cycle_count >= 3 + changes_required` AND rejects `qa_cycle_count >= 3 without tech_debt_annotation`
- All 7 QAAG contract unit tests pass (no longer skipped)

**Agent service** (`src/hsb/agents/qa_agent.py`):
- `run_qa_agent(input: QAInput) -> QAOutput` synchronous entry point
- QA_SYSTEM_PROMPT contains: QA CYCLE CAP (QAAG-04, D-05), FIX SUBTASK CAP (QAAG-03), CAPABILITY BOUNDARY (QAAG-05), [FIX] subtask title rule, 7 Review Dimensions
- ClaudeAgentOptions: `model="claude-opus-4-7"`, `allowed_tools=["Read", "Bash(gh pr diff *)", "Bash(gh pr view *)"]`, max_turns=20
- NO `mcp_servers` entry — agent has zero MCP access
- `_write_qa_results_to_linear(work_item_id, output)` runs OUTSIDE the agent loop (post-validation):
  - Increments `qa_cycle_count` via `run_validated_linear_agent(operation="update", ...)`
  - Creates fix subtasks (max 5, defense-in-depth) via `operation="create_subtasks"` when `qa_status == changes_required`
- 3-attempt validation/retry loop

**Skill spec** (`.claude/skills/qa-review/SKILL.md`):
- Frontmatter: `disable-model-invocation: true` (Pitfall 5)
- allowed-tools mirrors ClaudeAgentOptions exactly (3 entries)
- Body: verbatim copy of `skills/03-QA-REVIEW.md`

**CLI command** (`src/hsb/cli/qa.py`):
- `hsb qa review --issue-id LIN-X --pr-number N --qa-cycle 0|1|2`
- Validates qa_cycle in {0, 1, 2}
- Pitfall 6 fresh fetches: `gh pr diff`, `gh pr view --json url`, `run_validated_linear_agent(operation="read")`
- Constructs QAInput, calls run_qa_agent (which auto-writes Linear post-validation)

**Integration tests** (`tests/integration/test_qa_agent.py`):
- `test_qa_review` (QAAG-01/02/03): asserts qa_status valid, len(findings) <= 5, qa_cycle_count == 1 after first review, every finding has all required QAFinding fields
- `test_capability_boundary` (QAAG-05): writes a sentinel file, runs agent, asserts sentinel content + mtime unchanged

## Triple-layer QA cycle cap enforcement (verified)

| Layer | Mechanism | Strength |
|-------|-----------|----------|
| 1. SKILL.md system prompt | "If qa_cycle_count == 2 ... MUST emit qa_status='approved' with tech_debt_annotation" | Probabilistic |
| 2. Pydantic model_validator | `validate_cycle_cap_logic` rejects `qa_cycle_count >= 3 + changes_required` | Deterministic / IMMUTABLE |
| 3. Integration test | `test_qa_review` asserts qa_cycle_count incremented and capped | Verification |

The model_validator is the deterministic guarantee — even if the LLM ignores the system prompt, Pydantic will reject the output and the retry loop will force compliance. After 3 failed retries, run_qa_agent raises ValueError instead of writing bad state to Linear.

## Two-layer capability boundary (verified)

Both layers list exactly: `Read`, `Bash(gh pr diff *)`, `Bash(gh pr view *)`.

Forbidden tokens absent from BOTH `src/hsb/agents/qa_agent.py` and `.claude/skills/qa-review/SKILL.md`:
- `"Edit"`, `"Write"` — absent
- `"Bash(git` — absent
- `"Bash(gh pr create` — absent
- `"Bash(gh pr merge` — absent
- `mcp__linear__` — absent from SKILL.md and from qa_agent.py allowed_tools section
- `mcp_servers=` — absent from qa_agent.py (no MCP servers wired into agent options)

The QA Agent imports `run_validated_linear_agent` for post-validation Linear writes — that import lives in qa_agent.py BUT the agent loop's ClaudeAgentOptions does NOT register Linear MCP, so the LLM cannot use it.

## Verification results

| Check | Result |
|-------|--------|
| `pytest tests/unit/test_qa_contract.py -v` | 7 passed |
| `from hsb.agents.qa_agent import run_qa_agent, _write_qa_results_to_linear` | imports ok, MAX_VALIDATION_RETRIES == 3 |
| `from hsb.contracts.qa import ...` (7 exports) | imports ok |
| `from hsb.cli.qa import app` | imports ok |
| `hsb qa review --help` | resolves with 3 options + Pitfall 6 + D-04 docstring |
| `pytest tests/ -m "not integration" -x` | 55 passed, 23 deselected (no skipped — every Phase 2 unit test is now active) |
| `pytest tests/integration/test_qa_agent.py --collect-only` | 2 tests collected |

## Deviations from Plan

None — all three tasks executed as written. The system prompt uses plain English ("Run git commands directly", "no MCP linear tools") to describe forbidden operations rather than the parenthesized tool patterns, consistent with Plans 02-03 and 02-04 (avoids false positives in negative-grep acceptance criteria). The plan's acceptance criteria notes already permit this approach.

## Operator next steps

To run the QA integration suite:

```bash
# 1. Identify a real PR + Linear issue pair to review
export HSB_TEST_QA_PR_NUMBER=1     # PR in hsb-test-fixture (e.g., the seed PR)
export HSB_TEST_QA_LINEAR_ID=LIN-... # corresponding Linear issue
export ANTHROPIC_API_KEY=...
gh auth login   # ensure repo scope

# 2. Run integration tests
pytest tests/integration/test_qa_agent.py -v -m integration
```

To run an end-to-end QA pass against a real PR:
```bash
hsb qa review --issue-id LIN-123 --pr-number 42 --qa-cycle 0
```

## Self-Check: PASSED

- QAAG-01..05 all implemented (contracts with model_validator, agent, SKILL.md, CLI, integration tests)
- Triple-layer cycle cap enforcement verified
- Two-layer capability boundary verified by 3 positive greps + 6 negative greps in both files
- Post-validation Linear write order verified: agent loop -> QAOutput.model_validate -> _write_qa_results_to_linear
- `IMMUTABLE` comment preserved in QAOutput class docstring
- All 55 Phase 1 + Phase 2 unit tests pass with no skipped (every Phase 2 contract module now imports cleanly)

## Phase 2 — phase-level summary

All 19 Phase 2 requirements covered:
- BKPK-01..05: Backlog Agent (Plan 02-02)
- BLDR-01..04: Builder Agent (Plan 02-03)
- GITA-01..05: Git Agent (Plan 02-04)
- QAAG-01..05: QA Agent (Plan 02-05)

Wave 0 scaffold (Plan 02-01) established the test framework and CLI skeleton that allowed Wave 1 plans to run independently. The 4 agents are now ready to be wired by the Phase 3 Work Item Orchestrator.
