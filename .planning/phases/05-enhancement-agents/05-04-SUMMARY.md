---
phase: 05-enhancement-agents
plan: 04
status: autonomous-complete-pending-operator-checkpoint
wave: 3
completed: 2026-05-06
requirements:
  - UATA-01
  - UATA-03
  - SC-1
  - SC-2
  - SC-3
  - SC-4
  - SC-5
checkpoint:
  type: human-verify
  resume_signal: "approved" | "blocked: <reason>"
---

# Plan 05-04 Summary — Global Orchestrator wiring + operator GO/NO-GO

Wave 3 of Phase 5. Wires Plans 05-01 (Intelligence inline in WIO),
05-02 (Risk Agent + chokepoint module), and 05-03 (UAT Agent) into the
Phase 4 Global Orchestrator. Phase 4 capabilities (GORD-01..04,
MORD-01..05) remain functional — Phase 5 is purely additive.

This plan has THREE tasks:

| Task | Status | Notes |
|------|--------|-------|
| 1: GlobalOrchestratorOutput contract extension + 4 conftest fixtures | Complete | Backward-compatible (default empty lists) |
| 2: GlobalOrchestrator extensions + 3 integration test files | Complete | Phase 4 features verified preserved |
| 3: Human GO/NO-GO checkpoint (5 Success Criteria) | **Pending operator** | See "Operator Verification Contract" below |

## Files Modified (autonomous tasks)

| Path | Change |
|------|--------|
| `src/hsb/contracts/global_orchestrator.py` | Imports `AutoImprovementTrigger`. `GlobalOrchestratorOutput` adds `uat_dispatched: list[str] = Field(default_factory=list)` and `improvement_triggers: list[AutoImprovementTrigger] = Field(default_factory=list)`. Phase 4 invariants preserved. |
| `src/hsb/agents/global_orchestrator.py` | Imports RiskAgent, run_uat_and_validate, AutoImprovementTrigger, UATResult, re. Adds `_UAT_BANNED_RE` regex + `_uat_passes_g10` helper at module level. Adds `_detect_uat_ready_user_stories` and `_fetch_children` methods to GlobalOrchestrator. Extends `get_ready_tasks` with Step 2 (Risk priority queue), Step 4 (UAT dispatch), Step 5 (improvement_triggers=[]). |
| `tests/conftest.py` | Adds 4 Phase 5 fixtures: `tmp_knowledge_cleanup`, `linear_test_workspace`, `uat_ready_user_story`, `test_task_with_knowledge_fixture`, `test_task_with_qa_finding_fixture`. Phase 1+ fixtures and Plan 05-02's `_gsd_clear_api_key` autouse remain untouched. |

## Files Created

| Path | Lines |
|------|-------|
| `tests/integration/test_global_orchestrator_uat.py` | 109 |
| `tests/integration/test_uat_fix_subtasks.py` | 55 |
| `tests/integration/test_global_orchestrator_phase5.py` | 65 |

## Phase 5 Test Suite Status (autonomous portion)

| Suite | Count | Status |
|-------|-------|--------|
| Unit (Phase 1-5 cumulative) | 106 | All passing |
| Code-based evals (B1 + B3) | 18 | All passing |
| Integration source-grep tests (Phase 5 plans 01/03/04) | 22 | All passing |
| Integration fixture-driven tests (Phase 5) | 6 | Collect cleanly; require live Linear test workspace |
| Total Phase 5 integration tests collected | 59 | Clean collection across the suite |

## Phase 4 Regression Confirmation

`tests/integration/test_global_orchestrator_phase5.py::test_phase4_features_preserved`
PASSES. Source-grep verifies the following Phase 4 features remain in
`src/hsb/agents/global_orchestrator.py`:

- `_filter_ready_items` (GORD-01..02 dependency filter)
- `_check_epic_complete` (GORD-04 EPIC completion signal)
- `is_backlog_empty` (GORD-03 empty backlog signal)

Phase 4 unit tests (`test_orchestrator.py`, `test_main_orchestrator.py`,
`test_run_loop.py`) all pass alongside Phase 5 additions.

## Guardrail Enforcement Surface (Phase 5 cumulative)

