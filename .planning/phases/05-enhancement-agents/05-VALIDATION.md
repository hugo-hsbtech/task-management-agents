---
phase: 5
slug: enhancement-agents
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-06
revised: 2026-05-06
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio>=0.23.0 (async fixtures, async tests) and hypothesis>=6.100.0 (RISK-01 property-based test) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` section) — `asyncio_mode = "auto"` recommended; `markers = ["integration: real Linear test workspace + GitHub fixture"]` |
| **Quick run command** | `pytest tests/unit/ -x -q` (~5–15 seconds — unit tests only, no Linear/SDK calls) |
| **Full suite command** | `pytest tests/unit/ tests/evals/code_based/ tests/integration/ --collect-only -q && pytest tests/unit/ tests/evals/code_based/ -x -q` (collection-clean check + full unit + eval suite; integration tests run separately) |
| **Estimated runtime** | unit + eval: ~15–30 seconds; integration tests: ~2–5 minutes (real SDK + Linear) |
| **Integration markers** | `pytest -m integration` for Linear/SDK live runs; default unit/eval suite excludes integration via `-k "not integration"` if needed |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/ -x -q` (the quick command). Must be green before commit.
- **After every plan wave:**
  - Wave 1 (05-02): `pytest tests/unit/test_sdk_options_factory.py tests/unit/test_risk_agent_*.py tests/unit/test_linear_write_guard_g5.py -x -q`
  - Wave 2 (05-01, 05-03): `pytest tests/unit/ tests/evals/code_based/ -x -q` AND `pytest tests/integration/ --collect-only -q`
  - Wave 3 (05-04): full unit + eval green; integration `--collect-only` clean.
