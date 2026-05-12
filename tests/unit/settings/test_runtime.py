"""Tests for hsb.settings.runtime.RuntimeSettings."""

import pytest
from pydantic import SecretStr, ValidationError

_AGENT_RUNTIME_VARS = (
    "HSB_RUNTIME_BACKLOG",
    "HSB_RUNTIME_WORK_ITEM_ORCHESTRATOR",
    "HSB_RUNTIME_QUALITY_ASSURANCE",
    "HSB_RUNTIME_USER_ACCEPTANCE_TESTING",
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
    from settings import RuntimeSettings

    s = RuntimeSettings()
    assert s.backlog == "claude"
    assert s.work_item_orchestrator == "claude"
    assert s.quality_assurance == "claude"
    assert s.user_acceptance_testing == "claude"
    assert s.risk == "claude"
    assert s.git == "claude"
    assert s.builder == "claude"
    assert s.intelligence == "claude"
    assert s.linear == "claude"


def test_agent_runtime_enum_values():
    from settings import AgentRuntime

    assert AgentRuntime.CLAUDE.value == "claude"
    assert AgentRuntime.CODEX.value == "codex"
    # str-inheritance: enum members compare equal to their str values.
    assert AgentRuntime.CLAUDE == "claude"
    assert AgentRuntime.CODEX == "codex"


def test_backlog_can_be_codex(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "codex")
    from settings import AgentRuntime, RuntimeSettings

    s = RuntimeSettings()
    assert s.backlog == AgentRuntime.CODEX
    assert s.backlog == "codex"


def test_runtime_value_is_normalized_lower_stripped(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "  CODEX  ")
    from settings import RuntimeSettings

    assert RuntimeSettings().backlog == "codex"


def test_work_item_orchestrator_cannot_be_codex(monkeypatch):
    """HSB_RUNTIME_WORK_ITEM_ORCHESTRATOR=codex must surface the
    project-specific explanation about the missing stateful-client Codex
    equivalent — not pydantic's generic enum_error. The model_validator
    owns this message; narrowing the field type to a single-value enum
    would let pydantic intercept at field validation, hiding the
    explanation."""
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HSB_RUNTIME_WORK_ITEM_ORCHESTRATOR", "codex")
    from settings import RuntimeSettings

    with pytest.raises(ValidationError) as exc:
        RuntimeSettings()
    assert "Work Item Orchestrator is not flippable yet" in str(exc.value)
    assert "stateful" in str(exc.value)
    assert "ClaudeSDKClient" in str(exc.value)


def test_invalid_runtime_value_raises(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "gemini")
    from settings import RuntimeSettings

    with pytest.raises(ValidationError):
        RuntimeSettings()


def test_oauth_token_default_is_none(monkeypatch):
    _clear_runtime_env(monkeypatch)
    from settings import RuntimeSettings

    assert RuntimeSettings().claude_code_oauth_token is None


def test_oauth_token_reads_alias(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-claude-oauth-test")
    from settings import RuntimeSettings

    s = RuntimeSettings()
    assert isinstance(s.claude_code_oauth_token, SecretStr)
    assert s.claude_code_oauth_token.get_secret_value() == "sk-claude-oauth-test"


def test_oauth_token_does_not_leak_in_repr(monkeypatch):
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-claude-oauth-test")
    from settings import RuntimeSettings

    assert "sk-claude-oauth-test" not in repr(RuntimeSettings())


# --- G1 parity tests (relocated from _sdk_options.py) ---


def test_forbidden_vars_constant():
    from settings import FORBIDDEN_API_KEY_VARS

    assert FORBIDDEN_API_KEY_VARS == ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def test_assert_oauth2_only_noop_when_clear(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from settings import assert_oauth2_only

    # Should not raise.
    assert_oauth2_only()


def test_assert_oauth2_only_raises_on_anthropic(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "leaked")
    from settings import assert_oauth2_only

    with pytest.raises(RuntimeError) as exc:
        assert_oauth2_only()
    assert "G1 violation" in str(exc.value)
    assert "ANTHROPIC_API_KEY" in str(exc.value)


def test_assert_oauth2_only_raises_on_openai(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "leaked")
    from settings import assert_oauth2_only

    with pytest.raises(RuntimeError) as exc:
        assert_oauth2_only()
    assert "OPENAI_API_KEY" in str(exc.value)


def test_assert_oauth2_only_reexported_from_sdk_options(monkeypatch):
    """_sdk_options re-exports the relocated helper — same callable object."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from hsb.agents._sdk_options import assert_oauth2_only as via_sdk_options
    from settings import assert_oauth2_only as via_settings

    assert via_sdk_options is via_settings


def test_assert_oauth2_only_with_agent_name_api_key_allowed(monkeypatch):
    """When HSB_AUTH_ALLOW_API_KEY_<AGENT>=1, assert_oauth2_only skips _G1Guard."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "leaked")
    monkeypatch.setenv("HSB_AUTH_ALLOW_API_KEY_MYAGENT", "1")
    from settings import assert_oauth2_only

    assert_oauth2_only(agent_name="myagent")


def test_assert_oauth2_only_with_agent_name_not_allowed_raises(monkeypatch):
    """When api_key is NOT in allowed_auth_kinds, _G1Guard still fires."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HSB_AUTH_ALLOW_API_KEY_OTHERAGENT", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "leaked")
    from settings import assert_oauth2_only

    with pytest.raises(RuntimeError, match="G1 violation"):
        assert_oauth2_only(agent_name="otheragent")


def test_normalize_runtime_passes_through_non_str(monkeypatch):
    """_normalize_runtime returns non-str values unchanged for non-str input."""
    _clear_runtime_env(monkeypatch)
    from settings.runtime import RuntimeSettings

    result = RuntimeSettings._normalize_runtime(42)
    assert result == 42