| ID | Mechanism | Site |
|----|-----------|------|
| G1 | `assert_oauth2_only()` function-entry guard | `_sdk_options.py` (called from `make_options`) + session-scoped autouse fixture in `conftest.py` |
| G2 | `make_options()` factory rejects `"Agent"` in allowed_tools | `_sdk_options.py:43` |
| G3 | `assert_no_task_dispatch(msg)` in receive loops | WIO (3 sites), Risk Agent (1 site), UAT Agent (1 site) |
| G4 | Skill 14 SDK call uses `allowed_tools=[], mcp_servers=None, model=haiku, max_turns=3` | `risk_agent.py:177` |
| G5 | `linear_write_guard` decorator on LinearAgent write dispatcher | `linear_agent.py:181-189` |
| G6 | UAT cycle cap = 3 + Linear escalation comment (`linear_createComment` shape) | `global_orchestrator.py::_detect_uat_ready_user_stories` |
| G7 | `error_max_turns` raises RuntimeError; `try/except RuntimeError` around UAT dispatch logs at ERROR | UAT Agent receive loop + `get_ready_tasks` |
| G8 | WIO context warning at 120K input_tokens | WIO Steps 2-4 + Step 5 receive loops |
| G9 | `KnowledgeStorageInput.applicability` validator + `extra="forbid"` | `knowledge.py` |
| G10 | `_uat_passes_g10` (B1 coverage + B3 banned-token regex) before every UAT-related Linear write | `global_orchestrator.py:75` (helper); called twice in `get_ready_tasks` |

---

# Operator Verification Contract — Task 3 (GO/NO-GO checkpoint)