- **Before `/gsd-verify-work`:** Full unit + eval suites green. Integration tests run as part of the human GO/NO-GO checkpoint (Plan 05-04 Task 3).
- **Max feedback latency:** ~30 seconds for unit + eval (well under the 60 s Nyquist target).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-02-01 | 02 | 1 | RISK-04 | T-5-06, T-5-07, T-5-07b, T-5-10b | G1 function-entry only; G2 ValueError; G3 RuntimeError on Task tool; G5 PermissionError on risk_agent stack frame; conftest autouse fixture clears ANTHROPIC_API_KEY | unit | `pytest tests/unit/test_sdk_options_factory.py -x -q` | ❌ W0 (Wave 1 creates) | ⬜ pending |
| 05-02-02 | 02 | 1 | RISK-01, RISK-02, RISK-03, RISK-04 | T-5-06, T-5-08, T-5-10 | Deterministic quality score; sort + tiebreaker; pattern_evidence ≥ 2 filter; skill 14 SDK config (allowed_tools=[], mcp_servers=None, model=haiku, max_turns=3, max_budget=$0.05); G3 backstop in receive loop; SC-5 positive-path returns ≥1 trigger | unit | `pytest tests/unit/test_risk_agent_quality_score.py tests/unit/test_risk_agent_priority_queue.py tests/unit/test_risk_agent_triggers.py tests/unit/test_risk_agent_skill14_config.py -x -q` | ❌ W0 (Wave 1 creates) | ⬜ pending |
| 05-02-03 | 02 | 1 | RISK-04 | T-5-06 | G5 stack inspection: deny risk_agent.py callers except via approve_improvement_trigger() delegated path | unit | `pytest tests/unit/test_linear_write_guard_g5.py -x -q` | ❌ W0 (Wave 1 creates) | ⬜ pending |
| 05-01-01 | 01 | 2 | INTL-03 | T-5-03 | KnowledgeStorageInput pydantic schema rejects empty/'all tasks'/'n/a' applicability; rejects extra fields; rejects invalid type literal | unit | `pytest tests/unit/test_knowledge_storage_schema.py -x -q` | ❌ W0 (Wave 2 creates) | ⬜ pending |
| 05-01-02 | 01 | 2 | INTL-01, INTL-02, INTL-04, WORC-02 | T-5-01, T-5-02, T-5-04 | WIO allowed_tools excludes 'Agent' and Linear write tools; SKILL_FILES includes skills 10+11; G3 backstop wired into every client.receive_response() loop; G8 context budget warning at 120K tokens | unit + integration-collect | `pytest tests/unit/test_wio_allowed_tools.py -x -q && pytest tests/integration/test_wio_intelligence_enrichment.py tests/integration/test_wio_intelligence_storage.py --collect-only -q` | ❌ W0 (Wave 2 creates) | ⬜ pending |
| 05-03-01 | 03 | 2 | UATA-02 | T-5-12, T-5-13 | UATScenario.evidence min_length=10; UATResult.uat_cycle ge=1; scope_violations defaults []; B1 coverage check; B3 banned-token regex on findings | unit (eval) | `pytest tests/evals/code_based/test_uat_coverage.py tests/evals/code_based/test_uat_scope.py -x -q` | ❌ W0 (Wave 2 creates) | ⬜ pending |
| 05-03-02 | 03 | 2 | UATA-01, UATA-04, WORC-02 | T-5-11, T-5-12, T-5-13, T-5-14, T-5-15 | run_uat_and_validate Pattern B + 3-retry pydantic; allowed_tools=[Read,Glob,Grep,Bash] (no Write/Edit/Agent); mcp_servers=None; SCOPE BOUNDARY literal in prompt; G3 backstop in receive loop; no linear_agent import; uses make_options factory (G2 chokepoint) | unit (source-grep) + integration-collect | `pytest tests/integration/test_uat_agent.py -k "not test_uat_validates and not test_uat_agent_produces_no_scope" -x -q && pytest tests/integration/test_uat_agent.py --collect-only -q` | ❌ W0 (Wave 2 creates) | ⬜ pending |
| 05-04-01 | 04 | 3 | UATA-01, UATA-03 | T-5-17, T-5-23 | GlobalOrchestratorOutput extended with uat_dispatched + improvement_triggers (default empty list); 4 Phase 5 conftest fixtures added as @pytest_asyncio.fixture (issue 3 fix: NOT sync wrappers around asyncio.run()); Phase 4 contract callers continue to work | unit | `python -c "from hsb.contracts.global_orchestrator import GlobalOrchestratorOutput; o = GlobalOrchestratorOutput(ready_tasks=[], is_backlog_empty=False, is_epic_ready=False); assert o.uat_dispatched == [] and o.improvement_triggers == []"` AND `grep -q "@pytest_asyncio.fixture" tests/conftest.py` | ❌ W0 (Wave 3 creates) | ⬜ pending |
| 05-04-02 | 04 | 3 | UATA-01, UATA-03 | T-5-17, T-5-18, T-5-19, T-5-20, T-5-21, T-5-22, T-5-23 | GlobalOrchestrator imports RiskAgent + run_uat_and_validate; risk priority queue insertion; UAT inline-await dispatch; G6 cycle cap (uat_cycle_count >= 3) with `issueId` camelCase escalation payload (Issue 5 fix); G10 pre-persist UAT validation (B1+B3); Phase 4 features preserved | unit (source-grep) + integration-collect | `pytest tests/integration/test_global_orchestrator_uat.py -k "not test_uat_dispatch_on_all_tasks_approved" -x -q && pytest tests/integration/test_global_orchestrator_phase5.py -k test_phase4_features_preserved -x -q && pytest tests/integration/test_global_orchestrator_uat.py tests/integration/test_uat_fix_subtasks.py tests/integration/test_global_orchestrator_phase5.py --collect-only -q` | ❌ W0 (Wave 3 creates) | ⬜ pending |
| 05-04-03 | 04 | 3 | All Phase 5 SCs (SC-1..5) | T-5-11, T-5-17, T-5-19 | Human GO/NO-GO checkpoint covering all 5 success criteria; SC-5 references the 05-02 automated test (`test_sc5_positive_path_returns_trigger_for_seeded_qa_history`) as the binding automated verification path (Issue 6 fix), with live SDK as defense-in-depth | manual + automated | See Plan 05-04 Task 3 verification steps; full integration suite + manual Linear inspection | ❌ W0 (depends on Waves 1+2+3 complete) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 (test scaffolding before any implementation work) covers:

