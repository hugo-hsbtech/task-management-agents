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
