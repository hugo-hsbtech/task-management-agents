# Settings Consistent Module — Design

**Date:** 2026-05-11
**Status:** Spec — pending implementation plan
**Branch:** `feat/settings-consistent-module`
**Related:** `2026-05-09-codex-oauth-alt-runtime-design.md` (consumer of `HSB_RUNTIME_<AGENT>`), `2026-05-11-multi-provider-module-design.md` (will consume the same env-var landscape via its consumer adapter).

---

## 1. Goal

Introduce a single, typed, FastAPI-style settings module so that every environment-variable read in the project goes through one well-understood surface. Today the project has:

- **9 separate `load_dotenv()` calls** scattered across `src/hsb/agents/*.py` and `run_loop.py`.
- **31 `os.environ.get(...)` call sites** with ad-hoc string parsing, inline defaults, and per-site type coercion.
- **No type-checking** of env-var values — `int(os.environ.get("HSB_CLAIM_DELAY_MS", "200"))` is the prevailing pattern.
- **No prefix discipline** — `HSB_`, `CODEX_`, `LINEAR_`, `GITHUB_`, and `TEST_*` env vars are mixed at every read site.

This spec lands `src/hsb/settings/` as the canonical home for environment-derived configuration. Each domain (runtime, codex, linear, github, orchestrator, WIO IPC, test fixtures) gets its own `pydantic-settings.BaseSettings` subclass with a domain-appropriate env prefix and field-level types. Consumers import the one they need; there is no top-level aggregator. The G1 forbidden-API-key check moves into the runtime module so the env-var list lives next to the rest of the runtime config.

This branch is **module-only, no migration** — we land the module, prove the wiring with a single smoke-test consumer (`HSB_CLAIM_DELAY_MS` in `main_orchestrator.py`), and leave the other 30 `os.environ.get` call sites untouched. Subsequent feature work migrates the remaining sites incrementally when it touches those areas.

## 2. Non-goals

- **Migrating every existing `os.environ.get` call site.** Explicitly out of scope. The smoke-test consumer in §6 is the single touched site beyond the module itself; the remaining 30 stay as-is until natural migration via downstream feature work.
- **Removing `python-dotenv` / the 9 `load_dotenv()` calls.** They are idempotent and harmless; removal is part of the future migration, not this branch.
- **Replacing `resolve_runtime(agent_name)` in `src/hsb/agents/_sdk_options.py`.** The function dynamically reads `HSB_RUNTIME_<AGENT>` at call time; codifying it via `RuntimeSettings` fields is a follow-up once the multi-provider module spec lands (which already restructures runtime resolution).
- **Mutating settings at runtime.** All settings are frozen at construction. There is no `set_value()` API. Operators change config by changing env / `.env` and restarting.
- **Replacing the G1 sentinel.** The G1 check (`assert_oauth2_only()`) stays a function-entry guard in `_sdk_options.py`. Its forbidden-vars list and helper move into `settings/runtime.py` so the runtime-config surface is unified; `_sdk_options.py` continues to call the helper at the same time, in the same way, with the same error message.
- **Settings-as-feature-flags.** This module is for environment-derived config (auth, paths, tuning knobs), not for in-process behavior toggles or runtime feature flags.

## 3. Context

The project's two earlier specs both leaned on environment variables for their selection logic: `2026-05-09-codex-oauth-alt-runtime-design.md` introduced `HSB_RUNTIME_<AGENT>`; `2026-05-11-multi-provider-module-design.md` adds `HSB_AUTH_ALLOW_API_KEY_<AGENT>` and continues to read `CODEX_HOME` / `CODEX_PATH_OVERRIDE`. Each of those modules reads env vars directly — there is no project-wide pattern for "where does config come from."

The result today, by file:

