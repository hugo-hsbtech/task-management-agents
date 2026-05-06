---
phase: 2
slug: core-execution-agents
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-05
revised: 2026-05-06
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
| 02-01-01 | 01 | 0 | BKPK-01 | — | Backlog Agent parses plan.md and produces structured output | integration | `pytest tests/integration/test_backlog_agent.py::test_parse_plan -x -m integration` | ✓ | ⏸ operator |
| 02-01-02 | 01 | 0 | BKPK-02 | — | EPICs persisted to Linear with title and traceability | integration | `pytest tests/integration/test_backlog_agent.py::test_create_epics -x -m integration` | ✓ | ⏸ operator |
| 02-01-03 | 01 | 0 | BKPK-03 | — | User Stories persisted as children of EPICs | integration | `pytest tests/integration/test_backlog_agent.py::test_create_user_stories -x -m integration` | ✓ | ⏸ operator |
| 02-01-04 | 01 | 0 | BKPK-04 | — | Tasks persisted as children of User Stories or EPICs | integration | `pytest tests/integration/test_backlog_agent.py::test_create_tasks -x -m integration` | ✓ | ⏸ operator |
| 02-01-05 | 01 | 0 | BKPK-05 | — | Idempotency: second run does not create duplicate EPICs | integration | `pytest tests/integration/test_backlog_agent.py::test_idempotency -x -m integration` | ✓ | ⏸ operator |
| 02-02-01 | 02 | 0 | BLDR-01 | — | Builder reads work item from Linear and implements only scoped change | integration | `pytest tests/integration/test_builder_agent.py::test_scoped_implementation -x -m integration` | ✓ | ⏸ operator |
| 02-02-02 | 02 | 0 | BLDR-02 | — | Builder runs local validations and reports results | integration | `pytest tests/integration/test_builder_agent.py::test_validation_run -x -m integration` | ✓ | ⏸ operator |
| 02-02-03 | 02 | 0 | BLDR-03 | — | BuilderOutput contract validates correctly | unit | `pytest tests/unit/test_builder_contract.py -x` | ✓ | ✅ green |
| 02-02-04 | 02 | 0 | BLDR-04 | — | Builder does not use git or Linear tools | integration | `pytest tests/integration/test_builder_agent.py::test_capability_boundary -x -m integration` | ✓ | ⏸ operator |
| 02-03-01 | 03 | 0 | GITA-01 | — | Branch named feature/LIN-{id}-{slug} | unit | `pytest tests/unit/test_git_contract.py::test_branch_naming_regex -x` | ✓ | ✅ green |
| 02-03-02 | 03 | 0 | GITA-02 | — | Task PR targets EPIC branch | integration | `pytest tests/integration/test_git_agent.py::test_pr_base -x -m integration` | ✓ | ⏸ operator |
| 02-03-03 | 03 | 0 | GITA-03 | — | PR title includes Linear issue ID | unit | `pytest tests/unit/test_git_contract.py::test_pr_title_regex -x` | ✓ | ✅ green |
| 02-03-04 | 03 | 0 | GITA-04 | — | REBASE_STACK triggers for all sibling PRs | integration | `pytest tests/integration/test_git_agent.py::test_rebase_stack -x -m integration` | ✓ | ⏸ operator |
| 02-03-05 | 03 | 0 | GITA-05 | — | Git Agent never merges (allowed-tools check) | unit | `pytest tests/unit/test_git_contract.py::test_no_merge_in_allowed_tools -x` | ✓ | ✅ green |
| 02-04-01 | 04 | 0 | QAAG-01 | — | QA Agent produces approved/changes_required contract | integration | `pytest tests/integration/test_qa_agent.py::test_qa_review -x -m integration` | ✓ | ⏸ operator |
| 02-04-02 | 04 | 0 | QAAG-02 | — | Each finding includes all required fields | unit | `pytest tests/unit/test_qa_contract.py::test_finding_fields -x` | ✓ | ✅ green |
| 02-04-03 | 04 | 0 | QAAG-03 | — | Max 5 findings per report (Pydantic enforced) | unit | `pytest tests/unit/test_qa_contract.py::test_findings_max_length -x` | ✓ | ✅ green |
| 02-04-04 | 04 | 0 | QAAG-04 | — | qa_cycle_count=3 forces approved + tech_debt_annotation | unit | `pytest tests/unit/test_qa_contract.py::test_cycle_cap_validator -x` | ✓ | ✅ green |
| 02-04-05 | 04 | 0 | QAAG-05 | — | QA Agent never uses Edit/Write/git tools | integration | `pytest tests/integration/test_qa_agent.py::test_capability_boundary -x -m integration` | ✓ | ⏸ operator |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · ⏸ operator (live integration pending — see MILESTONE-UAT.md)*

