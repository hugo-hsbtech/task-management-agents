# Backlog Agent Codex Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Codex as a selectable LLM provider for the backlog agent, mirroring the Claude pattern.

**Architecture:** Add `CodexModel` enum and `ProviderName.codex` to `settings/provider.py` so Codex is a first-class provider option. Update `build_provider` in `backlog/agent.py` to map `ProviderName.codex` → the "openai" registry entry (Codex is the OAuth2-auth backend of `OpenAIProvider` in `llm_providers/providers/openai.py`). Add a parallel integration test to the one for Claude.

**Tech Stack:** Python, Pydantic v2, pydantic-settings, pytest, existing `llm_providers` library, `openai_codex_sdk` (already wired in `OpenAIProvider._CodexBackend`).

---

## Context for every task

- Repo root: `task-management-agents/`
- Source packages live under `src/` (e.g. `src/settings/`, `src/backlog/`, `src/llm_providers/`)
- Tests live under `tests/` (unit under `tests/unit/`, integration under `tests/integration/`)
- Run tests: `uv run pytest <path> -v`
- Baseline must stay green before and after every commit

---

## Task 1: Create the git worktree

**Files:**
- (no source changes — git ops only)

- [ ] **Step 1: Verify .worktrees is gitignored**

  ```bash
  git check-ignore -q .worktrees && echo "already ignored" || echo "NOT ignored"
  ```
  Expected: `already ignored`

- [ ] **Step 2: Create the worktree and branch**

  ```bash
  git worktree add .worktrees/feat/backlog-agent-codex -b feat/backlog-agent-codex
  ```
  Expected: `Preparing worktree (new branch 'feat/backlog-agent-codex')`

- [ ] **Step 3: Verify baseline tests pass in worktree**

  ```bash
  cd .worktrees/feat/backlog-agent-codex && uv run pytest tests/unit/ -q 2>&1 | tail -5
  ```
  Expected: all pass, 0 failures

---

## Task 2: Add CodexModel enum and ProviderName.codex to settings

**Files:**
- Modify: `src/settings/provider.py`