```
src/hsb/agents/_sdk_options.py        : 4 reads — CLAUDE_CODE_OAUTH_TOKEN doc, forbidden-keys list, HSB_RUNTIME_<AGENT>
src/hsb/agents/main_orchestrator.py   : 4 reads — HSB_CLAIM_DELAY_MS + 3 subprocess-env reads (PATH/HOME/ANTHROPIC_API_KEY)
src/hsb/runtime/codex.py              : 1 read  — CODEX_PATH_OVERRIDE
src/hsb/runtime/codex_guards.py       : 1 read  — CODEX_HOME
tests/conftest.py                     : 2 reads — defensive unset of ANTHROPIC_API_KEY, OPENAI_API_KEY
tests/integration/*                   : 15 reads — fixture URLs, test issue IDs, opt-in flags
```

Plus 9 `load_dotenv()` calls (no parsing — just dotenv loading), all at module import time. None of these reads coordinate. Each has its own default. Each parses its own type (`int`, `str`, the `.strip().lower()` dance for `HSB_RUNTIME_<AGENT>`). Each could quietly diverge.

`pydantic-settings` is the canonical FastAPI-ecosystem answer to this problem. The project already depends on `pydantic>=2.0` (FOUND-03 schema-drift defense). Adding `pydantic-settings>=2.0` is incremental and zero-friction.

## 4. Architecture

A new `src/hsb/settings/` package containing one **shared base** and one **per-domain settings class** per environment-variable group. No top-level aggregator. Consumers import what they need:

```python
from hsb.settings.orchestrator import OrchestratorSettings
CLAIM_DELAY_MS = OrchestratorSettings().claim_delay_ms
```

```
src/hsb/settings/
├── __init__.py        ← re-exports each Settings class (convenience only; no aggregator)
├── base.py            ← _HsbBaseSettings: shared env_file, extra="ignore", frozen=True, env_file resolved from repo root
├── runtime.py         ← RuntimeSettings + FORBIDDEN_API_KEY_VARS + assert_oauth2_only()
├── codex.py           ← CodexSettings  (CODEX_HOME, CODEX_PATH_OVERRIDE)
├── linear.py          ← LinearSettings (LINEAR_API_KEY)
├── github.py          ← GitHubSettings (GITHUB_TOKEN)
├── orchestrator.py    ← OrchestratorSettings (HSB_CLAIM_DELAY_MS, HSB_PROJECT)
├── wio_ipc.py         ← WIOIPCSettings (HSB_WIO_INPUT_FILE, HSB_WIO_OUTPUT_FILE)
└── test_fixture.py    ← TestFixtureSettings (HSB_TEST_FIXTURE_*, HSB_LIVE_CODEX, TEST_WORK_ITEM_ID, LINEAR_TEST_ISSUE_ID)
```

**Invariants:**

1. **Per-domain isolation.** Each settings class owns exactly one concern. No class mixes runtime auth with test-fixture URLs. Consumers import only what they consume.
2. **One shared base.** `_HsbBaseSettings` centralizes the `.env` file location, the `extra="ignore"` policy, the `frozen=True` mutability rule, and the `case_sensitive=False` env-var match. Subclasses declare only their `env_prefix` and their fields.
3. **No top-level aggregator.** There is no `Settings(_HsbBaseSettings)` that wraps every domain class. The compositional cost of importing two classes when an agent needs both is acceptable; the cost of having one mega-class that imports every dep at startup is not.
4. **Frozen.** Every settings instance is immutable post-construction (`model_config = SettingsConfigDict(frozen=True)`). Operators reconfigure by changing env / `.env` and restarting.
5. **No SDK imports at module top.** Settings classes are pure pydantic; they have no transitive dependency on `claude_agent_sdk`, `openai_codex_sdk`, `mcp_remote`, or any Linear/GitHub library.

## 5. Core abstractions

### 5.1 `_HsbBaseSettings`

```python
# src/hsb/settings/base.py
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class _HsbBaseSettings(BaseSettings):
    """Shared base for every per-domain settings class.

    Subclasses declare `env_prefix=` in their own `model_config`; pydantic-settings
    merges class-level config with parent config so subclasses inherit `extra`,
    `frozen`, and `case_sensitive` automatically."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )
```

Settings classes read from `os.environ`. The project's existing `load_dotenv()` calls (at module import in every agent file and `run_loop.py`) populate `.env` values into `os.environ` before any settings class is constructed — no `env_file` declaration is needed on the base, no duplication of dotenv loading.

