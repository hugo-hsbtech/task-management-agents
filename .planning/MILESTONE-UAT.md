---
milestone: v1.0
status: pending-operator
generated: 2026-05-06
total_groups: 5
total_steps: 24
estimated_duration: 60-90 min
---

# v1.0 Milestone — Operator UAT Test Plan

> Cross-phase consolidated test plan covering all 5 outstanding operator gates from Phases 1–5. Run in order — each group's sign-off unblocks the next. Check items off as you go.

**Status of autonomous work:** All 5 phases autonomous-complete. 93 commits across the milestone. 106 unit tests pass; 18 code-based evals pass; 22 integration source-grep tests pass; 59 integration tests collect cleanly.

**This document supersedes** the per-phase operator handoffs in:
- `phases/01-foundation-and-linear-integration/HUMAN-SETUP.md`
- `phases/02-core-execution-agents/02-HUMAN-UAT.md`
- `phases/03-work-item-orchestrator-and-single-cycle-mvp/03-04-SUMMARY.md` (Operator section)
- `phases/04-global-main-orchestrators-and-parallel-mode/04-04-SUMMARY.md` (Operator section)
- `phases/05-enhancement-agents/05-04-SUMMARY.md` (Operator Verification Contract)

The per-phase docs are authoritative for context; this file is the run-list.

---

## Pre-flight checks (before Group 1)

- [ ] `cd /home/ubuntu/hugo/task-management-agents`
- [ ] `git status` is clean
- [ ] `git log --oneline -5` shows recent Phase 5 commits (last commit ~2026-05-06)
- [ ] `.venv/` exists or you have `uv sync`/`pip install -e .` ready
- [ ] Browser is available (Linear MCP OAuth needs an interactive flow)
- [ ] You have a Linear workspace **you don't mind mutating** (NOT production)
- [ ] `gh auth status` shows authenticated (`hugo-hsbtech` per Phase 2 setup)

---

## Group 1 — Bootstrap (Phase 1) ⏱ ~15 min

**Goal:** Make the live integration suites runnable. One-time setup.

**Source:** `.planning/phases/01-foundation-and-linear-integration/HUMAN-SETUP.md`

### Step 1.1 — Anthropic auth (OAuth2, NOT API key)

> **Important:** The G1 guardrail (`_sdk_options.assert_oauth2_only()`) rejects `ANTHROPIC_API_KEY`. Use the OAuth2 token flow instead.

- [ ] Run `claude setup-token` (opens browser, completes OAuth2)
- [ ] Add to `.env` (NOT `.env.example` — `.env` is gitignored): `CLAUDE_CODE_OAUTH_TOKEN=<token-from-step>`
- [ ] Confirm `ANTHROPIC_API_KEY` is **not** set: `env | grep -i ANTHROPIC_API_KEY` → empty
- [ ] Source the env: `set -a; source .env; set +a` (or open a fresh shell)

### Step 1.2 — Linear MCP OAuth (one-time browser flow)

- [ ] Activate venv: `source .venv/bin/activate`
- [ ] Trigger the cached token flow:
  ```bash
  python -c "import asyncio; from hsb.agents.linear_agent import run_linear_agent; asyncio.run(run_linear_agent('List Linear teams. Return JSON: {\"operation\":\"read\",\"result\":\"success\",\"linear_entities\":[],\"error\":null}'))"
  ```
- [ ] Browser tab opens → log into Linear → grant access → close tab
- [ ] Python call completes and prints tool calls (token cached at `~/.mcp-remote/`)

### Step 1.3 — Test workspace env vars

- [ ] In Linear: Settings → Workspace → Teams → click your sandbox team. Copy the team ID from the URL.
  ```bash
  export LINEAR_TEST_TEAM_ID=<team-id>
  ```
- [ ] In Linear: create one sandbox issue you don't mind being mutated. Note its ID:
  ```bash
  export LINEAR_TEST_ISSUE_ID=LIN-XXX
  ```
- [ ] Persist these in `.env` if you want them across shells.

**Group 1 sign-off:** ⬜ Bootstrap complete on `__________` (date)

---

## Group 2 — Phase 2: Core Execution Agents ⏱ ~20 min

**Goal:** All 4 execution agents pass live integration tests; idempotency holds.

**Source:** `.planning/phases/02-core-execution-agents/02-HUMAN-UAT.md`

**Prerequisites:** Group 1 ✓ + `hsb-test-fixture` GitHub repo accessible (clone/fork of `https://github.com/hugo-hsbtech/hsb-test-fixture` if needed).

### Step 2.1 — Backlog Agent (BKPK-01..05)

- [ ] `pytest tests/integration/test_backlog_agent.py -v` → 5 PASS
- [ ] Open Linear UI: confirm EPICs / User Stories / Tasks created with parent linkage and traceability comments
- [ ] **Idempotency check:** rerun the same command → 0 new EPICs created
- [ ] If any test fails: capture output, do not proceed

### Step 2.2 — Builder Agent (BLDR-01, BLDR-02, BLDR-04)