- [ ] **Step 1: Write failing tests first**

  Add to `tests/unit/settings/test_provider.py` (append to the file):

  ```python
  # ── CodexModel and ProviderName.codex ────────────────────────────────────────


  def test_codex_model_enum_values():
      from settings.provider import CodexModel

      assert CodexModel.codex_mini_latest == "codex-mini-latest"
      assert CodexModel.o4_mini == "o4-mini"


  def test_codex_provider_name_enum():
      assert ProviderName.codex == "codex"


  def test_codex_model_accepted():
      from pathlib import Path

      from settings.provider import CodexModel

      ps = ProviderSettings(
          name=ProviderName.codex,
          model=CodexModel.codex_mini_latest,
          auth=OAuth2CliAuth(token_path=Path.home() / ".codex" / "auth.json"),
      )
      assert ps.model == "codex-mini-latest"
      assert ps.is_codex() is True
      assert ps.is_claude() is False
      assert ps.is_openai() is False


  def test_codex_rejects_api_key_auth():
      from settings.provider import CodexModel

      with pytest.raises(ValidationError, match="codex requires oauth2_cli auth"):
          ProviderSettings(
              name=ProviderName.codex,
              model=CodexModel.o4_mini,
              auth=ApiKeyAuth(key="sk-test"),
          )


  def test_codex_invalid_model_raises():
      from pathlib import Path

      with pytest.raises(ValidationError, match="not valid for provider"):
          ProviderSettings(
              name=ProviderName.codex,
              model="gpt-4o",
              auth=OAuth2CliAuth(token_path=Path.home() / ".codex" / "auth.json"),
          )


  def test_is_codex_false_for_others():
      ps = ProviderSettings()  # defaults to claude
      assert ps.is_codex() is False
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```bash
  uv run pytest tests/unit/settings/test_provider.py -k "codex" -v 2>&1 | tail -20
  ```
  Expected: errors like `ImportError: cannot import name 'CodexModel'` or `AttributeError`

- [ ] **Step 3: Implement CodexModel and ProviderName.codex in settings**

  Edit `src/settings/provider.py`. Changes:

  3a. After `OpenAIModel`, add:
  ```python
  class CodexModel(StrEnum):
      codex_mini_latest = "codex-mini-latest"
      o4_mini = "o4-mini"
  ```

  3b. In `ProviderName`, add:
  ```python
  codex = "codex"
  ```
  (after `gemini = "gemini"`)

  3c. In `ProviderSettings.model_matches_provider`, extend the `valid` dict:
  ```python
  valid: dict[ProviderName, type[StrEnum]] = {
      ProviderName.claude: ClaudeModel,
      ProviderName.openai: OpenAIModel,
      ProviderName.codex: CodexModel,
      ProviderName.gemini: GeminiModel,
  }
  ```

  3d. In `ProviderSettings.validate_provider_config`, add before the ADC check:
  ```python
  if self.name == ProviderName.codex and self.auth.kind != "oauth2_cli":
      raise ValueError(
          f"codex requires oauth2_cli auth (got {self.auth.kind!r}). "
          "Run: codex login --device-auth"
      )
  ```

  3e. Add `is_codex()` helper after `is_gemini()`:
  ```python
  def is_codex(self) -> bool:
      return self.name == ProviderName.codex
  ```

- [ ] **Step 4: Run tests to confirm they pass**

  ```bash
  uv run pytest tests/unit/settings/test_provider.py -v 2>&1 | tail -15
  ```
  Expected: all pass

- [ ] **Step 5: Commit**

  ```bash
  git add src/settings/provider.py tests/unit/settings/test_provider.py
  git commit -m "feat(settings): add CodexModel enum and ProviderName.codex"
  ```

---

## Task 3: Export CodexModel from settings package

**Files:**
- Modify: `src/settings/__init__.py`

- [ ] **Step 1: Write failing test**

  Add to `tests/unit/settings/test_init_reexports.py` (or create if missing), after existing imports:

  ```python
  def test_codex_model_reexported():
      from settings import CodexModel  # noqa: F401 — import check
      assert CodexModel.codex_mini_latest == "codex-mini-latest"
  ```

  Run:
  ```bash
  uv run pytest tests/unit/settings/test_init_reexports.py -k "codex" -v 2>&1 | tail -10
  ```
  Expected: `ImportError: cannot import name 'CodexModel' from 'settings'`

- [ ] **Step 2: Add CodexModel to settings/__init__.py**

  In `src/settings/__init__.py`, in the `from settings.provider import (...)` block, add `CodexModel` to the import list and to `__all__`.

  After this change the relevant section reads:
  ```python
  from settings.provider import (
      ApiKeyAuth,
      AuthConfig,
      ClaudeConfig,
      CodexModel,
      GeminiConfig,
      OAuth2ADCAuth,
      OAuth2CliAuth,
      OpenAIConfig,
      ProviderSettings,
  )
  ```

  And in `__all__`:
  ```python
  "CodexModel",
  ```
  (add alphabetically between `"ClaudeConfig"` and `"GeminiConfig"`)

- [ ] **Step 3: Run tests**

  ```bash
  uv run pytest tests/unit/settings/test_init_reexports.py -v 2>&1 | tail -10
  ```
  Expected: all pass

- [ ] **Step 4: Commit**

  ```bash
  git add src/settings/__init__.py tests/unit/settings/test_init_reexports.py
  git commit -m "feat(settings): export CodexModel from settings package"
  ```

---

## Task 4: Wire ProviderName.codex in build_provider

**Files:**
- Modify: `src/backlog/agent.py`

**Background:** `ProviderRegistry` has "openai" and "claude" registered. `ProviderName.codex` is a settings-layer distinction — at the registry level, Codex IS the `OpenAIProvider` with OAuth2 auth (which auto-selects `_CodexBackend`). So `build_provider` must map "codex" → "openai" when calling the registry.

- [ ] **Step 1: Write failing test**

  Add to `tests/unit/backlog/test_agent.py` (append at end):

  ```python
  def test_build_provider_maps_codex_name_to_openai_registry(monkeypatch) -> None:
      """build_provider(codex settings) must call ProviderRegistry.build("openai", ...)."""
      from pathlib import Path

      from settings.provider import CodexModel, OAuth2CliAuth, ProviderName, ProviderSettings

      class TestProvider:
          def __init__(self, auth: OAuth2CliToken) -> None:
              self.auth = auth

      calls: list[tuple[str, object]] = []

      def fake_build(name: str, *, auth: object) -> TestProvider:
          calls.append((name, auth))
          return TestProvider(auth)  # type: ignore[arg-type]

      monkeypatch.setattr(ProviderRegistry, "build", fake_build)

      codex_settings = ProviderSettings(
          name=ProviderName.codex,
          model=CodexModel.codex_mini_latest,
          auth=OAuth2CliAuth(token_path=Path("/tmp/auth.json")),
      )

      build_provider(codex_settings)

      assert calls[0][0] == "openai", (
          "build_provider must pass 'openai' to ProviderRegistry for codex settings"
      )
      assert isinstance(calls[0][1], OAuth2CliToken)
  ```

- [ ] **Step 2: Run test to confirm it fails**

  ```bash
  uv run pytest tests/unit/backlog/test_agent.py::test_build_provider_maps_codex_name_to_openai_registry -v 2>&1 | tail -15
  ```
  Expected: `AssertionError: build_provider must pass 'openai' to ProviderRegistry for codex settings`
  (currently it passes `"codex"` which causes `ProviderNotFoundError`)

- [ ] **Step 3: Update build_provider in backlog/agent.py**

  In `src/backlog/agent.py`, locate `build_provider` and replace:

  ```python
  def build_provider(provider_settings: ProviderSettings | None = None) -> BaseProvider:
      """Build the configured LLM provider without reading env vars in this module."""

      provider_settings = provider_settings or settings.provider
      auth = _auth_from_settings(provider_settings)
      return ProviderRegistry.build(provider_settings.name.value, auth=auth)
  ```

  With:

  ```python
  def build_provider(provider_settings: ProviderSettings | None = None) -> BaseProvider:
      """Build the configured LLM provider without reading env vars in this module."""

      provider_settings = provider_settings or settings.provider
      auth = _auth_from_settings(provider_settings)
      # Codex is the OAuth2 backend of OpenAIProvider; map at the registry boundary.
      registry_name = (
          "openai" if provider_settings.name == ProviderName.codex
          else provider_settings.name.value
      )
      return ProviderRegistry.build(registry_name, auth=auth)
  ```

  Also add the import at the top of `backlog/agent.py` — `ProviderName` is already available from `settings` but needs to be named. Check: `from settings import ... ProviderName ...` or add it to the existing import:

  ```python
  from settings import (
      ApiKeyAuth,
      OAuth2ADCAuth,
      OAuth2CliAuth,
      ProviderName,
      ProviderSettings,
      settings,
  )
  ```

- [ ] **Step 4: Run the new test**

  ```bash
  uv run pytest tests/unit/backlog/test_agent.py::test_build_provider_maps_codex_name_to_openai_registry -v 2>&1 | tail -10
  ```
  Expected: PASS

- [ ] **Step 5: Run the full unit test suite to check no regressions**

  ```bash
  uv run pytest tests/unit/ -q 2>&1 | tail -10
  ```
  Expected: all pass

- [ ] **Step 6: Commit**

  ```bash
  git add src/backlog/agent.py tests/unit/backlog/test_agent.py
  git commit -m "feat(backlog): wire ProviderName.codex through build_provider to openai registry"
  ```

---

## Task 5: Add integration test for Codex

**Files:**
- Create: `tests/integration/backlog/test_backlog_agent_codex.py`

This mirrors `tests/integration/backlog/test_backlog_agent_claude.py` exactly but uses Codex settings. It is guard-skipped unless `HSB_RUN_CODEX_INTEGRATION=1` is set in the environment.

- [ ] **Step 1: Create the integration test file**

  Create `tests/integration/backlog/test_backlog_agent_codex.py`:

  ```python
  """Live Codex integration test for the provider-agnostic backlog agent.

  Requires:
    - `codex login --device-auth` completed (creates ~/.codex/auth.json)
    - ~/.codex/config.toml with `forced_login_method = "chatgpt"`
    - LINEAR_API_KEY, LINEAR_TEAM_ID, LINEAR_PROJECT_ID set

  Run with:
      HSB_RUN_CODEX_INTEGRATION=1 \\
          uv run pytest tests/integration/backlog/test_backlog_agent_codex.py -q
  """

  from __future__ import annotations

  import asyncio
  import json
  import os
  from pathlib import Path

  import pytest

  from backlog.agent import BacklogAgent
  from backlog.contracts import BacklogInput, IssueType
  from backlog.platforms import LinearPlatform
  from settings import settings
  from settings.provider import (
      CodexModel,
      OAuth2CliAuth,
      ProviderName,
      ProviderSettings,
  )

  pytestmark = [pytest.mark.integration]

  REAL_WORLD_PLAN = (
      Path(__file__).parent / "planning-poker-prd.md"
  ).read_text(encoding="utf-8")


  def _codex_provider_settings() -> ProviderSettings:
      codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
      return ProviderSettings(
          name=ProviderName.codex,
          model=CodexModel.codex_mini_latest,
          auth=OAuth2CliAuth(token_path=codex_home / "auth.json"),
      )


  def test_codex_generates_realistic_backlog_for_product_plan(capsys) -> None:
      if not os.environ.get("HSB_RUN_CODEX_INTEGRATION"):
          pytest.skip("HSB_RUN_CODEX_INTEGRATION env var must be set to run this test")

      auth_path = Path(
          os.environ.get("CODEX_HOME", Path.home() / ".codex")
      ) / "auth.json"
      if not auth_path.exists():
          pytest.skip(f"Codex not authenticated: {auth_path} missing. Run: codex login --device-auth")

      linear_settings = settings.linear
      if linear_settings.api_key is None:
          pytest.skip("LINEAR_API_KEY is not configured in settings.linear")
      if linear_settings.team_id is None:
          pytest.skip("LINEAR_TEAM_ID is not configured in settings.linear")
      if linear_settings.project_id is None:
          pytest.skip("LINEAR_PROJECT_ID is not configured in settings.linear")

      platform = LinearPlatform(
          team_id=linear_settings.team_id,
          project_id=linear_settings.project_id,
      )
      try:
          asyncio.run(
              platform.validate_target(
                  api_key=linear_settings.api_key.get_secret_value(),
              )
          )
      except ValueError as exc:
          pytest.skip(str(exc))

      input_contract = BacklogInput(
          plan_content=REAL_WORLD_PLAN,
          stacks=["nextjs", "react", "typescript", "golang", "postgres", "redis"],
          platform=platform,
          context={
              "repository": "https://github.com/hugo-hsbtech/hsb-test-fixture",
              "environment": "integration-test",
          },
      )

      agent = BacklogAgent(provider_settings=_codex_provider_settings())
      output, results = agent.run_and_create_sync(input_contract)

      with capsys.disabled():
          print("\nBacklogOutput (Codex):")
          print(json.dumps(output.model_dump(mode="json"), indent=2))
          print("\nLinear write results:")
          print(
              json.dumps(
                  [r.model_dump(mode="json") for r in results],
                  indent=2,
              )
          )

      assert output.is_linear()
      assert output.issues
      assert {issue.issue_type for issue in output.issues} & {
          IssueType.epic,
          IssueType.user_story,
          IssueType.task,
      }

      for issue in output.issues:
          assert issue.fields.title.strip()
          assert issue.fields.description.strip()
          assert issue.fields.platform_fields["team_id"] == linear_settings.team_id
          assert issue.fields.platform_fields["project_id"] == linear_settings.project_id

      assert len(results) == len(output.issues)
      assert {result["action"] for result in results} <= {"create", "reuse", "update"}
      assert any(result["action"] in {"create", "reuse"} for result in results)
  ```

- [ ] **Step 2: Run the test file in dry-run (no integration env set)**

  ```bash
  uv run pytest tests/integration/backlog/test_backlog_agent_codex.py -v 2>&1 | tail -10
  ```
  Expected: `SKIPPED` (because `HSB_RUN_CODEX_INTEGRATION` is not set)

- [ ] **Step 3: Run the full unit suite to verify no regressions**

  ```bash
  uv run pytest tests/unit/ -q 2>&1 | tail -5
  ```
  Expected: all pass

- [ ] **Step 4: Commit**

  ```bash
  git add tests/integration/backlog/test_backlog_agent_codex.py
  git commit -m "test(backlog): add Codex integration test mirroring Claude test"
  ```

---

## Task 6: Final verification

- [ ] **Step 1: Run full unit suite one more time**

  ```bash
  uv run pytest tests/unit/ -q 2>&1 | tail -5
  ```
  Expected: all pass, 0 failures

- [ ] **Step 2: Run llm_providers tests**

  ```bash
  uv run pytest tests/llm_providers/ -q 2>&1 | tail -5
  ```
  Expected: all pass, 0 failures

- [ ] **Step 3: Verify Codex can be constructed end-to-end (smoke)**

  ```bash
  uv run python -c "
  from pathlib import Path
  from settings.provider import CodexModel, OAuth2CliAuth, ProviderName, ProviderSettings
  from backlog.agent import build_provider
  from llm_providers.auth.oauth2_cli import OAuth2CliToken

  ps = ProviderSettings(
      name=ProviderName.codex,
      model=CodexModel.codex_mini_latest,
      auth=OAuth2CliAuth(token_path=Path('/tmp/fake-auth.json')),
  )
  print('ProviderSettings OK:', ps.name, ps.model)
  print('is_codex:', ps.is_codex())
  " 2>&1
  ```
  Expected output (no crash):
  ```
  ProviderSettings OK: codex codex-mini-latest
  is_codex: True
  ```

- [ ] **Step 4: Final commit summary / tag (optional)**

  No extra commit needed if all prior commits are in order.