### 5.2 Per-domain settings classes — field schemas

#### 5.2.1 `RuntimeSettings`

```python
# src/hsb/settings/runtime.py
from __future__ import annotations

import os
from typing import ClassVar, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from hsb.settings.base import _HsbBaseSettings

FORBIDDEN_API_KEY_VARS: tuple[str, ...] = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def assert_oauth2_only() -> None:
    """G1 — function-entry guard. Raises RuntimeError if any forbidden
    API-key env var is set.

    Moved verbatim from `_sdk_options.py`; `_sdk_options.py` imports and
    calls this helper, preserving the original call site and timing
    semantics. The forbidden-vars list lives here now so the runtime
    config surface is unified.
    """
    forbidden = [v for v in FORBIDDEN_API_KEY_VARS if v in os.environ]
    if forbidden:
        raise RuntimeError(
            f"G1 violation: {', '.join(forbidden)} set — forbidden. "
            "Use OAuth tokens only (CLAUDE_CODE_OAUTH_TOKEN for Claude, "
            "`codex login --device-auth` for Codex)."
        )


class RuntimeSettings(_HsbBaseSettings):
    """Per-agent runtime selection + Claude OAuth token.

    Each agent gets an explicit field. Adding an agent means adding a field
    here — discoverable by definition. WIO is hard-frozen to Claude via a
    model_validator; passing `HSB_RUNTIME_WIO=codex` raises at construction.
    """

    model_config = SettingsConfigDict(env_prefix="HSB_RUNTIME_")

    # OAuth token — sourced by validation_alias because it doesn't share
    # the HSB_RUNTIME_ prefix. In pydantic-settings v2, a field's
    # `validation_alias` bypasses the class-level `env_prefix` and is used
    # verbatim as the env-var name — so this field reads CLAUDE_CODE_OAUTH_TOKEN
    # rather than HSB_RUNTIME_CLAUDE_CODE_OAUTH_TOKEN.
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

    @model_validator(mode="after")
    def _wio_is_claude_only(self) -> "RuntimeSettings":
        if self.wio != "claude":
            raise ValueError(
                "WIO is not flippable yet — stateful ClaudeSDKClient session "
                "has no Codex equivalent. Track separately when porting WIO."
            )
        return self

    @field_validator(
        "backlog", "qa", "uat", "risk", "git", "builder", "intelligence", "linear",
        mode="before",
    )
    @classmethod
    def _normalize_runtime(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v
```

The `_normalize_runtime` `mode="before"` validator replicates the existing `.strip().lower()` behavior in `resolve_runtime()` so today's `HSB_RUNTIME_BACKLOG=" CODEX "` continues to parse.

**Why explicit fields per agent (not a `dict[str, str]`):** the current set of agents is closed and small; the WIO hard-block is structurally easier to express with a per-field validator; future agent additions force a discoverable edit to this file rather than a silent env-var convention.

#### 5.2.2 `CodexSettings`

```python
# src/hsb/settings/codex.py
from pathlib import Path
from pydantic_settings import SettingsConfigDict
from hsb.settings.base import _HsbBaseSettings


class CodexSettings(_HsbBaseSettings):
    """Codex CLI configuration. Read by `runtime/codex.py` and
    `runtime/codex_guards.py`."""

    model_config = SettingsConfigDict(env_prefix="CODEX_")

    home: Path | None = None              # CODEX_HOME
    path_override: Path | None = None     # CODEX_PATH_OVERRIDE
```

#### 5.2.3 `LinearSettings`

```python
# src/hsb/settings/linear.py
from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict
from hsb.settings.base import _HsbBaseSettings


class LinearSettings(_HsbBaseSettings):
    """Linear MCP fallback authentication. Phase 1 prefers OAuth via
    mcp-remote (D-01); the API-key path is the headless/CI fallback."""

    model_config = SettingsConfigDict(env_prefix="LINEAR_")

    api_key: SecretStr | None = None       # LINEAR_API_KEY
```

#### 5.2.4 `GitHubSettings`

