# Settings Consistent Module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land `src/hsb/settings/` — seven independent `pydantic_settings.BaseSettings` subclasses, one per env-var domain — relocate the G1 forbidden-API-key list/helper into `settings/runtime.py`, and migrate one smoke-test consumer (`HSB_CLAIM_DELAY_MS` in `main_orchestrator.py`) to prove the wiring.

**Architecture:** Each settings class is a direct subclass of `BaseSettings` with its own `env_prefix` declared in `model_config`. No shared base, no `env_file` declaration, no aggregator. Settings read from `os.environ`; the existing 9 `load_dotenv()` calls (untouched) populate `os.environ` at module import. `_sdk_options.py` re-imports `assert_oauth2_only` from `settings/runtime.py` after the relocation — no behavior change.

**Tech Stack:** `pydantic>=2.0` (already a dependency), `pydantic-settings>=2.0` (new), Python 3.12+. TDD with `pytest` + `monkeypatch.setenv`.

**Spec:** `docs/superpowers/plans/../specs/2026-05-11-settings-consistent-module-design.md`

---

## File Structure

**Created:**

```
src/hsb/settings/
├── __init__.py                                 # re-exports each Settings class
├── runtime.py                                  # RuntimeSettings + FORBIDDEN_API_KEY_VARS + assert_oauth2_only
├── codex.py                                    # CodexSettings
├── linear.py                                   # LinearSettings
├── github.py                                   # GitHubSettings
├── orchestrator.py                             # OrchestratorSettings
├── wio_ipc.py                                  # WIOIPCSettings
└── test_fixture.py                             # TestFixtureSettings

tests/unit/settings/
├── test_runtime.py
├── test_codex.py
├── test_linear.py
├── test_github.py
├── test_orchestrator.py
├── test_wio_ipc.py
├── test_test_fixture.py
└── test_main_orchestrator_smoke.py
```

**Modified:**

- `pyproject.toml` — add `pydantic-settings>=2.0` to `dependencies`.
- `src/hsb/agents/_sdk_options.py` — delete local `_FORBIDDEN_API_KEY_VARS` and `assert_oauth2_only()`; replace with `from hsb.settings.runtime import assert_oauth2_only`.
- `src/hsb/agents/main_orchestrator.py:39` — replace `int(os.environ.get("HSB_CLAIM_DELAY_MS", "200"))` with `OrchestratorSettings().claim_delay_ms`.

**Untouched:** every other `os.environ.get` / `load_dotenv()` call site, all production agents, the entire `tests/integration/` suite, `tests/conftest.py`, `.env`, `.env.example`.

---

## Conventions

- **Venv path:** all `pytest` / `pip` commands run via `/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m …`. The worktree has no `.venv/`; we share the main repo's venv.
- **Working directory:** the worktree root `/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.claude/worktrees/feat+settings-consistent-module`.
- **Commit style:** Conventional Commits (`feat(settings): …`, `test(settings): …`, `refactor(sdk-options): …`). Match the recent log.
- **Test isolation:** every settings test uses `monkeypatch.setenv` / `monkeypatch.delenv`. **Never** mutate `os.environ` directly.
- **Skip `__init__.py` in `tests/unit/settings/`:** pytest discovers subdirs without it; matching existing `tests/unit/` style.

---

## Task 1: Add pydantic-settings dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current `[project]` dependencies block**

Read `pyproject.toml` lines 1-15 to confirm the dependency list shape (already inspected during brainstorming — should match the file structure section above).

- [ ] **Step 2: Add `pydantic-settings>=2.0` to dependencies**

Edit `pyproject.toml`. In the `dependencies = [...]` array under `[project]`, add `"pydantic-settings>=2.0",` after the `"pydantic>=2.0",` line. The block should read:

```toml
dependencies = [
    "claude-agent-sdk>=0.1.73",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "typer>=0.12",
    "rich>=13.0",
    "python-dotenv>=1.0",
    "openai-codex-sdk>=0.1.11",
]
```

- [ ] **Step 3: Install the dependency**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pip install -e ".[dev]" --quiet
```

Expected: install completes without errors; pip reports `pydantic-settings` installed.

- [ ] **Step 4: Verify import works**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -c "from pydantic_settings import BaseSettings, SettingsConfigDict; print('ok')"
```

Expected output: `ok`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build(deps): add pydantic-settings>=2.0 for hsb.settings module"
```

---

## Task 2: Create the package and OrchestratorSettings (TDD)

**Files:**
- Create: `src/hsb/settings/__init__.py`
- Create: `src/hsb/settings/orchestrator.py`
- Create: `tests/unit/settings/test_orchestrator.py`

`OrchestratorSettings` is the smallest production class. We start here because the smoke-test consumer (Task 9) depends on it, and the test pattern it establishes (monkeypatch + default + override + validation) repeats for every other class.

- [ ] **Step 1: Create the empty package `__init__.py`**

```bash
mkdir -p src/hsb/settings tests/unit/settings
```

Write `src/hsb/settings/__init__.py`:

```python
"""Per-domain settings classes. Import the one your code needs:

    from hsb.settings.orchestrator import OrchestratorSettings

This package has no top-level aggregator by design — see
docs/superpowers/specs/2026-05-11-settings-consistent-module-design.md §4.
Re-exports below are populated as each domain class lands.
"""
```

- [ ] **Step 2: Write the failing test**

Write `tests/unit/settings/test_orchestrator.py`:

```python
"""Tests for hsb.settings.orchestrator.OrchestratorSettings."""

import pytest
from pydantic import ValidationError


def test_claim_delay_ms_default_is_200(monkeypatch):
    monkeypatch.delenv("HSB_CLAIM_DELAY_MS", raising=False)
    from hsb.settings.orchestrator import OrchestratorSettings

    assert OrchestratorSettings().claim_delay_ms == 200


def test_claim_delay_ms_reads_env(monkeypatch):
    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "500")
    from hsb.settings.orchestrator import OrchestratorSettings

    assert OrchestratorSettings().claim_delay_ms == 500


