---
phase: 2
slug: core-execution-agents
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-05
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.23+ (installed via Phase 1 `pip install -e .[dev]`) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` (established Phase 1) |
| **Quick run command** | `pytest tests/unit/ -x` |
| **Full suite command** | `pytest tests/ -x --ignore=tests/integration/` |
| **Estimated runtime** | ~30s unit, ~5min integration |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/ -x`
- **After every plan wave:** Run `pytest tests/ -x --ignore=tests/integration/`
- **Before `/gsd-verify-work`:** Full suite including integration tests must be green
- **Max feedback latency:** 30 seconds (unit), 5 minutes (integration)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | BKPK-01 | — | Backlog Agent parses plan.md and produces structured output | integration | `pytest tests/integration/test_backlog_agent.py::test_parse_plan -x -m integration` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | BKPK-02 | — | EPICs persisted to Linear with title and traceability | integration | `pytest tests/integration/test_backlog_agent.py::test_create_epics -x -m integration` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0 | BKPK-03 | — | User Stories persisted as children of EPICs | integration | `pytest tests/integration/test_backlog_agent.py::test_create_user_stories -x -m integration` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 0 | BKPK-04 | — | Tasks persisted as children of User Stories or EPICs | integration | `pytest tests/integration/test_backlog_agent.py::test_create_tasks -x -m integration` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 0 | BKPK-05 | — | Idempotency: second run does not create duplicate EPICs | integration | `pytest tests/integration/test_backlog_agent.py::test_idempotency -x -m integration` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 0 | BLDR-01 | — | Builder reads work item from Linear and implements only scoped change | integration | `pytest tests/integration/test_builder_agent.py::test_scoped_implementation -x -m integration` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 0 | BLDR-02 | — | Builder runs local validations and reports results | integration | `pytest tests/integration/test_builder_agent.py::test_validation_run -x -m integration` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 0 | BLDR-03 | — | BuilderOutput contract validates correctly | unit | `pytest tests/unit/test_builder_contract.py -x` | ❌ W0 | ⬜ pending |
| 02-02-04 | 02 | 0 | BLDR-04 | — | Builder does not use git or Linear tools | integration | `pytest tests/integration/test_builder_agent.py::test_capability_boundary -x -m integration` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 0 | GITA-01 | — | Branch named feature/LIN-{id}-{slug} | integration | `pytest tests/integration/test_git_agent.py::test_branch_naming -x -m integration` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 0 | GITA-02 | — | Task PR targets EPIC branch | integration | `pytest tests/integration/test_git_agent.py::test_pr_base -x -m integration` | ❌ W0 | ⬜ pending |
| 02-03-03 | 03 | 0 | GITA-03 | — | PR title includes Linear issue ID | integration | `pytest tests/integration/test_git_agent.py::test_pr_title -x -m integration` | ❌ W0 | ⬜ pending |
| 02-03-04 | 03 | 0 | GITA-04 | — | REBASE_STACK triggers for all sibling PRs | integration | `pytest tests/integration/test_git_agent.py::test_rebase_stack -x -m integration` | ❌ W0 | ⬜ pending |
| 02-03-05 | 03 | 0 | GITA-05 | — | Git Agent never merges (allowed-tools check) | unit | `pytest tests/unit/test_git_contract.py::test_no_merge_in_allowed_tools -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 0 | QAAG-01 | — | QA Agent produces approved/changes_required contract | integration | `pytest tests/integration/test_qa_agent.py::test_qa_review -x -m integration` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 0 | QAAG-02 | — | Each finding includes all required fields | unit | `pytest tests/unit/test_qa_contract.py::test_finding_fields -x` | ❌ W0 | ⬜ pending |
| 02-04-03 | 04 | 0 | QAAG-03 | — | Max 5 findings per report (Pydantic enforced) | unit | `pytest tests/unit/test_qa_contract.py::test_findings_max_length -x` | ❌ W0 | ⬜ pending |
| 02-04-04 | 04 | 0 | QAAG-04 | — | qa_cycle_count=3 forces approved + tech_debt_annotation | unit | `pytest tests/unit/test_qa_contract.py::test_cycle_cap_validator -x` | ❌ W0 | ⬜ pending |
| 02-04-05 | 04 | 0 | QAAG-05 | — | QA Agent never uses Edit/Write/git tools | integration | `pytest tests/integration/test_qa_agent.py::test_capability_boundary -x -m integration` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_backlog_contract.py` — BacklogInput/BacklogOutput schema tests (BKPK-01)
- [ ] `tests/unit/test_builder_contract.py` — BuilderInput/BuilderOutput schema tests (BLDR-03)
- [ ] `tests/unit/test_git_contract.py` — GitInput/GitOutput schema tests + GITA-05 allowed-tools check
- [ ] `tests/unit/test_qa_contract.py` — QAFinding/QAOutput tests including cycle cap validator (QAAG-02, QAAG-03, QAAG-04)
- [ ] `tests/integration/test_backlog_agent.py` — real Linear workspace tests (BKPK-01 through BKPK-05)
- [ ] `tests/integration/test_builder_agent.py` — hsb-test-fixture repo tests (BLDR-01, BLDR-02, BLDR-04)
- [ ] `tests/integration/test_git_agent.py` — hsb-test-fixture repo tests (GITA-01 through GITA-05)
- [ ] `tests/integration/test_qa_agent.py` — real Linear + real PR tests (QAAG-01, QAAG-05)
- [ ] `hsb-test-fixture` GitHub repo creation (if not exists) — required for Builder and Git integration tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| REBASE_STACK cascade completeness | GITA-04 | Requires timing-sensitive multi-PR state that is hard to reproduce deterministically in CI | Create 2 sibling PRs on EPIC branch; merge one; verify both have `git rebase --onto` events in Git Agent trace |
| Linear hierarchy visual inspection | BKPK-02, BKPK-03, BKPK-04 | Parent-child link correctness visible in Linear UI but not easily asserted via API alone | Open Linear workspace after Backlog Agent run; verify EPIC → User Story → Task → Subtask tree |
| QA tech-debt annotation content quality | QAAG-04 | LLM judge for annotation quality (annotation is meaningful, not a filler string) | Review tech_debt_annotation field in QAOutput at qa_cycle_count=3; assess describes actual debt |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (unit), < 5min (integration)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