```python
# src/hsb/settings/github.py
from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict
from hsb.settings.base import _HsbBaseSettings


class GitHubSettings(_HsbBaseSettings):
    """Optional PAT for non-interactive `gh auth login --with-token`.
    If absent, operator uses the interactive device flow."""

    model_config = SettingsConfigDict(env_prefix="GITHUB_")

    token: SecretStr | None = None         # GITHUB_TOKEN
```

#### 5.2.5 `OrchestratorSettings`

```python
# src/hsb/settings/orchestrator.py
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from hsb.settings.base import _HsbBaseSettings


class OrchestratorSettings(_HsbBaseSettings):
    """Operational tuning knobs read by Main Orchestrator and Docker
    Compose scaffolding."""

    model_config = SettingsConfigDict(env_prefix="HSB_")

    claim_delay_ms: int = Field(default=200, ge=0)        # HSB_CLAIM_DELAY_MS
    project: str = "task-management-agents"                # HSB_PROJECT
```

The `ge=0` constraint catches negative-debounce typos; matches the implicit assumption in `main_orchestrator.py`.

#### 5.2.6 `WIOIPCSettings`

```python
# src/hsb/settings/wio_ipc.py
from pathlib import Path
from pydantic_settings import SettingsConfigDict
from hsb.settings.base import _HsbBaseSettings


class WIOIPCSettings(_HsbBaseSettings):
    """File paths for the WIO subprocess IPC handshake. Set by Main
    Orchestrator before invoking the WIO subprocess; read by WIO at startup."""

    model_config = SettingsConfigDict(env_prefix="HSB_WIO_")

    input_file: Path | None = None        # HSB_WIO_INPUT_FILE
    output_file: Path | None = None       # HSB_WIO_OUTPUT_FILE
```

#### 5.2.7 `TestFixtureSettings`

```python
# src/hsb/settings/test_fixture.py
from pathlib import Path
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from hsb.settings.base import _HsbBaseSettings


class TestFixtureSettings(_HsbBaseSettings):
    """Integration-test fixture URLs, IDs, and opt-in flags.

    Each field uses `validation_alias` because the env vars don't share a
    single prefix. Tests construct this and skip when fields are unset
    (current pattern via `_require_*` helpers)."""

    # No env_prefix — each field aliases its full env-var name.

    fixture_url: str | None = Field(default=None, validation_alias="HSB_TEST_FIXTURE_URL")
    fixture_path: Path | None = Field(default=None, validation_alias="HSB_TEST_FIXTURE_PATH")
    live_codex: bool = Field(default=False, validation_alias="HSB_LIVE_CODEX")
    test_work_item_id: str | None = Field(default=None, validation_alias="TEST_WORK_ITEM_ID")
    linear_test_issue_id: str | None = Field(default=None, validation_alias="LINEAR_TEST_ISSUE_ID")
```

`bool` coercion for `HSB_LIVE_CODEX` follows pydantic's standard env-bool semantics (`"1"`, `"true"`, `"yes"` → True; others → False). The current code's `if "HSB_LIVE_CODEX" not in os.environ: skip` becomes `if not TestFixtureSettings().live_codex: skip`.

### 5.3 `__init__.py` re-export surface

```python
# src/hsb/settings/__init__.py
"""Per-domain settings classes. Import the one your code needs:

    from hsb.settings.orchestrator import OrchestratorSettings

This package has no top-level aggregator by design — see
docs/superpowers/specs/2026-05-11-settings-consistent-module-design.md §4."""

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
    "CodexSettings",
    "FORBIDDEN_API_KEY_VARS",
    "GitHubSettings",
    "LinearSettings",
    "OrchestratorSettings",
    "RuntimeSettings",
    "TestFixtureSettings",
    "WIOIPCSettings",
    "assert_oauth2_only",
]
```

## 6. G1 relocation

The G1 forbidden-vars list (`("ANTHROPIC_API_KEY", "OPENAI_API_KEY")`) and the `assert_oauth2_only()` helper move from `src/hsb/agents/_sdk_options.py` into `src/hsb/settings/runtime.py`.