def test_claim_delay_ms_rejects_negative(monkeypatch):
    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "-1")
    from hsb.settings.orchestrator import OrchestratorSettings

    with pytest.raises(ValidationError):
        OrchestratorSettings()


def test_project_default(monkeypatch):
    monkeypatch.delenv("HSB_PROJECT", raising=False)
    from hsb.settings.orchestrator import OrchestratorSettings

    assert OrchestratorSettings().project == "task-management-agents"


def test_project_reads_env(monkeypatch):
    monkeypatch.setenv("HSB_PROJECT", "org-acme")
    from hsb.settings.orchestrator import OrchestratorSettings

    assert OrchestratorSettings().project == "org-acme"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_orchestrator.py -x -q
```

Expected: 5 errors (collection or import), `ModuleNotFoundError: No module named 'hsb.settings.orchestrator'`.

- [ ] **Step 4: Implement OrchestratorSettings**

Write `src/hsb/settings/orchestrator.py`:

```python
"""Operational tuning knobs read by Main Orchestrator and Docker Compose
scaffolding.

Env vars: HSB_CLAIM_DELAY_MS, HSB_PROJECT.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorSettings(BaseSettings):
    """HSB_CLAIM_DELAY_MS (claim debounce, ms) and HSB_PROJECT (Docker Compose project scope)."""

    model_config = SettingsConfigDict(env_prefix="HSB_")

    claim_delay_ms: int = Field(default=200, ge=0)
    project: str = "task-management-agents"
```

- [ ] **Step 5: Run test to verify it passes**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_orchestrator.py -x -q
```

Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/hsb/settings/__init__.py src/hsb/settings/orchestrator.py tests/unit/settings/test_orchestrator.py
git commit -m "feat(settings): add OrchestratorSettings + package scaffolding"
```

---

## Task 3: CodexSettings (TDD)

**Files:**
- Create: `src/hsb/settings/codex.py`
- Create: `tests/unit/settings/test_codex.py`

- [ ] **Step 1: Write the failing test**

Write `tests/unit/settings/test_codex.py`:

```python
"""Tests for hsb.settings.codex.CodexSettings."""

from pathlib import Path


def test_home_default_is_none(monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    from hsb.settings.codex import CodexSettings

    assert CodexSettings().home is None


def test_home_reads_env_as_path(monkeypatch):
    monkeypatch.setenv("CODEX_HOME", "/root/.codex")
    from hsb.settings.codex import CodexSettings

    settings = CodexSettings()
    assert settings.home == Path("/root/.codex")
    assert isinstance(settings.home, Path)


def test_path_override_default_is_none(monkeypatch):
    monkeypatch.delenv("CODEX_PATH_OVERRIDE", raising=False)
    from hsb.settings.codex import CodexSettings

    assert CodexSettings().path_override is None


def test_path_override_reads_env_as_path(monkeypatch):
    monkeypatch.setenv("CODEX_PATH_OVERRIDE", "/usr/local/bin/codex")
    from hsb.settings.codex import CodexSettings

    assert CodexSettings().path_override == Path("/usr/local/bin/codex")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_codex.py -x -q
```

Expected: `ModuleNotFoundError: No module named 'hsb.settings.codex'`.

- [ ] **Step 3: Implement CodexSettings**

Write `src/hsb/settings/codex.py`:

```python
"""Codex CLI configuration.

Read by `runtime/codex.py` (CODEX_PATH_OVERRIDE) and `runtime/codex_guards.py` (CODEX_HOME).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class CodexSettings(BaseSettings):
    """CODEX_HOME (Codex auth dir) and CODEX_PATH_OVERRIDE (explicit codex binary path)."""

    model_config = SettingsConfigDict(env_prefix="CODEX_")

    home: Path | None = None
    path_override: Path | None = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_codex.py -x -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/settings/codex.py tests/unit/settings/test_codex.py
git commit -m "feat(settings): add CodexSettings (CODEX_HOME, CODEX_PATH_OVERRIDE)"
```

---

## Task 4: LinearSettings (TDD)

**Files:**
- Create: `src/hsb/settings/linear.py`
- Create: `tests/unit/settings/test_linear.py`

- [ ] **Step 1: Write the failing test**

Write `tests/unit/settings/test_linear.py`:

```python
"""Tests for hsb.settings.linear.LinearSettings."""

from pydantic import SecretStr


def test_api_key_default_is_none(monkeypatch):
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    from hsb.settings.linear import LinearSettings

    assert LinearSettings().api_key is None