This section is the resume-from-handoff document. The operator runs the
13-step verification matrix below, then signals "approved" (or "blocked:
<reason>") to mark the autonomous Phase 5 portion fully accepted.

## Pre-conditions (operator must confirm before starting)

- Plan 04-04 operator MVP checkpoint has been signed off (see
  `.planning/phases/04-global-main-orchestrators-and-parallel-mode/04-04-SUMMARY.md`).
- Linear test workspace authenticated via `mcp-remote` OAuth2 (Phase 1 setup).
- Linear test workspace contains:
  - At least one User Story with all child tasks `qa_status=approved` (UAT dispatch test).
  - At least 2 todo tasks with no blocking dependencies (Risk priority queue test).
- `hsb-test-fixture` GitHub repo accessible (Phase 2 setup).
- `knowledge/` directory has at least one pre-seeded entry under `knowledge/qa/`.
- `.worktrees/` directory at repo root is empty.
- `ANTHROPIC_API_KEY` is **NOT** set in the environment (G1 OAuth2 invariant).

## 13-Step Verification Matrix

### SC-1: Intelligence enrichment retrieves knowledge entries before Builder

```bash
cd /home/ubuntu/hugo/task-management-agents
pytest tests/integration/test_wio_intelligence_enrichment.py::test_wio_step1_populates_knowledge_context -v
```

Expected: test PASSES. Open Linear and confirm the test task's comments
include an "Enrichment Report" or `knowledge_context` block.

### SC-2: Intelligence writes knowledge entry with all 8 required fields after QA

```bash
pytest tests/integration/test_wio_intelligence_storage.py::test_wio_step5_writes_knowledge_entry -v
ls knowledge/qa/ knowledge/implementation/ knowledge/patterns/ 2>/dev/null
```

Expected: test PASSES. At least one new `.md` file under
`knowledge/<category>/`. Open one and confirm all 8 fields
(`title`, `type`, `context`, `evidence`, `insight`, `recommendation`,
`applicability`, `date`) are present.

### SC-3: UAT Agent produces scenario results per acceptance criterion

```bash
pytest tests/integration/test_uat_agent.py::test_uat_validates_user_story_with_all_tasks_approved -v
pytest tests/integration/test_global_orchestrator_uat.py::test_uat_dispatch_on_all_tasks_approved -v
```

Expected: both PASS. Open the User Story in Linear; confirm `uat_status`
is updated (`approved` or `changes_required` — both are valid).

### SC-4: Risk Agent priority queue is consumed by Global Orchestrator

```bash
pytest tests/integration/test_global_orchestrator_phase5.py::test_ready_tasks_sorted_by_risk_score -v
```

Expected: test PASSES — `GlobalOrchestratorOutput.ready_tasks` order
matches `RiskAgent.get_priority_queue()` output for the same Linear state.

### SC-5: Risk Agent surfaces improvement triggers without creating Linear items

**5a — automated path (primary, binding):**
```bash
pytest tests/unit/test_risk_agent_triggers.py::test_sc5_positive_path_returns_trigger_for_seeded_qa_history -v
```
Expected: test PASSES. Confirms `detect_improvement_triggers` returns
≥1 `AutoImprovementTrigger` for the seeded `qa_history`; every trigger
has `linear_state == "suggested"` and `len(pattern_evidence) >= 2`.

**5b — live SDK smoke (defense-in-depth):**
```bash
python -c "import asyncio
from hsb.agents.risk_agent import RiskAgent
agent = RiskAgent()
triggers = asyncio.run(agent.detect_improvement_triggers(qa_history=[
    {'work_item_id':'LIN-1','category':'auth','status':'changes_required'},
    {'work_item_id':'LIN-2','category':'auth','status':'changes_required'},
    {'work_item_id':'LIN-3','category':'auth','status':'changes_required'},
], scores=[]))
for t in triggers:
    print(f'{t.title}: linear_state={t.linear_state}, evidence_count={len(t.pattern_evidence)}')"
```
Expected: 0 or more triggers printed; EVERY printed `linear_state ==
'suggested'`; EVERY `evidence_count >= 2`. Open Linear and verify NO
new issues were created (RISK-04 confirmation).

### G1 OAuth2-only regression smoke

```bash
env | grep -i ANTHROPIC_API_KEY
python -c "from hsb.agents.uat_agent import run_uat_and_validate"
python -c "from hsb.agents.risk_agent import RiskAgent"
python -c "from hsb.agents.global_orchestrator import GlobalOrchestrator"
```
Expected: env grep returns nothing; all three imports succeed.

### G2 no-sub-subagent-dispatch smoke

```bash
grep -r '"Agent"' src/hsb/agents/ | grep -v "_FORBIDDEN_TOOLS\|test_\|Agent SDK\|forbidden"
```
Expected: no matches except comments / forbidden-tools set / SDK references.

### Phase 4 regression — cascade and parallel still work

```bash
pytest tests/integration/test_global_orchestrator_e2e.py tests/integration/test_parallel_mode_e2e.py -v
hsb run --help
hsb run-next-step --help
```
Expected: Phase 4 integration tests PASS or SKIP with documented reason;
CLI commands still register.

### Full unit suite green

```bash
pytest tests/unit/ -x -q
```
Expected: exit 0; 106 tests pass.

### Full integration suite collects cleanly

```bash
pytest tests/integration/ --collect-only -q
```
Expected: exit 0; 59 tests collected; no errors.

### Code-based eval suite (B1 + B3)

```bash
pytest tests/evals/code_based/ -x -q
```
Expected: exit 0; 18 tests pass.

### Manual Linear inspection

Open Linear test workspace. Verify:
- The User Story chosen by SC-3 has `uat_status` set to `approved` or
  `changes_required`.
- If `changes_required`: 1+ fix subtasks created with descriptions
  matching the failed scenarios' findings.
- The User Story's `uat_cycle_count` is 1 (first UAT cycle).
- No improvement-trigger work items appear in Linear (RISK-04).

### Manual `knowledge/` inspection

Open `knowledge/qa/` and other categories. Verify:
- New `.md` entries from this run have all 8 required fields populated.
- No entries have `applicability: "all tasks"`, empty applicability, or
  `applicability: "n/a"` (G9 + pydantic validator).
- No obvious-duplicate entries.

## Resume Signal

After running all 13 steps, signal one of:
- `"approved"` — all 5 SCs verified, Phase 5 marked complete.
- `"blocked: <description>"` — at least one step failed; planner replans
  to address the gap. If G6 UAT cycle cap activates during SC-3, document
  the User Story ID and continue (correct G6 behavior, not a failure).

## Required Fields to Capture (operator fills in upon completion)

| Field | Captured value |
|-------|----------------|
| User Story ID used for SC-3 | `<LIN-...>` |
| Final `uat_status` after SC-3 | `<approved|changes_required>` |
| Final `uat_cycle_count` | `<int>` |
| New `knowledge/<category>/*.md` files written during SC-2 | `<list>` |
| SC-5 manual smoke output (raw) | `<paste>` |
| New Linear items created during SC-5 | `<should be: NONE>` |
| G6 UAT cycle cap activations during smoke | `<list of User Story IDs>` |
| G10 UAT pre-persist validation failures during smoke | `<list>` |
| Phase 4 cascade test status | `<PASS|SKIP|FAIL>` |
| Phase 4 parallel test status | `<PASS|SKIP|FAIL>` |

## Self-Check (autonomous portion): PASSED

- All Phase 5 contract files exist and import cleanly.
- All Phase 5 SDK call sites use `make_options()` factory (G1+G2 chokepoint).
- All G3 backstops wired into receive loops.
- G5 LinearAgent decorator applied to write dispatcher.
- G6 escalation uses camelCase `linear_createComment` payload shape.
- G10 pre-persist validation guards every UAT-related Linear write.
- Phase 4 features (GORD-01..04) verified preserved.
- 106 unit tests + 18 code-based evals + 22 integration source-grep tests
  pass; 59 integration tests collect cleanly.

The autonomous portion of Plan 05-04 — and therefore Phase 5 — is
**complete except for the operator GO/NO-GO checkpoint**.
