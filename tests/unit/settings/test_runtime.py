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
