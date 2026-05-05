---
phase: 1
slug: foundation-and-linear-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-05
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (not yet installed) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` section — Wave 0 installs) |
| **Quick run command** | `pytest tests/test_contracts.py tests/test_hooks.py -x` |
| **Full suite command** | `pytest tests/ -x --ignore=tests/test_integration.py` |
| **Estimated runtime** | ~15 seconds (unit only), ~120 seconds (full with integration) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_contracts.py tests/test_hooks.py -x`
- **After every plan wave:** Run `pytest tests/ -x --ignore=tests/test_integration.py`
- **Before `/gsd-verify-work`:** Full suite (including integration) must be green
- **Max feedback latency:** 15 seconds (unit tests)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | FOUND-02 | — | pyproject.toml contains no secrets | smoke | `pip install -e . && hsb --help` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | FOUND-03 | T-1-01 | Pydantic extra fields raise ValidationError | unit | `pytest tests/test_contracts.py -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | LINR-05 | — | Retry max 3; backoff 1s/2s/4s | unit | `pytest tests/test_hooks.py::test_retry_backoff -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 0 | FOUND-04 | — | knowledge/ dirs exist | smoke | `pytest tests/test_knowledge_store.py::test_directories_exist -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | FOUND-01 | — | Linear MCP connects; prefix = mcp__linear__ | integration | `pytest tests/test_integration.py::test_mcp_connection -x -m integration` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 2 | LINR-01 | — | EPIC→Story→Task→Subtask with parentId | integration | `pytest tests/test_integration.py::test_create_hierarchy -x -m integration` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 2 | LINR-02 | — | update status/qa_status/uat_status/assigned_orchestrator | integration | `pytest tests/test_integration.py::test_update_fields -x -m integration` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 2 | LINR-03 | — | Structured comment body written to Linear | integration | `pytest tests/test_integration.py::test_add_comment -x -m integration` | ❌ W0 | ⬜ pending |
| 1-02-05 | 02 | 2 | LINR-04 | — | PR URL linked to Linear issue | integration | `pytest tests/test_integration.py::test_link_pr -x -m integration` | ❌ W0 | ⬜ pending |
| 1-02-06 | 02 | 2 | LINR-05 | — | updatedAt before < updatedAt after each mutation | integration | `pytest tests/test_integration.py::test_updated_at_logging -x -m integration` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures (mock Linear MCP response payloads, sample LinearOutput JSON)
- [ ] `tests/test_contracts.py` — pydantic validation unit tests (FOUND-03, schema drift detection)
- [ ] `tests/test_hooks.py` — retry hook unit tests (LINR-05 timing, attempt count, updatedAt logic)
- [ ] `tests/test_knowledge_store.py` — directory existence smoke test (FOUND-04)
- [ ] `tests/test_integration.py` — live MCP tests marked `@pytest.mark.integration` (FOUND-01, LINR-01 through LINR-05)
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and `markers = ["integration: requires live Linear MCP connection"]`
- [ ] Framework install: `pip install pytest pytest-asyncio`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OAuth 2.1 browser flow completes successfully | FOUND-01 | Requires interactive browser; can't automate in CI | Run `python -c "import asyncio; from src.hsb.agents.linear_agent import run_linear_agent; asyncio.run(run_linear_agent('ping'))"` in a session with a browser available; confirm OAuth tab opens and token is cached at `~/.mcp-remote/` |
| Linear MCP tool prefix is `mcp__linear__` (not `mcp__claude_ai_Linear__`) | FOUND-01 | Runtime inspection of SystemMessage init | Run any Linear Agent CLI command with `LOGLEVEL=DEBUG`; observe `[TOOL] mcp__linear__*` in output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s (unit tests)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