- [ ] `pyproject.toml` — add `hypothesis>=6.100.0` AND `pytest-asyncio>=0.23.0` to dev dependencies (Plan 05-02 Task 1 Edit 8). If Phase 1 already declared pytest-asyncio, do NOT duplicate; add only what is missing.
- [ ] `tests/conftest.py` — append session-scoped autouse `_gsd_clear_api_key` fixture clearing `ANTHROPIC_API_KEY` at session start (Plan 05-02 Task 1 Edit 6 — defensive G1 pairing per checker BLOCKER #2). Phase 1+ existing fixtures MUST remain untouched.
- [ ] `tests/conftest.py` — append 4 async Phase 5 fixtures: `uat_ready_user_story`, `tmp_knowledge_cleanup`, `test_task_with_knowledge_fixture`, `test_task_with_qa_finding_fixture` as `@pytest_asyncio.fixture` (NOT sync wrappers around `asyncio.run()` per AI-SPEC §4b.2 / checker BLOCKER #3). Plan 05-04 Task 1 owns this.
- [ ] `pytest.ini` / `pyproject.toml` — set `asyncio_mode = "auto"` if not already present from Phase 1.

If pytest-asyncio is not yet installed in the dev env at Wave 0 start, run `pip install -e ".[dev]"` (or the equivalent for the project's dependency manager) after Plan 05-02 modifies `pyproject.toml`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UAT verdict matches a careful human reviewer's judgment for the same User Story | UATA-02, AI-SPEC §1b sub-domain 1 | LLM-judge calibration drift detection; the operator labels reference UAT scenarios as "a human reviewer would have caught this" vs. "this was genuinely ambiguous". This is a flywheel signal, not an online guardrail. | Plan 05-04 Task 3 step 12: open the UAT-validated User Story in Linear; confirm `uat_status` matches what a careful human reviewer would conclude. Flag any false-pass for the eval-set expansion. |
| Human GO/NO-GO checkpoint at end of Phase 5 (Plan 05-04 Task 3) covering SC-1..SC-5 + G1..G5 smoke + Phase 4 regression | All Phase 5 SCs | End-to-end Linear test workspace + GitHub fixture state cannot be deterministically asserted from automated tests alone (depends on workspace contents). Operator inspects Linear/knowledge directory state in addition to running the automated test suite. | See Plan 05-04 Task 3 13-step verification procedure. SC-5 has a NEW automated path per checker Issue 6 (`pytest tests/unit/test_risk_agent_triggers.py::test_sc5_positive_path_returns_trigger_for_seeded_qa_history`); the manual step is now defense-in-depth confirmation. |
| Knowledge Store entry signal-threshold quality (recurring vs. one-off) | INTL-03, AI-SPEC §1b sub-domain 2 | LLM-judgment-driven; D-07 explicitly delegates ingestion criteria to skill 11 LLM judgment. Quality is observed over time (entry early-deletion rate per AI-SPEC §6 flywheel) — not a single-test gate. | After Plan 05-04 Task 3 step 13, manually inspect `knowledge/<category>/*.md` files written during the integration test. Confirm each has `applicability` that is specific (not "all tasks"), and that the entry would plausibly inform a future Builder. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (pytest-asyncio install + conftest fixtures)
- [x] No watch-mode flags
- [x] Feedback latency < 60s (unit + eval suite ~30s)
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Issue 7 (checker WARNING): VALIDATION.md populated from plans
- [x] Issue 1 (checker BLOCKER): G3 + G5 wired into plans (G3 in receive loops; G5 as `linear_write_guard` decorator on Phase 1 LinearAgent write methods, applied in Plan 05-02 Task 3)
- [x] Issue 2 (checker BLOCKER): module-top OAuth2 assertions removed from `intelligence_agent.py`, `_sdk_options.py`, `risk_agent.py`, `uat_agent.py`; G1 enforcement centralized at function-entry via `_sdk_options.assert_oauth2_only()` called from `make_options()`; defensive autouse session fixture in `conftest.py` clears the env var
- [x] Issue 3 (checker BLOCKER): Plan 05-04 Task 1 conftest fixtures converted to `@pytest_asyncio.fixture` async generators
- [x] Issue 4 (checker WARNING): Plan 05-03 moved to Wave 2 (`depends_on: ["05-02"]`); Plan 05-01 also moved to Wave 2 (depends on `_sdk_options.py`); Plan 05-04 moved to Wave 3
- [x] Issue 5 (checker WARNING): Plan 05-04 added G6 escalation payload shape unit tests asserting `issueId` camelCase + `body` (Linear MCP `linear_createComment` shape)
- [x] Issue 6 (checker WARNING): Plan 05-02 Task 2 added `test_sc5_positive_path_returns_trigger_for_seeded_qa_history`; Plan 05-04 Task 3 SC-5 checkpoint cites this test as the binding automated verification path

**Approval:** approved 2026-05-06 (revised plan set — addresses all 3 BLOCKERS + 4 WARNINGS from checker)