def test_api_key_reads_env_as_secretstr(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test_token")
    from hsb.settings.linear import LinearSettings

    settings = LinearSettings()
    assert isinstance(settings.api_key, SecretStr)
    assert settings.api_key.get_secret_value() == "lin_api_test_token"


def test_api_key_does_not_leak_in_repr(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test_token")
    from hsb.settings.linear import LinearSettings

    settings = LinearSettings()
    assert "lin_api_test_token" not in repr(settings)
    assert "lin_api_test_token" not in str(settings)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_linear.py -x -q
```

Expected: `ModuleNotFoundError: No module named 'hsb.settings.linear'`.

- [ ] **Step 3: Implement LinearSettings**

Write `src/hsb/settings/linear.py`:

```python
"""Linear MCP fallback authentication.

Phase 1 prefers OAuth via mcp-remote (D-01); the API-key path is the
headless/CI fallback. Env var: LINEAR_API_KEY.
"""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LinearSettings(BaseSettings):
    """Optional Linear API key for non-OAuth Linear MCP authentication."""

    model_config = SettingsConfigDict(env_prefix="LINEAR_")

    api_key: SecretStr | None = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_linear.py -x -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/settings/linear.py tests/unit/settings/test_linear.py
git commit -m "feat(settings): add LinearSettings (LINEAR_API_KEY)"
```

---

## Task 5: GitHubSettings (TDD)

**Files:**
- Create: `src/hsb/settings/github.py`
- Create: `tests/unit/settings/test_github.py`

- [ ] **Step 1: Write the failing test**

Write `tests/unit/settings/test_github.py`:

```python
"""Tests for hsb.settings.github.GitHubSettings."""

from pydantic import SecretStr


def test_token_default_is_none(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    from hsb.settings.github import GitHubSettings

    assert GitHubSettings().token is None


def test_token_reads_env_as_secretstr(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    from hsb.settings.github import GitHubSettings

    settings = GitHubSettings()
    assert isinstance(settings.token, SecretStr)
    assert settings.token.get_secret_value() == "ghp_test_token_value"


def test_token_does_not_leak_in_repr(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    from hsb.settings.github import GitHubSettings

    settings = GitHubSettings()
    assert "ghp_test_token_value" not in repr(settings)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_github.py -x -q
```

Expected: `ModuleNotFoundError: No module named 'hsb.settings.github'`.

- [ ] **Step 3: Implement GitHubSettings**

Write `src/hsb/settings/github.py`:

```python
"""Optional GitHub PAT for non-interactive `gh auth login --with-token`.

If absent, operator uses the interactive device flow. Env var: GITHUB_TOKEN.
"""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    """Optional Personal Access Token for non-interactive `gh auth login`."""

    model_config = SettingsConfigDict(env_prefix="GITHUB_")

    token: SecretStr | None = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_github.py -x -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/settings/github.py tests/unit/settings/test_github.py
git commit -m "feat(settings): add GitHubSettings (GITHUB_TOKEN)"
```

---

## Task 6: WIOIPCSettings (TDD)

**Files:**
- Create: `src/hsb/settings/wio_ipc.py`
- Create: `tests/unit/settings/test_wio_ipc.py`

- [ ] **Step 1: Write the failing test**

Write `tests/unit/settings/test_wio_ipc.py`:

```python
"""Tests for hsb.settings.wio_ipc.WIOIPCSettings."""

from pathlib import Path


def test_defaults_are_none(monkeypatch):
    monkeypatch.delenv("HSB_WIO_INPUT_FILE", raising=False)
    monkeypatch.delenv("HSB_WIO_OUTPUT_FILE", raising=False)
    from hsb.settings.wio_ipc import WIOIPCSettings

    settings = WIOIPCSettings()
    assert settings.input_file is None
    assert settings.output_file is None


def test_reads_env_as_paths(monkeypatch):
    monkeypatch.setenv("HSB_WIO_INPUT_FILE", "/tmp/wio-in.json")
    monkeypatch.setenv("HSB_WIO_OUTPUT_FILE", "/tmp/wio-out.json")
    from hsb.settings.wio_ipc import WIOIPCSettings

    settings = WIOIPCSettings()
    assert settings.input_file == Path("/tmp/wio-in.json")
    assert settings.output_file == Path("/tmp/wio-out.json")
    assert isinstance(settings.input_file, Path)
    assert isinstance(settings.output_file, Path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_wio_ipc.py -x -q
```

Expected: `ModuleNotFoundError: No module named 'hsb.settings.wio_ipc'`.

- [ ] **Step 3: Implement WIOIPCSettings**

Write `src/hsb/settings/wio_ipc.py`:

```python
"""File paths for the WIO subprocess IPC handshake.

Set by Main Orchestrator before invoking the WIO subprocess; read by WIO
at startup. Env vars: HSB_WIO_INPUT_FILE, HSB_WIO_OUTPUT_FILE.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class WIOIPCSettings(BaseSettings):
    """Subprocess IPC paths written by main_orchestrator, read by WIO."""

    model_config = SettingsConfigDict(env_prefix="HSB_WIO_")

    input_file: Path | None = None
    output_file: Path | None = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_wio_ipc.py -x -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/settings/wio_ipc.py tests/unit/settings/test_wio_ipc.py
git commit -m "feat(settings): add WIOIPCSettings (HSB_WIO_INPUT_FILE, HSB_WIO_OUTPUT_FILE)"
```

---

## Task 7: TestFixtureSettings (TDD)

**Files:**
- Create: `src/hsb/settings/test_fixture.py`
- Create: `tests/unit/settings/test_test_fixture.py`

Note: this class uses `validation_alias` on every field (no `env_prefix`) because the env vars don't share a single stem (`HSB_TEST_FIXTURE_*`, `HSB_LIVE_CODEX`, `TEST_WORK_ITEM_ID`, `LINEAR_TEST_ISSUE_ID`).

- [ ] **Step 1: Write the failing test**

Write `tests/unit/settings/test_test_fixture.py`:

```python
"""Tests for hsb.settings.test_fixture.TestFixtureSettings."""

from pathlib import Path


def test_all_defaults_when_unset(monkeypatch):
    for var in (
        "HSB_TEST_FIXTURE_URL",
        "HSB_TEST_FIXTURE_PATH",
        "HSB_LIVE_CODEX",
        "TEST_WORK_ITEM_ID",
        "LINEAR_TEST_ISSUE_ID",
    ):
        monkeypatch.delenv(var, raising=False)

    from hsb.settings.test_fixture import TestFixtureSettings

    s = TestFixtureSettings()
    assert s.fixture_url is None
    assert s.fixture_path is None
    assert s.live_codex is False
    assert s.test_work_item_id is None
    assert s.linear_test_issue_id is None


def test_fixture_url_alias(monkeypatch):
    monkeypatch.setenv("HSB_TEST_FIXTURE_URL", "https://github.com/me/hsb-test-fixture")
    from hsb.settings.test_fixture import TestFixtureSettings

    assert (
        TestFixtureSettings().fixture_url
        == "https://github.com/me/hsb-test-fixture"
    )


def test_fixture_path_alias(monkeypatch):
    monkeypatch.setenv("HSB_TEST_FIXTURE_PATH", "/tmp/fixture")
    from hsb.settings.test_fixture import TestFixtureSettings

    assert TestFixtureSettings().fixture_path == Path("/tmp/fixture")


def test_live_codex_truthy(monkeypatch):
    monkeypatch.setenv("HSB_LIVE_CODEX", "1")
    from hsb.settings.test_fixture import TestFixtureSettings

    assert TestFixtureSettings().live_codex is True


def test_live_codex_falsy(monkeypatch):
    monkeypatch.setenv("HSB_LIVE_CODEX", "0")
    from hsb.settings.test_fixture import TestFixtureSettings

    assert TestFixtureSettings().live_codex is False


def test_test_work_item_id_alias(monkeypatch):
    monkeypatch.setenv("TEST_WORK_ITEM_ID", "LIN-999")
    from hsb.settings.test_fixture import TestFixtureSettings

    assert TestFixtureSettings().test_work_item_id == "LIN-999"


def test_linear_test_issue_id_alias(monkeypatch):
    monkeypatch.setenv("LINEAR_TEST_ISSUE_ID", "LIN-555")
    from hsb.settings.test_fixture import TestFixtureSettings

    assert TestFixtureSettings().linear_test_issue_id == "LIN-555"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_test_fixture.py -x -q
```

Expected: `ModuleNotFoundError: No module named 'hsb.settings.test_fixture'`.

- [ ] **Step 3: Implement TestFixtureSettings**

Write `src/hsb/settings/test_fixture.py`:

```python
"""Integration-test fixture URLs, IDs, and opt-in flags.

Tests construct this and skip when fields are unset (current pattern via
`_require_*` helpers). No env_prefix — each field uses `validation_alias`
because the env vars don't share a single stem.

Env vars: HSB_TEST_FIXTURE_URL, HSB_TEST_FIXTURE_PATH, HSB_LIVE_CODEX,
TEST_WORK_ITEM_ID, LINEAR_TEST_ISSUE_ID.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class TestFixtureSettings(BaseSettings):
    """Integration-test fixture configuration. All fields optional."""

    fixture_url: str | None = Field(
        default=None,
        validation_alias="HSB_TEST_FIXTURE_URL",
    )
    fixture_path: Path | None = Field(
        default=None,
        validation_alias="HSB_TEST_FIXTURE_PATH",
    )
    live_codex: bool = Field(
        default=False,
        validation_alias="HSB_LIVE_CODEX",
    )
    test_work_item_id: str | None = Field(
        default=None,
        validation_alias="TEST_WORK_ITEM_ID",
    )
    linear_test_issue_id: str | None = Field(
        default=None,
        validation_alias="LINEAR_TEST_ISSUE_ID",
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_test_fixture.py -x -q
```

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/settings/test_fixture.py tests/unit/settings/test_test_fixture.py
git commit -m "feat(settings): add TestFixtureSettings (validation_alias bindings)"
```

---

## Task 8: RuntimeSettings — fields, validators, WIO hard-block (TDD)

**Files:**
- Create: `src/hsb/settings/runtime.py`
- Create: `tests/unit/settings/test_runtime.py`

This task adds the **fields and runtime-selection logic only**. The G1 helper (`FORBIDDEN_API_KEY_VARS` + `assert_oauth2_only`) and its tests come in Task 9 to keep this task scoped.

- [ ] **Step 1: Write the failing test**

Write `tests/unit/settings/test_runtime.py`:

```python
"""Tests for hsb.settings.runtime.RuntimeSettings (fields + WIO hard-block)."""

import pytest
from pydantic import SecretStr, ValidationError

_AGENT_RUNTIME_VARS = (
    "HSB_RUNTIME_BACKLOG",
    "HSB_RUNTIME_WIO",
    "HSB_RUNTIME_QA",
    "HSB_RUNTIME_UAT",
    "HSB_RUNTIME_RISK",
    "HSB_RUNTIME_GIT",
    "HSB_RUNTIME_BUILDER",
    "HSB_RUNTIME_INTELLIGENCE",
    "HSB_RUNTIME_LINEAR",
)


def _clear_runtime_env(monkeypatch):
    for var in (*_AGENT_RUNTIME_VARS, "CLAUDE_CODE_OAUTH_TOKEN"):
        monkeypatch.delenv(var, raising=False)


def test_all_agents_default_to_claude(monkeypatch):
    _clear_runtime_env(monkeypatch)
    from hsb.settings.runtime import RuntimeSettings

    s = RuntimeSettings()
    assert s.backlog == "claude"
    assert s.wio == "claude"
    assert s.qa == "claude"
    assert s.uat == "claude"
    assert s.risk == "claude"
    assert s.git == "claude"
    assert s.builder == "claude"
    assert s.intelligence == "claude"
    assert s.linear == "claude"


def test_backlog_can_be_codex(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "codex")
    from hsb.settings.runtime import RuntimeSettings

    assert RuntimeSettings().backlog == "codex"


def test_runtime_value_is_normalized_lower_stripped(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "  CODEX  ")
    from hsb.settings.runtime import RuntimeSettings

    assert RuntimeSettings().backlog == "codex"


def test_wio_cannot_be_codex(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HSB_RUNTIME_WIO", "codex")
    from hsb.settings.runtime import RuntimeSettings

    with pytest.raises(ValidationError):
        RuntimeSettings()


def test_invalid_runtime_value_raises(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "gemini")
    from hsb.settings.runtime import RuntimeSettings

    with pytest.raises(ValidationError):
        RuntimeSettings()


def test_oauth_token_default_is_none(monkeypatch):
    _clear_runtime_env(monkeypatch)
    from hsb.settings.runtime import RuntimeSettings

    assert RuntimeSettings().claude_code_oauth_token is None


def test_oauth_token_reads_alias(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-claude-oauth-test")
    from hsb.settings.runtime import RuntimeSettings

    s = RuntimeSettings()
    assert isinstance(s.claude_code_oauth_token, SecretStr)
    assert s.claude_code_oauth_token.get_secret_value() == "sk-claude-oauth-test"


def test_oauth_token_does_not_leak_in_repr(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-claude-oauth-test")
    from hsb.settings.runtime import RuntimeSettings

    assert "sk-claude-oauth-test" not in repr(RuntimeSettings())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_runtime.py -x -q
```

Expected: `ModuleNotFoundError: No module named 'hsb.settings.runtime'`.

- [ ] **Step 3: Implement RuntimeSettings**

Write `src/hsb/settings/runtime.py`:

```python
"""Per-agent runtime selection + Claude OAuth token.

Env vars: HSB_RUNTIME_<AGENT> (one per known agent) and
CLAUDE_CODE_OAUTH_TOKEN (sourced via validation_alias because it does
not share the HSB_RUNTIME_ prefix).

WIO is hard-frozen to "claude" because the stateful ClaudeSDKClient
session has no Codex equivalent (tracked separately). Passing
HSB_RUNTIME_WIO=codex raises ValidationError at construction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    """Per-agent runtime selection + Claude OAuth token."""

    model_config = SettingsConfigDict(env_prefix="HSB_RUNTIME_")

    # OAuth token — sourced by validation_alias because it doesn't share
    # the HSB_RUNTIME_ prefix. In pydantic-settings v2, a field's
    # validation_alias bypasses the class-level env_prefix.
    claude_code_oauth_token: SecretStr | None = Field(
        default=None,
        validation_alias="CLAUDE_CODE_OAUTH_TOKEN",
    )

    # Per-agent runtime selection. Explicit fields, one per known agent.
    backlog: Literal["claude", "codex"] = "claude"
    wio: Literal["claude"] = "claude"  # hard-blocked from "codex"
    qa: Literal["claude", "codex"] = "claude"
    uat: Literal["claude", "codex"] = "claude"
    risk: Literal["claude", "codex"] = "claude"
    git: Literal["claude", "codex"] = "claude"
    builder: Literal["claude", "codex"] = "claude"
    intelligence: Literal["claude", "codex"] = "claude"
    linear: Literal["claude", "codex"] = "claude"

    @field_validator(
        "backlog",
        "qa",
        "uat",
        "risk",
        "git",
        "builder",
        "intelligence",
        "linear",
        "wio",
        mode="before",
    )
    @classmethod
    def _normalize_runtime(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @model_validator(mode="after")
    def _wio_is_claude_only(self) -> "RuntimeSettings":
        if self.wio != "claude":
            raise ValueError(
                "WIO is not flippable yet — stateful ClaudeSDKClient session "
                "has no Codex equivalent. Track separately when porting WIO."
            )
        return self
```

- [ ] **Step 4: Run test to verify it passes**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_runtime.py -x -q
```

Expected: `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/settings/runtime.py tests/unit/settings/test_runtime.py
git commit -m "feat(settings): add RuntimeSettings — per-agent runtime + OAuth token"
```

---

## Task 9: Relocate G1 (FORBIDDEN_API_KEY_VARS + assert_oauth2_only) into settings/runtime.py

**Files:**
- Modify: `src/hsb/settings/runtime.py` — add the two symbols.
- Modify: `tests/unit/settings/test_runtime.py` — extend with G1-parity tests.
- Modify: `src/hsb/agents/_sdk_options.py` — delete local definitions, import from new location.

The G1 helper's exact bytes (function body, error message string) MUST be preserved verbatim — any change to the error format could break grep-based logs / alerts. After this task, calling `hsb.agents._sdk_options.assert_oauth2_only()` and `hsb.settings.runtime.assert_oauth2_only()` returns the same function object.

- [ ] **Step 1: Append G1-parity tests to `tests/unit/settings/test_runtime.py`**

Add the following at the end of the file (after the last test):

```python
# --- G1 parity tests (relocated from _sdk_options.py) ---


def test_forbidden_vars_constant():
    from hsb.settings.runtime import FORBIDDEN_API_KEY_VARS

    assert FORBIDDEN_API_KEY_VARS == ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def test_assert_oauth2_only_noop_when_clear(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from hsb.settings.runtime import assert_oauth2_only

    # Should not raise.
    assert_oauth2_only()


def test_assert_oauth2_only_raises_on_anthropic(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "leaked")
    from hsb.settings.runtime import assert_oauth2_only

    with pytest.raises(RuntimeError) as exc:
        assert_oauth2_only()
    assert "G1 violation" in str(exc.value)
    assert "ANTHROPIC_API_KEY" in str(exc.value)


def test_assert_oauth2_only_raises_on_openai(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "leaked")
    from hsb.settings.runtime import assert_oauth2_only

    with pytest.raises(RuntimeError) as exc:
        assert_oauth2_only()
    assert "OPENAI_API_KEY" in str(exc.value)


def test_assert_oauth2_only_reexported_from_sdk_options(monkeypatch):
    """_sdk_options re-exports the relocated helper — same callable object."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from hsb.agents._sdk_options import assert_oauth2_only as via_sdk_options
    from hsb.settings.runtime import assert_oauth2_only as via_settings

    assert via_sdk_options is via_settings
```

- [ ] **Step 2: Run the new tests — expect failure**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_runtime.py::test_forbidden_vars_constant tests/unit/settings/test_runtime.py::test_assert_oauth2_only_reexported_from_sdk_options -x -q
```

Expected: failures — `ImportError: cannot import name 'FORBIDDEN_API_KEY_VARS'` and the identity check fails because `_sdk_options.assert_oauth2_only` is still the local function, not the re-import.

- [ ] **Step 3: Add `import os` to `src/hsb/settings/runtime.py`**

If `import os` is not already present (it isn't — Task 8's RuntimeSettings only needs `typing.Literal` and pydantic imports), add it to the stdlib import block, immediately after `from __future__ import annotations`:

```python
from __future__ import annotations

import os
from typing import Literal
```

- [ ] **Step 4: Copy the G1 constant + helper verbatim from `_sdk_options.py`**

Open `src/hsb/agents/_sdk_options.py` and read lines 41-65 (the `_FORBIDDEN_TOOLS` line through the closing `)` of the `raise RuntimeError(...)` call).

Copy lines **43-65 only** (skip line 41, which is the G2 `_FORBIDDEN_TOOLS` set unrelated to G1; skip the blank line 42).

Paste them into `src/hsb/settings/runtime.py` immediately **after** the import block and **before** the `class RuntimeSettings(BaseSettings):` line.

Then apply exactly one edit to the pasted block: rename `_FORBIDDEN_API_KEY_VARS` (both the definition and the in-function reference) to `FORBIDDEN_API_KEY_VARS` — dropping the leading underscore. Add the type annotation `: tuple[str, ...]` to the constant declaration for mypy strictness:

```python
# Pasted from _sdk_options.py lines 43-65, with one rename:
#   _FORBIDDEN_API_KEY_VARS  →  FORBIDDEN_API_KEY_VARS  (now public)
# Function body, docstring, and error message are byte-identical to the
# original.

FORBIDDEN_API_KEY_VARS: tuple[str, ...] = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def assert_oauth2_only() -> None:
    """G1 (AI-SPEC §6) — function-entry-time guard. Rejects metered API keys
    for either runtime. Operators must use OAuth tokens:
      - Claude:  CLAUDE_CODE_OAUTH_TOKEN  (from `claude setup-token`)
      - Codex:   ~/.codex/auth.json       (from `codex login --device-auth`)

    Called from :func:`make_options` before every ``ClaudeAgentOptions``
    construction. Function-time (NOT module-import-time) so test environments
    that legitimately have ``ANTHROPIC_API_KEY`` set for unrelated reasons do
    not break pytest collection. The defensive pairing is the session-scoped
    autouse fixture in ``tests/conftest.py`` that unsets the env var at
    session start.
    """
    forbidden = [v for v in FORBIDDEN_API_KEY_VARS if v in os.environ]
    if forbidden:
        raise RuntimeError(
            f"G1 violation: {', '.join(forbidden)} set — forbidden. "
            "Use OAuth tokens only (CLAUDE_CODE_OAUTH_TOKEN for Claude, "
            "`codex login --device-auth` for Codex)."
        )
```

**Do not** paraphrase the docstring, reflow lines, qualify the `:func:` reference, or alter the error-message format string. The exact bytes must be preserved so grep-based log filters / alert rules that match on the error string keep working.

- [ ] **Step 5: Update `src/hsb/agents/_sdk_options.py` to import the helper instead of defining it**

In `src/hsb/agents/_sdk_options.py`:

Replace lines 43-65 (the `_FORBIDDEN_API_KEY_VARS = …` constant through the end of the `assert_oauth2_only()` function body — including the closing `)` of the `raise RuntimeError(...)` call) with:

```python
from hsb.settings.runtime import (
    FORBIDDEN_API_KEY_VARS as _FORBIDDEN_API_KEY_VARS,  # noqa: F401  re-export
    assert_oauth2_only,  # noqa: F401  re-export
)
```

Place this import alongside the other `from claude_agent_sdk` imports near the top of the file (the file's import ordering convention is standard-lib → third-party → first-party). `_FORBIDDEN_API_KEY_VARS` keeps its underscore-prefixed alias to avoid breaking any importer that referenced the original private name.

- [ ] **Step 6: Run the full settings test suite**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/ -x -q
```

Expected: all settings tests pass (including the 5 new G1-parity tests).

- [ ] **Step 7: Run the existing unit suite — confirm no regressions**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit -x -q
```

Expected: original 111 tests still pass, plus the new settings tests. Final tally should be 111 + (5 from orchestrator + 4 from codex + 3 from linear + 3 from github + 2 from wio_ipc + 7 from test_fixture + 8 from runtime fields + 5 from G1 parity) = 111 + 37 = **148 passed**.

If `test_wio_oauth2_guard_present` (in `tests/unit/test_wio_allowed_tools.py`) fails, stop — it should not, since it reads `work_item_orchestrator.py` docstring not `_sdk_options.py`. Investigate before continuing.

- [ ] **Step 8: Commit**

```bash
git add src/hsb/settings/runtime.py src/hsb/agents/_sdk_options.py tests/unit/settings/test_runtime.py
git commit -m "refactor(g1): relocate FORBIDDEN_API_KEY_VARS + assert_oauth2_only to hsb.settings.runtime

_sdk_options.py re-imports both symbols (the underscore-aliased
constant and the function) so existing call sites and fully-qualified
names continue to resolve. Function body and error message are
byte-identical to the previous version."
```

---

## Task 10: Smoke-test migration — main_orchestrator HSB_CLAIM_DELAY_MS

**Files:**
- Modify: `src/hsb/agents/main_orchestrator.py:39`
- Create: `tests/unit/settings/test_main_orchestrator_smoke.py`

- [ ] **Step 1: Write the failing test**

Write `tests/unit/settings/test_main_orchestrator_smoke.py`:

```python
"""Smoke-test parity check: main_orchestrator.CLAIM_DELAY_MS uses
OrchestratorSettings as the env-var source."""

import importlib

import pytest


def _reload_main_orchestrator():
    """Force a fresh module-level read of CLAIM_DELAY_MS."""
    import hsb.agents.main_orchestrator as mo

    return importlib.reload(mo)


def test_claim_delay_ms_default(monkeypatch):
    monkeypatch.delenv("HSB_CLAIM_DELAY_MS", raising=False)
    mo = _reload_main_orchestrator()
    assert mo.CLAIM_DELAY_MS == 200
    assert isinstance(mo.CLAIM_DELAY_MS, int)


def test_claim_delay_ms_reads_env(monkeypatch):
    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "750")
    mo = _reload_main_orchestrator()
    assert mo.CLAIM_DELAY_MS == 750


def test_claim_delay_ms_rejects_negative(monkeypatch):
    from pydantic import ValidationError

    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "-1")
    with pytest.raises(ValidationError):
        _reload_main_orchestrator()
```

- [ ] **Step 2: Run test to verify it fails or passes pre-migration**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_main_orchestrator_smoke.py -x -q
```

Expected: `test_claim_delay_ms_default` and `test_claim_delay_ms_reads_env` pass (the existing implementation handles them); `test_claim_delay_ms_rejects_negative` **fails** because the current `int(os.environ.get(...))` accepts `-1` silently.

This is the desired "tightening" — the new implementation must reject negatives. Continue to the migration step.

- [ ] **Step 3: Migrate the call site**

In `src/hsb/agents/main_orchestrator.py`:

Replace the import block at lines 18-26 to remove the now-unused `os` import (only if `os` is unused elsewhere in the file — verify with a grep first; **do NOT remove `os` if any other call site uses it**):

```bash
grep -n "^import os\|\bos\.\b" src/hsb/agents/main_orchestrator.py
```

If `os` has other uses (it does — line 241 onwards in `_build_subprocess_env`), leave the import alone.

Then replace line 39:

```python
# Before:
CLAIM_DELAY_MS = int(os.environ.get("HSB_CLAIM_DELAY_MS", "200"))

# After:
from hsb.settings.orchestrator import OrchestratorSettings  # noqa: E402

CLAIM_DELAY_MS = OrchestratorSettings().claim_delay_ms
```

Place the `from hsb.settings.orchestrator import …` line **above** the `CLAIM_DELAY_MS = …` assignment, in module-level position (the `# noqa: E402` is defensive in case ruff complains about the placement — match the existing `[tool.ruff.lint.per-file-ignores]` style if needed).

If the import-after-`load_dotenv()` pattern feels awkward, an alternative placement is to add the import to the top-level imports block (lines 14-32). Pick whichever lands the test green; both behaviorally equivalent.

- [ ] **Step 4: Run smoke-test parity to confirm**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_main_orchestrator_smoke.py -x -q
```

Expected: **3 passed** — all three smoke tests now green.

- [ ] **Step 5: Run the full unit suite — no regressions**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit -x -q
```

Expected: all tests pass. **111 baseline + 37 new + 3 smoke = 151 passed.**

Particular attention: `tests/unit/test_main_orchestrator.py::test_main_orchestrator_*` should still pass — the `inspect.getsource` test at line 197 asserts only that `"**os.environ"` is not in the source (subprocess env safety, unaffected by this edit).

- [ ] **Step 6: Commit**

```bash
git add src/hsb/agents/main_orchestrator.py tests/unit/settings/test_main_orchestrator_smoke.py
git commit -m "feat(main-orchestrator): migrate HSB_CLAIM_DELAY_MS to OrchestratorSettings

Single smoke-test consumer per the spec's 'module-only, no migration'
policy. Tightens type validation — pydantic now rejects negative
debounce values, where the previous int(os.environ.get(...)) accepted
them silently."
```

---

## Task 11: Populate `__init__.py` re-export surface

**Files:**
- Modify: `src/hsb/settings/__init__.py`
- Create: `tests/unit/settings/test_init_reexports.py`

- [ ] **Step 1: Write the failing test**

Write `tests/unit/settings/test_init_reexports.py`:

```python
"""hsb.settings package-level re-exports — convenience surface."""


def test_orchestrator_settings_reexported():
    from hsb.settings import OrchestratorSettings as Reexport
    from hsb.settings.orchestrator import OrchestratorSettings as Original

    assert Reexport is Original


def test_codex_settings_reexported():
    from hsb.settings import CodexSettings as Reexport
    from hsb.settings.codex import CodexSettings as Original

    assert Reexport is Original


def test_linear_settings_reexported():
    from hsb.settings import LinearSettings as Reexport
    from hsb.settings.linear import LinearSettings as Original

    assert Reexport is Original


def test_github_settings_reexported():
    from hsb.settings import GitHubSettings as Reexport
    from hsb.settings.github import GitHubSettings as Original

    assert Reexport is Original


def test_wio_ipc_settings_reexported():
    from hsb.settings import WIOIPCSettings as Reexport
    from hsb.settings.wio_ipc import WIOIPCSettings as Original

    assert Reexport is Original


def test_test_fixture_settings_reexported():
    from hsb.settings import TestFixtureSettings as Reexport
    from hsb.settings.test_fixture import TestFixtureSettings as Original

    assert Reexport is Original


def test_runtime_settings_reexported():
    from hsb.settings import RuntimeSettings as Reexport
    from hsb.settings.runtime import RuntimeSettings as Original

    assert Reexport is Original


def test_g1_helpers_reexported():
    from hsb.settings import FORBIDDEN_API_KEY_VARS, assert_oauth2_only
    from hsb.settings.runtime import (
        FORBIDDEN_API_KEY_VARS as Original_Const,
        assert_oauth2_only as Original_Fn,
    )

    assert FORBIDDEN_API_KEY_VARS is Original_Const
    assert assert_oauth2_only is Original_Fn
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_init_reexports.py -x -q
```

Expected: failures — `ImportError: cannot import name 'OrchestratorSettings' from 'hsb.settings'`.

- [ ] **Step 3: Update `__init__.py` to re-export every class**

Replace the contents of `src/hsb/settings/__init__.py`:

```python
"""Per-domain settings classes. Import the one your code needs:

    from hsb.settings.orchestrator import OrchestratorSettings

This package has no top-level aggregator by design — see
docs/superpowers/specs/2026-05-11-settings-consistent-module-design.md §4.
The re-exports below are a convenience surface; per-module imports remain
the canonical pattern.
"""

from hsb.settings.codex import CodexSettings
from hsb.settings.github import GitHubSettings
from hsb.settings.linear import LinearSettings
from hsb.settings.orchestrator import OrchestratorSettings
from hsb.settings.runtime import (
    FORBIDDEN_API_KEY_VARS,
    RuntimeSettings,
    assert_oauth2_only,
)
from hsb.settings.test_fixture import TestFixtureSettings
from hsb.settings.wio_ipc import WIOIPCSettings

__all__ = [
    "FORBIDDEN_API_KEY_VARS",
    "CodexSettings",
    "GitHubSettings",
    "LinearSettings",
    "OrchestratorSettings",
    "RuntimeSettings",
    "TestFixtureSettings",
    "WIOIPCSettings",
    "assert_oauth2_only",
]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit/settings/test_init_reexports.py -x -q
```

Expected: `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/settings/__init__.py tests/unit/settings/test_init_reexports.py
git commit -m "feat(settings): populate package __init__.py re-exports"
```

---

## Task 12: Final verification — lint, type-check, full test sweep

**Files:** none modified; verification only.

- [ ] **Step 1: Run ruff lint**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m ruff check src/hsb/settings tests/unit/settings src/hsb/agents/_sdk_options.py src/hsb/agents/main_orchestrator.py
```

Expected: `All checks passed!` (or no errors).

If ruff complains about import ordering in `main_orchestrator.py`, restore the canonical import order — `from __future__` first, stdlib, third-party, then `hsb.*`. The `from hsb.settings.orchestrator import OrchestratorSettings` belongs in the first-party block.

- [ ] **Step 2: Run ruff format check**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m ruff format --check src/hsb/settings tests/unit/settings
```

Expected: `N files already formatted`.

If files need formatting, run `ruff format` (without `--check`) and amend the relevant commit. **Do not** create a separate "format" commit — fold into the relevant feature commit via `git commit --amend` only if the previous commit hasn't been pushed.

- [ ] **Step 3: Run mypy on the new module**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m mypy src/hsb/settings
```

Expected: `Success: no issues found in N source files`.

Any `Missing type stubs` warnings from pydantic-settings are acceptable per `ignore_missing_imports = true` in `pyproject.toml`. Real type errors must be fixed.

- [ ] **Step 4: Run the full unit suite**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/unit -x -q
```

Expected tally:
- 111 pre-existing tests
- 37 settings-class tests (5 + 4 + 3 + 3 + 2 + 7 + 8 + 5 G1)
- 3 smoke tests
- 8 re-export tests
- **Total: 159 passed.**

- [ ] **Step 5: Run the code-based evals (B1 UAT coverage + B3 banned-token regex)**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/evals/code_based -x -q
```

Expected: all evals pass. These are independent of the settings module but worth confirming as a defense-in-depth check.

- [ ] **Step 6: Confirm no integration regressions (collection only)**

```bash
/home/hugo/Dropbox/DevProjects/HSB/task-management-agents/.venv/bin/python -m pytest tests/integration --collect-only -q
```

Expected: all tests collect cleanly (most will skip without live env vars; that's expected). No `ImportError` / `ModuleNotFoundError` from any test module.

- [ ] **Step 7: Confirm clean git status + final log**

```bash
git status
git log --oneline main..HEAD
```

Expected status: clean (no uncommitted or untracked files in `src/` or `tests/`).

Expected log (12 commits — the spec commits already on the branch, plus 11 from this plan):

```
<commit-N>  test(settings): populate __init__.py re-exports
<commit-N-1> feat(main-orchestrator): migrate HSB_CLAIM_DELAY_MS to OrchestratorSettings
<commit-N-2> refactor(g1): relocate FORBIDDEN_API_KEY_VARS + assert_oauth2_only to hsb.settings.runtime
<commit-N-3> feat(settings): add RuntimeSettings — per-agent runtime + OAuth token
<commit-N-4> feat(settings): add TestFixtureSettings (validation_alias bindings)
<commit-N-5> feat(settings): add WIOIPCSettings (HSB_WIO_INPUT_FILE, HSB_WIO_OUTPUT_FILE)
<commit-N-6> feat(settings): add GitHubSettings (GITHUB_TOKEN)
<commit-N-7> feat(settings): add LinearSettings (LINEAR_API_KEY)
<commit-N-8> feat(settings): add CodexSettings (CODEX_HOME, CODEX_PATH_OVERRIDE)
<commit-N-9> feat(settings): add OrchestratorSettings + package scaffolding
<commit-N-10> build(deps): add pydantic-settings>=2.0 for hsb.settings module
… (spec commits)
```

- [ ] **Step 8: Push and report ready**

```bash
git push
```

Confirm the push lands on the existing remote tracking branch `origin/feat/settings-consistent-module`. No PR open yet — that comes after operator review.

---

## Self-Review Notes (post-plan)

**Spec coverage:**
- §4 file structure → Tasks 2-8, 11
- §5.1.* per-domain classes → one task each (Tasks 2-8)
- §6 G1 relocation → Task 9
- §7 smoke-test consumer → Task 10
- §8 pyproject.toml dep add → Task 1
- §9 test strategy → tests created in each task
- §10 consumer impact → exercised by Task 10 (only production change) and Task 12 (verification)
- §11 worktree/branch → handled at brainstorming time
- §12 out-of-scope → respected; no other call site touched

**Placeholder scan:** none.

**Type consistency:** `OrchestratorSettings.claim_delay_ms: int`, `CodexSettings.home: Path | None`, etc. — all field types referenced consistently across implementation and test code blocks.

**One known gotcha (worth re-stating at execution time):** Task 10's smoke-test parity tests use `importlib.reload(...)` on `hsb.agents.main_orchestrator` to force a fresh `CLAIM_DELAY_MS` read. This re-runs every module-top side effect, including `load_dotenv()`. If the worktree has a `.env` with `HSB_CLAIM_DELAY_MS=…`, the test must `monkeypatch.delenv` it before reload — which the test already does. If a future plan adds another module-level side effect (e.g., a Linear MCP probe), the reload may slow or fail; the alternative is to refactor `CLAIM_DELAY_MS` from a module constant into a `@lru_cache` function call, but that's out of scope here.
