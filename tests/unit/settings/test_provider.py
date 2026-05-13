"""Tests for settings.provider — ProviderSettings validators and helpers."""

import pytest
from pydantic import ValidationError

from settings.provider import (
    ApiKeyAuth,
    ClaudeConfig,
    GeminiConfig,
    OAuth2ADCAuth,
    OAuth2CliAuth,
    OpenAIConfig,
    ProviderName,
    ProviderSettings,
)

# ── OAuth2CliAuth.at_least_one_source ─────────────────────────────────────────


def test_oauth2_cli_auth_requires_env_var_or_token_path():
    with pytest.raises(ValidationError, match="must provide env_var or token_path"):
        OAuth2CliAuth()


def test_oauth2_cli_auth_valid_with_env_var():
    auth = OAuth2CliAuth(env_var="CLAUDE_CODE_OAUTH_TOKEN")
    assert auth.env_var == "CLAUDE_CODE_OAUTH_TOKEN"
    assert auth.token_path is None


def test_oauth2_cli_auth_valid_with_token_path(tmp_path):
    auth = OAuth2CliAuth(token_path=tmp_path / "token")
    assert auth.token_path == tmp_path / "token"
    assert auth.env_var is None


# ── ProviderSettings.model_matches_provider ───────────────────────────────────


def test_provider_default_is_claude_haiku():
    ps = ProviderSettings()
    assert ps.name == ProviderName.claude
    assert ps.model == "claude-haiku-4-5"


def test_model_mismatch_raises():
    with pytest.raises(ValidationError, match="not valid for provider"):
        ProviderSettings(name=ProviderName.claude, model="gpt-4o")


def test_openai_model_accepted():
    ps = ProviderSettings(
        name=ProviderName.openai,
        model="gpt-4o",
        auth=ApiKeyAuth(key="sk-test"),
    )
    assert ps.model == "gpt-4o"


def test_gemini_model_accepted():
    ps = ProviderSettings(
        name=ProviderName.gemini,
        model="gemini-2.5-pro",
        auth=OAuth2ADCAuth(),
        gemini=GeminiConfig(project_id="my-project"),
    )
    assert ps.model == "gemini-2.5-pro"


def test_invalid_model_for_openai_raises():
    with pytest.raises(ValidationError, match="not valid for provider"):
        ProviderSettings(
            name=ProviderName.openai,
            model="claude-haiku-4-5",
            auth=ApiKeyAuth(key="sk-test"),
        )


# ── ProviderSettings.validate_provider_config ────────────────────────────────


def test_gemini_config_on_non_gemini_raises():
    with pytest.raises(
        ValidationError, match="gemini config only valid when name='gemini'"
    ):
        ProviderSettings(
            name=ProviderName.claude,
            model="claude-haiku-4-5",
            auth=OAuth2CliAuth(env_var="CLAUDE_CODE_OAUTH_TOKEN"),
            gemini=GeminiConfig(project_id="x"),
        )


def test_claude_config_on_non_claude_raises():
    with pytest.raises(
        ValidationError, match="claude config only valid when name='claude'"
    ):
        ProviderSettings(
            name=ProviderName.openai,
            model="gpt-4o",
            auth=ApiKeyAuth(key="sk-test"),
            claude=ClaudeConfig(),
        )


def test_openai_config_on_non_openai_raises():
    with pytest.raises(
        ValidationError, match="openai config only valid when name='openai'"
    ):
        ProviderSettings(
            name=ProviderName.claude,
            model="claude-haiku-4-5",
            auth=OAuth2CliAuth(env_var="CLAUDE_CODE_OAUTH_TOKEN"),
            openai=OpenAIConfig(organization="org-x"),
        )


def test_adc_auth_on_non_gemini_raises():
    with pytest.raises(ValidationError, match="oauth2_adc only valid for gemini"):
        ProviderSettings(
            name=ProviderName.claude,
            model="claude-haiku-4-5",
            auth=OAuth2ADCAuth(),
        )


def test_adc_auth_without_project_id_raises():
    with pytest.raises(ValidationError, match="oauth2_adc requires gemini.project_id"):
        ProviderSettings(
            name=ProviderName.gemini,
            model="gemini-2.5-pro",
            auth=OAuth2ADCAuth(),
            gemini=GeminiConfig(),
        )


def test_adc_auth_without_gemini_config_raises():
    with pytest.raises(ValidationError, match="oauth2_adc requires gemini.project_id"):
        ProviderSettings(
            name=ProviderName.gemini,
            model="gemini-2.5-pro",
            auth=OAuth2ADCAuth(),
        )


# ── is_* helpers ──────────────────────────────────────────────────────────────


def test_is_claude_true():
    ps = ProviderSettings()
    assert ps.is_claude() is True
    assert ps.is_openai() is False
    assert ps.is_gemini() is False


def test_is_openai_true():
    ps = ProviderSettings(
        name=ProviderName.openai,
        model="gpt-4o",
        auth=ApiKeyAuth(key="sk-test"),
    )
    assert ps.is_openai() is True
    assert ps.is_claude() is False
    assert ps.is_gemini() is False


def test_is_gemini_true():
    ps = ProviderSettings(
        name=ProviderName.gemini,
        model="gemini-2.5-pro",
        auth=OAuth2ADCAuth(),
        gemini=GeminiConfig(project_id="proj"),
    )
    assert ps.is_gemini() is True
    assert ps.is_claude() is False
    assert ps.is_openai() is False


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
