---
phase: 04-global-main-orchestrators-and-parallel-mode
plan: 02
status: complete
completed: 2026-05-06
requirements:
  - GORD-01
  - GORD-02
  - GORD-03
  - GORD-04
key-files:
  created:
    - src/hsb/agents/global_orchestrator.py
  modified:
    - tests/unit/test_global_orchestrator.py
---

# Plan 04-02 Summary: Global Orchestrator Implementation

## What Was Built

Pure Python `GlobalOrchestrator` class (D-01) at
`src/hsb/agents/global_orchestrator.py`. No Claude Agent SDK session, no LLM
invocation — only stdlib + dotenv + Phase 1 `run_validated_linear_agent` +
Phase 4 `GlobalOrchestratorOutput` contract.

### Class Structure

```python
class GlobalOrchestrator:
    async def get_ready_tasks(self) -> GlobalOrchestratorOutput  # Public
    def _filter_ready_items(self, all_items: list[dict]) -> list[dict]   # GORD-01 + GORD-02
    def _check_epic_complete(self, all_items: list[dict]) -> bool        # GORD-04
    async def _fetch_all_items(self) -> list[dict]                       # wraps run_validated_linear_agent
```

### Requirement Coverage

| Req | Behavior | Test |
|-----|----------|------|
| GORD-01 | Only `status='todo'` items returned | `test_returns_todo_only` (sync, exercises `_filter_ready_items`) |
| GORD-02 | Items with non-`done` deps excluded | `test_dependency_filter` (sync, exercises `_filter_ready_items`) |
| GORD-03 | Empty Linear → `is_backlog_empty=True` | `test_empty_backlog_signal` (async, mocks `_fetch_all_items` → `[]`) |
| GORD-04 | All non-epics done+approved → `is_epic_ready=True` | `test_epic_ready_signal` (async, mocks full set) |

### Sort Key

`(priority asc, createdAt asc)` per CONTEXT.md Claude's Discretion. `priority`
defaults to 999 so unset items sort last; `createdAt` is the deterministic
tiebreaker. Linear's priority field is `1=urgent, 2=high, 3=medium, 4=low,
0=none` — ascending sort surfaces urgent first.

### D-01 Architectural Property

Source-grep assertion built into `tests/unit/test_main_orchestrator.py::
test_no_sdk_session_in_global_orchestrator` (currently a Plan 03 stub — fills
in during Plan 04-03). The file does not import `claude_agent_sdk`,
`ClaudeAgentOptions`, or any LLM primitive.

## Verification Run

```
pytest tests/unit/test_global_orchestrator.py -v
6 passed in 0.43s
```

Functional contract tests (2) and behavior tests (4) all green.

```
python -c "from hsb.agents.global_orchestrator import GlobalOrchestrator; ..."
OK: GlobalOrchestrator pure Python class loaded, D-01 enforced
```

## Tasks Completed

- Task 1: Implement GlobalOrchestrator class with four methods (1 public async, 1 private async, 2 private sync)
- Task 2: Replace Wave 0 GORD-01..04 stubs with real assertions

## Self-Check

- [x] `src/hsb/agents/global_orchestrator.py` exists with `GlobalOrchestrator` class
- [x] All four methods present: `get_ready_tasks`, `_filter_ready_items`, `_check_epic_complete`, `_fetch_all_items`
- [x] D-01 architectural property holds — no `claude_agent_sdk` / `ClaudeAgentOptions` / `query(` / `create_sdk_mcp_server`
- [x] Imports `run_validated_linear_agent` from Phase 1 and `GlobalOrchestratorOutput`/`ReadyTask` from Plan 01
- [x] `load_dotenv()` at module level
- [x] Empty backlog branch returns `is_backlog_empty=True, ready_tasks=[], is_epic_ready=False`
- [x] Dependency filter excludes blocked items
- [x] EPIC completion check filters non-epic children
- [x] Sort key uses priority + createdAt
- [x] All 6 unit tests pass; no `Wave 0 stub` markers remain in this file

## Self-Check: PASSED

## What This Enables

- **Plan 03:** `MainOrchestrator` can `from hsb.agents.global_orchestrator
  import GlobalOrchestrator` and mock it via
  `patch("hsb.agents.main_orchestrator.GlobalOrchestrator")`. The class is
  ready to be called from `run_main_orchestrator(mode=...)`.
- **Plan 04:** Live integration tests in `tests/integration/
  test_global_orchestrator_e2e.py` (Wave 0 stubs) can be filled in to call the
  real `GlobalOrchestrator` against the Linear test workspace.