`_sdk_options.py` keeps its call site verbatim — the import line changes only:

```python
# before
_FORBIDDEN_API_KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")

def assert_oauth2_only() -> None:
    forbidden = [v for v in _FORBIDDEN_API_KEY_VARS if v in os.environ]
    if forbidden:
        raise RuntimeError(...)


# after
from hsb.settings.runtime import assert_oauth2_only  # re-export

# (module-level FORBIDDEN_API_KEY_VARS deleted; assert_oauth2_only is now imported)
```

This is a pure move — same function body, same string formatting, same RuntimeError. **No existing tests break.** Two tests grep for the literal `"ANTHROPIC_API_KEY"`, but neither reads `_sdk_options.py`:

- `tests/unit/test_main_orchestrator.py:197` reads `main_orchestrator.py` source and asserts `"**os.environ" not in source` (subprocess env safety, T-4-04). Unaffected.
- `tests/unit/test_wio_allowed_tools.py:47` reads `work_item_orchestrator.py` source and asserts the WIO module's docstring still documents the G1 contract (the literal is in WIO's docstring at line 25, not in any imported module). Unaffected.

The session-scoped `_gsd_clear_api_key` autouse fixture in `tests/conftest.py` is unchanged (still does `os.environ.pop(...)` for both keys at session start).

A new G1-parity unit test in `tests/unit/settings/test_runtime.py` (see §9) covers the relocated function directly.

## 7. Smoke-test consumer

A single production read site is migrated to prove the wiring end-to-end:

```python
# src/hsb/agents/main_orchestrator.py
# before:
CLAIM_DELAY_MS = int(os.environ.get("HSB_CLAIM_DELAY_MS", "200"))

# after:
from hsb.settings.orchestrator import OrchestratorSettings
CLAIM_DELAY_MS = OrchestratorSettings().claim_delay_ms
```

The substitution:
- Preserves the default (`200`).
- Preserves the int type.
- Adds a `ge=0` constraint (negative debounce raises `ValidationError`, which is strictly tighter than the current `int(...)` parsing — a negative env value passed through silently before).
- No other call site is touched in this branch.

This is the **only production-code change outside of `src/hsb/settings/`**. Everything else is additive.

## 8. Dependencies

`pyproject.toml`:

```toml
[project]
dependencies = [
    "claude-agent-sdk>=0.1.73",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",          # ADDED
    "typer>=0.12",
    "rich>=13.0",
    "python-dotenv>=1.0",              # KEPT — transitional, 9 callers still depend on it
    "openai-codex-sdk>=0.1.11",
]
```

`pydantic-settings` 2.x depends on `pydantic>=2.0` (already pinned) and `python-dotenv>=0.21` (already pinned at `>=1.0`). No new transitive risk.

`python-dotenv` stays until the migration phase removes the 9 `load_dotenv()` calls. Removing it from `pyproject.toml` now would break those call sites; that work belongs in a follow-up.

## 9. Testing strategy

`tests/unit/settings/` — one file per domain class plus a shared base test:

```
tests/unit/settings/
├── test_base.py                    ← _find_env_file() walks up; settings frozen; extra="ignore"
├── test_runtime.py                 ← per-agent fields; wio="codex" raises; assert_oauth2_only() parity
├── test_codex.py                   ← CODEX_HOME / CODEX_PATH_OVERRIDE as Path; None defaults
├── test_linear.py                  ← LINEAR_API_KEY as SecretStr; repr does not leak value
├── test_github.py                  ← GITHUB_TOKEN as SecretStr; repr does not leak value
├── test_orchestrator.py            ← claim_delay_ms default 200; ge=0 rejects -1
├── test_wio_ipc.py                 ← HSB_WIO_INPUT_FILE / OUTPUT_FILE as Path
├── test_test_fixture.py            ← validation_alias bindings; live_codex bool coercion
└── test_main_orchestrator_smoke.py ← CLAIM_DELAY_MS == OrchestratorSettings().claim_delay_ms parity
```

Each test uses `monkeypatch.setenv` / `monkeypatch.delenv` (pytest fixture) — no real env mutation.