- [ ] `pytest tests/integration/test_builder_agent.py -v` → 3 PASS
- [ ] After run: `cd hsb-test-fixture && git log --oneline -3` — capability boundary check: HEAD unchanged from before the test (Builder must NOT commit)

### Step 2.3 — Git Agent (GITA-01..04)

- [ ] `pytest tests/integration/test_git_agent.py -v` → 4 PASS
- [ ] Open the GitHub PR the test created — verify:
  - [ ] Base branch matches `epic/LIN-...` regex (NOT `main`)
  - [ ] Branch name + PR title match the contract regex
  - [ ] `--force-with-lease` only (no plain `--force`)

### Step 2.4 — QA Agent (QAAG-01, QAAG-05)

- [ ] `pytest tests/integration/test_qa_agent.py -v` → 2 PASS
- [ ] Verify sentinel file (`tests/fixtures/qa_sentinel.txt` or per plan spec) is unmodified after QA run
- [ ] `QAOutput.cycle` increments 0 → 1 in the test output

**Group 2 sign-off:** ⬜ Phase 2 verified on `__________` (date) — update `02-HUMAN-UAT.md` summary block (`passed: 4`, `pending: 0`)

---

## Group 3 — Phase 3: WIO MVP cycle (D-02 context-budget validation) ⏱ ~10 min

**Goal:** A single Task moves todo → done through Intelligence → Builder → Git → QA → fix loop, and context budget stays in spec.

**Source:** `.planning/phases/03-work-item-orchestrator-and-single-cycle-mvp/03-04-SUMMARY.md`

**Prerequisites:** Group 2 ✓.

### Step 3.1 — Seed a fresh test task

- [ ] In Linear, create one new Task in `todo` state under your test User Story (parent must exist)
- [ ] `export TEST_WORK_ITEM_ID=LIN-XXX`

### Step 3.2 — Full lifecycle integration test

- [ ] `pytest tests/integration/test_orchestrator_e2e.py::test_full_lifecycle_todo_to_done -v` → PASS
- [ ] Confirm Task transitioned `todo → done` in Linear UI
- [ ] Confirm QA cycle cap not exceeded (max 3 — WORC-03)
- [ ] Confirm Step 1 enrichment + Step 5 storage left a comment + a knowledge entry

### Step 3.3 — Context budget check (D-02)

- [ ] Inspect WIO logs for `input_tokens` near session close-out
- [ ] Combined system prompt was ~14.4K chars after Phase 3; Phase 5 added skills 10+11. Confirm `input_tokens` < 200K throughout (G8 warns at 120K — should not fire on a single Task)

**Group 3 sign-off:** ⬜ Phase 3 MVP verified on `__________` (date)

---

## Group 4 — Phase 4: Parallel mode E2E (SC-5 acceptance gate) ⏱ ~15 min

**Goal:** Two-task concurrent run with optimistic claiming + worktree isolation passes the no-double-claim test.

**Source:** `.planning/phases/04-global-main-orchestrators-and-parallel-mode/04-04-SUMMARY.md`

**Prerequisites:** Group 3 ✓ + `.worktrees/` directory at repo root is empty (`git worktree list` shows only main).

### Step 4.1 — Seed parallel test tasks

- [ ] In Linear, create ≥2 fresh `todo` Tasks with **no blocking dependencies** between them
- [ ] (No env var needed — Main Orchestrator picks them up via Backlog Agent)

### Step 4.2 — Parallel-mode acceptance test

- [ ] `pytest tests/integration/test_parallel_mode_e2e.py::test_no_double_claim_parallel_two_tasks -v` → PASS
- [ ] Confirm both tasks moved off `todo` (one or both reached `done`, depending on QA outcome)
- [ ] Confirm Linear shows distinct claim comments — no double-claim race

### Step 4.3 — CLI smoke

- [ ] `hsb run --parallel` (with at least one ready task) → no errors, dispatches correctly
- [ ] After run: `git worktree list` → only main; `.worktrees/` should be empty (Pitfall C cleanup)

**Group 4 sign-off:** ⬜ Phase 4 parallel mode verified on `__________` (date) — update `04-04-SUMMARY.md` resume signal: `approved`

---

## Group 5 — Phase 5: GO/NO-GO matrix (5 Success Criteria + regressions) ⏱ ~20 min

**Goal:** All 5 Phase 5 Success Criteria pass; G1/G2 guardrails hold; Phase 4 regression is green; full unit suite is green.

**Source:** `.planning/phases/05-enhancement-agents/05-04-SUMMARY.md` (Operator Verification Contract)

**Prerequisites:** Group 4 ✓ + `knowledge/` has ≥1 pre-seeded entry under `knowledge/qa/` + a User Story with all child tasks QA-approved.

### Step 5.1 — SC-1: Intelligence enrichment retrieves knowledge before Builder

- [ ] `pytest tests/integration/test_wio_intelligence_enrichment.py::test_wio_step1_populates_knowledge_context -v` → PASS
- [ ] Open the test task in Linear; comments include an "Enrichment Report" or `knowledge_context` block

