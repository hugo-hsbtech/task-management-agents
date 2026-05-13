"""resolve_auth — strict (provider, auth_kind) → AuthStrategy with resolved value.

Exercises the full matrix:
  - claude  + oauth2_cli_token → CLAUDE_CODE_OAUTH_TOKEN
  - claude  + api_key          → ANTHROPIC_API_KEY
  - openai  + oauth2_cli_token → <codex_home>/auth.json
  - openai  + api_key          → OPENAI_API_KEY
  - gemini  + api_key          → GEMINI_API_KEY
  - gemini  + oauth2_adc       → OAuth2ADC()
Plus the failure modes (missing source, unsupported combo).
"""

from __future__ import annotations

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.factory import AuthResolutionError, resolve_auth
from llm_providers.auth.oauth2_cli import OAuth2CliToken

# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------


def test_claude_oauth2_reads_env_var(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "claude-tok")
    strat = resolve_auth("claude", "oauth2_cli_token")
    assert isinstance(strat, OAuth2CliToken)
    assert strat.resolve().payload["token"] == "claude-tok"


def test_claude_oauth2_missing_raises(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    with pytest.raises(AuthResolutionError, match="CLAUDE_CODE_OAUTH_TOKEN"):
        resolve_auth("claude", "oauth2_cli_token")


def test_claude_api_key_reads_env_var(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")
    strat = resolve_auth("claude", "api_key")
    assert isinstance(strat, ApiKey)
    assert strat.resolve().payload["api_key"] == "sk-anthropic"


def test_claude_api_key_missing_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(AuthResolutionError, match="ANTHROPIC_API_KEY"):
        resolve_auth("claude", "api_key")


# ---------------------------------------------------------------------------
# OpenAI / Codex
# ---------------------------------------------------------------------------


def test_openai_oauth2_reads_codex_auth_file(monkeypatch, tmp_path):
    auth_file = tmp_path / "auth.json"
    auth_file.write_text('{"access_token": "codex-tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    strat = resolve_auth("openai", "oauth2_cli_token")
    assert isinstance(strat, OAuth2CliToken)
    assert strat.resolve().payload["token"] == "codex-tok"


def test_openai_oauth2_accepts_token_key_fallback(monkeypatch, tmp_path):
    """Older Codex CLI writes the bearer under "token", not "access_token"."""
    auth_file = tmp_path / "auth.json"
    auth_file.write_text('{"token": "legacy-tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    strat = resolve_auth("openai", "oauth2_cli_token")
    assert strat.resolve().payload["token"] == "legacy-tok"


def test_openai_oauth2_accepts_raw_text_fallback(monkeypatch, tmp_path):
    """If auth.json isn't JSON we treat the contents as the token literal."""
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("raw-token-string")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    strat = resolve_auth("openai", "oauth2_cli_token")
    assert strat.resolve().payload["token"] == "raw-token-string"


def test_openai_oauth2_missing_file_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    with pytest.raises(AuthResolutionError, match="auth.json"):
        resolve_auth("openai", "oauth2_cli_token")


def test_openai_api_key_reads_env_var(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    strat = resolve_auth("openai", "api_key")
    assert isinstance(strat, ApiKey)
    assert strat.resolve().payload["api_key"] == "sk-openai"


def test_openai_api_key_missing_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AuthResolutionError, match="OPENAI_API_KEY"):
        resolve_auth("openai", "api_key")


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


def test_gemini_api_key_reads_env_var(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-test")
    strat = resolve_auth("gemini", "api_key")
    assert isinstance(strat, ApiKey)
    assert strat.resolve().payload["api_key"] == "AIzaSy-test"


def test_gemini_api_key_missing_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(AuthResolutionError, match="GEMINI_API_KEY"):
        resolve_auth("gemini", "api_key")


def test_gemini_oauth2_adc_returns_strategy():
    from llm_providers.auth.oauth2_adc import OAuth2ADC

    strat = resolve_auth("gemini", "oauth2_adc")
    assert isinstance(strat, OAuth2ADC)
    cred = strat.resolve()
    assert cred.kind == "oauth2_adc"


# ---------------------------------------------------------------------------
# Negative paths
# ---------------------------------------------------------------------------


def test_unsupported_combo_raises():
    with pytest.raises(AuthResolutionError, match="Unsupported"):
        resolve_auth("gemini", "oauth2_cli_token")


def test_unsupported_kind_for_known_provider_raises():
    with pytest.raises(AuthResolutionError, match="Unsupported"):
        resolve_auth("claude", "oauth2_adc")


def test_extract_codex_token_handles_dict_without_known_keys(monkeypatch, tmp_path):
    """Dict with no recognised key falls through to the raw-text branch."""
    auth_file = tmp_path / "auth.json"
    auth_file.write_text('{"other_field": "x"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    strat = resolve_auth("openai", "oauth2_cli_token")
    # Raw string contains the JSON literal — confirms we hit the fallback.
    assert "other_field" in strat.resolve().payload["token"]