---

## Wave 0 Requirements

- [x] `tests/unit/test_backlog_contract.py` — BacklogInput/BacklogOutput schema tests (BKPK-01)
- [x] `tests/unit/test_builder_contract.py` — BuilderInput/BuilderOutput schema tests (BLDR-03)
- [x] `tests/unit/test_git_contract.py` — GitInput/GitOutput schema tests + GITA-05 allowed-tools check
- [x] `tests/unit/test_qa_contract.py` — QAFinding/QAOutput tests including cycle cap validator (QAAG-02, QAAG-03, QAAG-04)
- [x] `tests/integration/test_backlog_agent.py` — real Linear workspace tests (BKPK-01 through BKPK-05)
- [x] `tests/integration/test_builder_agent.py` — hsb-test-fixture repo tests (BLDR-01, BLDR-02, BLDR-04)
- [x] `tests/integration/test_git_agent.py` — hsb-test-fixture repo tests (GITA-01 through GITA-05)
- [x] `tests/integration/test_qa_agent.py` — real Linear + real PR tests (QAAG-01, QAAG-05)
- [x] `hsb-test-fixture` GitHub repo creation — present at `https://github.com/hugo-hsbtech/hsb-test-fixture` (created autonomously by Phase 2 wrapper, recorded in `02-FIXTURE-REPO.md`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| REBASE_STACK cascade completeness | GITA-04 | Requires timing-sensitive multi-PR state that is hard to reproduce deterministically in CI | Create 2 sibling PRs on EPIC branch; merge one; verify both have `git rebase --onto` events in Git Agent trace |
| Linear hierarchy visual inspection | BKPK-02, BKPK-03, BKPK-04 | Parent-child link correctness visible in Linear UI but not easily asserted via API alone | Open Linear workspace after Backlog Agent run; verify EPIC → User Story → Task → Subtask tree |
| QA tech-debt annotation content quality | QAAG-04 | LLM judge for annotation quality (annotation is meaningful, not a filler string) | Review tech_debt_annotation field in QAOutput at qa_cycle_count=3; assess describes actual debt |
| Live integration suite operator gates | BKPK-01..05, BLDR-01,02,04, GITA-02,04, QAAG-01,05 | Require live Linear MCP + GitHub PR + browser OAuth | Consolidated in `.planning/MILESTONE-UAT.md` Group 2 (~20 min once Phase 1 OAuth bootstraps) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s (unit), < 5min (integration)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-06

---

## Validation Audit 2026-05-06

| Metric | Count |
|--------|-------|
| Tasks audited | 19 |
| Unit tasks COVERED (green) | 7 |
| Integration tasks COVERED (collect cleanly + operator-pending live runs) | 12 |
| Tasks MISSING | 0 |
| Tasks PARTIAL (failing) | 0 |
| Wave 0 deliverables verified on disk | 9/9 |
| Manual-Only items | 4 |

**Audit method:** Filesystem audit confirmed all 9 Wave 0 deliverables exist (`tests/unit/test_*_contract.py` × 4, `tests/integration/test_*_agent.py` × 4, `hsb-test-fixture` repo). Per Phase 02-VERIFICATION.md, all 55 unit tests pass; 14 integration tests collect cleanly under `-m integration`. The 12 integration tasks are reclassified `⏸ operator` (live integration pending) and documented in `.planning/MILESTONE-UAT.md` Group 2 — they are not blockers for Nyquist compliance because (a) test bodies exist, (b) tests skip cleanly without env vars, (c) operator pathway is fully documented.

**Compliance flip rationale:** `nyquist_compliant: true` because every Phase 2 task has either `Status: ✅ green` or `Status: ⏸ operator` with a Wave 0 file present and a documented operator path. No task is in `MISSING` or `PARTIAL` (failing) state.