### Step 5.2 — SC-2: Intelligence writes 8-field knowledge entry after QA

- [ ] `pytest tests/integration/test_wio_intelligence_storage.py::test_wio_step5_writes_knowledge_entry -v` → PASS
- [ ] `ls knowledge/qa/ knowledge/implementation/ knowledge/patterns/` shows at least one new `.md` file
- [ ] Open the new entry — confirm all 8 fields present: `title`, `type`, `context`, `evidence`, `insight`, `recommendation`, `applicability`, `date`
- [ ] `applicability` is non-empty AND not the literal string "all tasks" / "n/a" / "tbd" (G9 validator)

### Step 5.3 — SC-3: UAT Agent validates User Story with scenario results

- [ ] `pytest tests/integration/test_uat_agent.py::test_uat_validates_user_story_with_all_tasks_approved -v` → PASS
- [ ] `pytest tests/integration/test_global_orchestrator_uat.py::test_uat_dispatch_on_all_tasks_approved -v` → PASS
- [ ] Open the User Story in Linear → `uat_status` updated (`approved` or `changes_required` — both valid)

### Step 5.4 — SC-4: Risk Agent priority queue consumed by Global Orchestrator

- [ ] `pytest tests/integration/test_global_orchestrator_phase5.py::test_ready_tasks_sorted_by_risk_score -v` → PASS
- [ ] `GlobalOrchestratorOutput.ready_tasks` order matches `RiskAgent.get_priority_queue()` for the same Linear state

### Step 5.5 — SC-5a (binding): improvement triggers automated path

- [ ] `pytest tests/unit/test_risk_agent_triggers.py::test_sc5_positive_path_returns_trigger_for_seeded_qa_history -v` → PASS
- [ ] Test confirms ≥1 `AutoImprovementTrigger` returned; every trigger has `linear_state == "suggested"` and `len(pattern_evidence) >= 2`

### Step 5.6 — SC-5b (smoke): live SDK + RISK-04 confirmation

- [ ] Run the live SDK snippet:
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
- [ ] Every printed `linear_state == 'suggested'`
- [ ] Every `evidence_count >= 2`
- [ ] **Open Linear and verify NO new issues were created** (RISK-04 — the strongest milestone-level invariant)

### Step 5.7 — G1 OAuth2-only regression smoke

- [ ] `env | grep -i ANTHROPIC_API_KEY` → empty
- [ ] `python -c "from hsb.agents.uat_agent import run_uat_and_validate"` → no error
- [ ] `python -c "from hsb.agents.risk_agent import RiskAgent"` → no error
- [ ] `python -c "from hsb.agents.global_orchestrator import GlobalOrchestrator"` → no error

### Step 5.8 — G2 no-sub-subagent-dispatch smoke

- [ ] `grep -r '"Agent"' src/hsb/agents/ | grep -v "_FORBIDDEN_TOOLS\|test_\|Agent SDK\|forbidden"` → no matches except in comments / forbidden-tools set / SDK references

### Step 5.9 — Phase 4 regression

- [ ] `pytest tests/integration/test_global_orchestrator_e2e.py tests/integration/test_parallel_mode_e2e.py -v` → all PASS or SKIP with documented reason
- [ ] `hsb run --help` shows `--parallel` flag still registered
- [ ] `hsb run-next-step --help` (Phase 3 retained per D-11) still registered

### Step 5.10 — Full unit suite

- [ ] `pytest tests/unit/ -x -q` → exit 0; 106 tests pass

**Group 5 sign-off:** ⬜ Phase 5 GO/NO-GO verified on `__________` (date) — update `05-04-SUMMARY.md` resume signal: `approved`

---

## Milestone close-out

After all 5 group sign-offs:

- [ ] Update each phase's STATE.md / VERIFICATION.md to mark operator checkpoint resolved
- [ ] Run `/gsd-progress --forensic` for the 6-check integrity audit
- [ ] Run `/gsd-complete-milestone` to archive v1.0 and prepare v2.0 planning

**v1.0 milestone fully signed off on:** `__________` (date)

---

## Rollback / Failure handling

If any step fails:

1. **Capture full output** to a scratch file
2. **Do not proceed** to the next group — failures cascade
3. **Open `/gsd-debug`** with the failing test name and the captured output — the systematic-debugging skill is designed for this
4. **For guardrail violations** (G1/G2/G4/G5/G6/G9/G10): treat as BLOCKER. These are structural invariants — a regression here means the executor fixed the symptom without honoring the invariant
5. **For Linear-state issues** (e.g., wrong `uat_status` field, missing comments): check the Linear MCP `linear_*` tool names — Phase 5 G6 fix verified `issueId` (camelCase) is the correct payload key

If you discover the **fix would change autonomous code**, the right path is `/gsd-discuss-phase {N}` → `/gsd-plan-phase {N} --gaps` → re-execute. The plan-checker iteration loop catches most regressions before they ship.