**Parity tests** for the smoke-test site:
- `CLAIM_DELAY_MS` retains type `int`.
- Default (`HSB_CLAIM_DELAY_MS` unset) gives `200`.
- `HSB_CLAIM_DELAY_MS=500` gives `500`.
- `HSB_CLAIM_DELAY_MS=-1` raises `ValidationError` (tightened from the previous silent acceptance).

**G1 parity tests** for the relocated helper:
- `assert_oauth2_only()` with `ANTHROPIC_API_KEY=x` raises `RuntimeError`.
- The error message is the same string (asserted by exact substring match) so any grep-based logs / alerts that filter on it continue to work.
- The re-export `from hsb.settings.runtime import assert_oauth2_only` is accessible from `hsb.agents._sdk_options.assert_oauth2_only` (i.e. the existing fully-qualified name resolves to the same function object).

**No existing structural tests need updating** (see §6 — both grep-based tests read files unrelated to the G1 relocation). The new G1-parity tests in `tests/unit/settings/test_runtime.py` cover the relocated function.

**No integration tests** are added by this branch — the smoke-test consumer is enough to prove the import path works end-to-end. The existing 111 unit tests continue to pass without modification (verified locally).

## 10. Consumer impact

### 10.1 Production code

| File | How it consumes today | Impact of this PR |
|---|---|---|
| `src/hsb/agents/main_orchestrator.py` | `int(os.environ.get("HSB_CLAIM_DELAY_MS", "200"))` | Migrated — uses `OrchestratorSettings()`. |
| `src/hsb/agents/_sdk_options.py` | Defines `_FORBIDDEN_API_KEY_VARS` + `assert_oauth2_only()` locally | Re-exports from `hsb.settings.runtime`. No behavior change. |
| `src/hsb/agents/work_item_orchestrator.py` | Reads `HSB_WIO_INPUT_FILE` / `OUTPUT_FILE` via `os.environ` | **Untouched.** `WIOIPCSettings` is available; not yet adopted. |
| Other 7 agents + `run_loop.py` | 9 `load_dotenv()` calls + various inline `os.environ.get` reads | **Untouched.** |
| `src/hsb/runtime/codex.py`, `codex_guards.py` | Inline `os.environ.get("CODEX_*")` | **Untouched.** `CodexSettings` is available; not yet adopted. |

### 10.2 Tests

| File | Impact |
|---|---|
| `tests/conftest.py` | **Untouched** — `_gsd_clear_api_key` fixture still pops the forbidden vars. |
| `tests/unit/test_main_orchestrator.py:197` | **Untouched** — still asserts `"**os.environ" not in source`. |
| `tests/unit/test_wio_allowed_tools.py:47` | **Untouched** — reads `work_item_orchestrator.py` docstring (G1 contract documentation), not `_sdk_options.py`. |
| `tests/integration/*` | **Untouched** — `_require_*` skip helpers continue to read `os.environ` directly. Migration to `TestFixtureSettings` is follow-up work. |

### 10.3 Operator surface

No new env vars. No renamed env vars. No removed env vars. `.env` and `.env.example` are unchanged. **Zero operator-visible change.**

## 11. Worktree and branch

This work happens in `feat/settings-consistent-module`, created via `EnterWorktree` and rooted at `origin/main` (not at `design/multi-provider-module`). The two specs are independent — settings reads env vars, the multi-provider module restructures runtime resolution. The multi-provider module will eventually consume `RuntimeSettings`/`CodexSettings` once both land, but neither blocks the other.

## 12. Out of scope (explicit)

- Migration of the other 30 `os.environ.get` call sites (see §10.1 "Untouched" rows).
- Removal of `python-dotenv` and the 9 `load_dotenv()` calls.
- Replacement of `resolve_runtime(agent_name)` in `_sdk_options.py` with `RuntimeSettings` field reads — that's part of the multi-provider module work.
- A new env-var-as-feature-flag pattern.
- Settings hot-reload / file watching.
- Any net-new env var beyond `HSB_ENV_FILE` (the module catalogs what exists; the only addition is the override hook itself).
