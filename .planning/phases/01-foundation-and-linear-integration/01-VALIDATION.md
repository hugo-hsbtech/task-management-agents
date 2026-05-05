---
phase: 1
slug: foundation-and-linear-integration
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-05
revised: 2026-05-05
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Test IDs reconciled with the actual test files created by Plans 01-05 (revision 1).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (Wave 0 installs via Plan 01 pyproject.toml) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` section — Plan 01 creates) |
| **Quick run command** | `pytest tests/test_contracts.py tests/test_hooks.py -x` |
| **Full suite command** | `pytest tests/ -x --ignore=tests/test_integration.py` |
| **Estimated runtime** | ~15 seconds (unit only), ~120 seconds (full with integration) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_contracts.py tests/test_hooks.py -x` (once those files exist after Plans 02-03)
- **After every plan wave:** Run `pytest tests/ -x --ignore=tests/test_integration.py`
- **Before `/gsd-verify-work`:** Full suite (including integration) must be green
- **Max feedback latency:** 15 seconds (unit tests)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | FOUND-02 | — | pyproject.toml contains no secrets | smoke | `pip install -e . && hsb --help` | Plan 01 | ⬜ pending |
| 1-01-02 | 01 | 1 | FOUND-04 | — | knowledge/ category dirs exist | smoke | `test -d knowledge/architecture && test -d knowledge/qa && test -d knowledge/implementation && test -d knowledge/backlog && test -d knowledge/risk` | Plan 01 (inline verify) | ⬜ pending |
| 1-02-01 | 02 | 2 | FOUND-03 | T-1-01 | Pydantic extra fields raise ValidationError | unit | `pytest tests/test_contracts.py -x` | Plan 02 | ⬜ pending |
| 1-03-01 | 03 | 2 | LINR-05 | — | Retry max 3; backoff 1s/2s/4s; audit log written | unit | `pytest tests/test_hooks.py -x` | Plan 03 | ⬜ pending |
| 1-04-01 | 04 | 3 | LINR-05 | — | Agent loop wires hooks + validation | smoke | `pytest tests/test_hooks.py tests/test_contracts.py -x` (regression after wiring) | Plan 04 (re-runs existing) | ⬜ pending |
| 1-05-01 | 05 | 4 | LINR-01..04 | — | CLI dispatches to validated agent | unit | `pytest tests/test_cli.py -x` | Plan 05 | ⬜ pending |
| 1-05-02 | 05 | 4 | FOUND-01 | — | Linear MCP connects; prefix = mcp__linear__ | integration | `pytest tests/test_integration.py::test_mcp_connection_and_tool_prefix -x -m integration` | Plan 05 | ⬜ pending |
| 1-05-03 | 05 | 4 | LINR-01 | — | EPIC -> User Story -> Task -> Subtask with parentId (full 4-level hierarchy) | integration | `pytest tests/test_integration.py::test_create_epic tests/test_integration.py::test_create_user_story_under_epic tests/test_integration.py::test_create_task_under_epic tests/test_integration.py::test_create_subtask_under_task -x -m integration` | Plan 05 | ⬜ pending |
| 1-05-04 | 05 | 4 | LINR-02 | — | update status (standard) + qa_status / uat_status / assigned_orchestrator (custom fields, agent-selected mechanism) | integration | `pytest tests/test_integration.py::test_update_issue_status tests/test_integration.py::test_update_issue_custom_fields -x -m integration` | Plan 05 | ⬜ pending |
| 1-05-05 | 05 | 4 | LINR-02 (UI) | — | Operator visually confirms custom field values in Linear UI per RESEARCH.md OQ1 resolution | manual | HUMAN-SETUP.md Step 5b (operator-driven, recorded in checkpoint resume-signal) | Plan 05 | ⬜ pending |
| 1-05-06 | 05 | 4 | LINR-03 | — | Structured comment body written to Linear | integration | `pytest tests/test_integration.py::test_add_comment -x -m integration` | Plan 05 | ⬜ pending |
| 1-05-07 | 05 | 4 | LINR-04 | — | PR URL linked to Linear issue | integration | `pytest tests/test_integration.py::test_link_pr -x -m integration` | Plan 05 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 / Plan-Created Test Files

These test files are created by the plans listed; no separate "Wave 0" exists in this phase because Plan 01 ships `pyproject.toml` (with pytest config) plus directory scaffolding, and subsequent plans add their own test files alongside production code:

- [ ] `tests/conftest.py` — created by **Plan 02** (shared fixtures: mock Linear MCP response payloads, sample LinearOutput JSON)
- [ ] `tests/test_contracts.py` — created by **Plan 02** (pydantic validation unit tests for FOUND-03, schema drift detection)
- [ ] `tests/test_hooks.py` — created by **Plan 03** (retry hook unit tests for LINR-05 timing, attempt count, updatedAt logic, audit log write, list filter enforcement, PreCompact)
- [ ] `tests/test_cli.py` — created by **Plan 05** (typer CliRunner smoke tests for all 4 LINR commands)
- [ ] `tests/test_integration.py` — created by **Plan 05** (live MCP tests marked `@pytest.mark.integration`; 9 tests covering FOUND-01, LINR-01 4-level hierarchy, LINR-02 status + custom fields, LINR-03, LINR-04)
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and `markers = ["integration: requires live Linear MCP connection"]` — created by **Plan 01**
- [ ] Framework install (`pytest`, `pytest-asyncio` declared as dev deps in pyproject.toml) — installed via `pip install -e .[dev]` after Plan 01

**Note:** No separate `tests/test_knowledge_store.py` is created. FOUND-04 (knowledge directory existence) is verified by an inline `test -d` shell check in Plan 01's `<verify><automated>` block — directory existence is a one-liner; a dedicated pytest module would add ceremony without value.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OAuth 2.1 browser flow completes successfully | FOUND-01 | Requires interactive browser; can't automate in CI | Run `python -c "import asyncio; from hsb.agents.linear_agent import run_linear_agent; asyncio.run(run_linear_agent('ping'))"` in a session with a browser available; confirm OAuth tab opens and token is cached at `~/.mcp-remote/`. Per HUMAN-SETUP.md Step 2. |
| Linear MCP tool prefix is `mcp__linear__` (not `mcp__claude_ai_Linear__`) | FOUND-01 | Runtime inspection of SystemMessage init | Run any Linear Agent CLI command with `LOGLEVEL=DEBUG`; observe `[TOOL] mcp__linear__*` in output. Per Plan 05 Task 3 Step 2. |
| LINR-02 custom fields (qa_status / uat_status / assigned_orchestrator) visible in Linear UI | LINR-02 | RESEARCH.md OQ1 resolved as agent-selected fallback (native field / label / structured comment); only a human can confirm the chosen mechanism actually surfaces in the UI | After `test_update_issue_custom_fields` passes, open `LINEAR_TEST_ISSUE_ID` in Linear UI; confirm qa_status / uat_status / assigned_orchestrator visible as native field, label, or structured comment. Per HUMAN-SETUP.md Step 5b. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (revised: every Per-Task row above has a concrete command or "manual" justification)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (verified by inspection of Per-Task table)
- [x] Wave 0 covers all MISSING references (revised: removed phantom `test_knowledge_store.py` reference; all listed test files map to a creating plan)
- [x] No watch-mode flags
- [x] Feedback latency < 15s (unit tests)
- [x] `nyquist_compliant: true` set in frontmatter (revised: every required test file is created by a named plan; manual-only verifications have explicit operator instructions)

**Approval:** ready for execution
