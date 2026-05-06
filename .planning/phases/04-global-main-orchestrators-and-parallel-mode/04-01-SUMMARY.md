---
phase: 04-global-main-orchestrators-and-parallel-mode
plan: 01
status: complete
completed: 2026-05-06
requirements:
  - GORD-01
  - GORD-02
  - GORD-03
  - GORD-04
  - MORD-01
  - MORD-02
  - MORD-03
  - MORD-04
  - MORD-05
key-files:
  created:
    - src/hsb/contracts/global_orchestrator.py
    - src/hsb/contracts/main_orchestrator.py
    - tests/unit/test_global_orchestrator.py
    - tests/unit/test_main_orchestrator.py
    - tests/integration/test_global_orchestrator_e2e.py
    - tests/integration/test_parallel_mode_e2e.py
    - .claude/skills/global-orchestration/SKILL.md
    - .claude/skills/main-orchestrator/SKILL.md
  modified:
    - .gitignore
---

# Plan 04-01 Summary: Phase 4 Foundation (Contracts + Stubs + SKILL.md)

## What Was Built

**Phase 4 scaffolding only — zero production logic.** Establishes the contract
surface, test stub coverage, and SKILL.md migrations that subsequent plans
(02 Global Orchestrator, 03 Main Orchestrator, 04 CLI integration) bind to.

### Pydantic Contracts

- `src/hsb/contracts/global_orchestrator.py` — `ReadyTask`, `GlobalOrchestratorOutput`
  per AGENT-CONTRACTS.md §0 + CONTEXT.md D-03. Both forbid extra fields.
- `src/hsb/contracts/main_orchestrator.py` — `ClaimResult`, `DispatchedItem`,
  `MainOrchestratorOutput` per AGENT-CONTRACTS.md §0 + D-04. All three forbid
  extras. `final_status` enum extends the spec with `"exception"` to cover
  Pitfall E (asyncio.gather exception normalization).

### Test Stubs (Wave 0 / Nyquist enforcement)

| File | Behavior stubs | Functional tests |
|------|---------------|------------------|
| `tests/unit/test_global_orchestrator.py` | 4 (GORD-01..04) | 2 (output contract + extra-field rejection) |
| `tests/unit/test_main_orchestrator.py` | 8 (MORD-01..04 incl alias + D-01/D-02 + parallel routing) | 2 (output contract + extra-field rejection) |
| `tests/integration/test_global_orchestrator_e2e.py` | 5 (GORD-01..04 live + MORD-05) | — |
| `tests/integration/test_parallel_mode_e2e.py` | 3 (MORD-03 gate + alias + D-09 cleanup) | — |

Every behavior stub fails with the literal string `"Wave 0 stub"` so a grep
confirms completeness (26 markers total). Test collection succeeds without
import errors at Wave 0 because behavior stubs do not import not-yet-existing
agent modules — they fail at `pytest.fail(...)` when the test body runs.

### SKILL.md Migrations

- `.claude/skills/global-orchestration/SKILL.md` — frontmatter +
  verbatim body of `skills/07-GLOBAL-ORCHESTRATION.md`.
- `.claude/skills/main-orchestrator/SKILL.md` — frontmatter +
  verbatim body of `skills/00-MAIN-ORCHESTRATOR.md`.

Both have `disable-model-invocation: true` (these are reference docs for pure
Python classes — they must not auto-invoke during conversation). Source skill
files at `skills/07-GLOBAL-ORCHESTRATION.md` and `skills/00-MAIN-ORCHESTRATOR.md`
are unchanged (Phase 1 D-07 pattern).

### .gitignore

Appended `# Phase 4: transient git worktrees created by parallel mode` /
`.worktrees/` entry. Mitigates Threat T-4-03 — transient runtime worktrees
never enter version control.

## Verification Run

```
pytest tests/unit/test_global_orchestrator.py::test_global_orchestrator_output_contract \
       tests/unit/test_global_orchestrator.py::test_global_orchestrator_output_extra_field_rejected \
       tests/unit/test_main_orchestrator.py::test_main_orchestrator_output_contract \
       tests/unit/test_main_orchestrator.py::test_dispatched_item_extra_field_rejected -v
4 passed in 0.09s

pytest tests/unit/test_global_orchestrator.py tests/unit/test_main_orchestrator.py --collect-only -q
16 tests collected in 0.07s
```

## Tasks Completed

- Task 1: Phase 4 pydantic contracts and `.gitignore` worktrees entry
- Task 2: Wave 0 test stubs for all 9 Phase 4 requirement IDs
- Task 3: SKILL.md migrations for global-orchestration and main-orchestrator

## Self-Check

- [x] All 9 files exist (2 contracts, 4 tests, 2 SKILL.md, 1 .gitignore touched)
- [x] All 5 pydantic models load and validate sample data
- [x] 4 functional contract tests pass
- [x] All 14 behavior stubs fail with "Wave 0 stub" marker
- [x] Test collection on `tests/unit/` succeeds (16 tests collected)
- [x] Both SKILL.md files have correct frontmatter + `disable-model-invocation: true`
- [x] `.worktrees/` entry exists in `.gitignore`
- [x] Source skill files at `skills/` are unchanged (git status clean for those paths)

## Self-Check: PASSED

## What This Enables

- **Plan 02:** GlobalOrchestrator implementation has `GlobalOrchestratorOutput`
  to instantiate and 4 GORD-01..04 unit stubs to fill in.
- **Plan 03:** MainOrchestrator implementation has `MainOrchestratorOutput`,
  `DispatchedItem`, `ClaimResult` to bind to and 8 MORD-01..04 + D-01/D-02
  unit stubs to satisfy.
- **Plan 04:** CLI integration plus operator MVP test has 8 integration stubs
  (5 GORD live + 3 MORD parallel gate) ready to fill in.
