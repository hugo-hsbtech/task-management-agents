"""hsb.runtime.resolver — HSB_RUNTIME_<AGENT> routing + hard-blocks + alias."""

import pytest

from hsb.runtime.handle import HsbProviderHandle
from hsb.runtime.resolver import resolve_runtime


def test_default_routes_to_claude(monkeypatch):
    monkeypatch.delenv("HSB_RUNTIME_BACKLOG", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
    h = resolve_runtime("backlog")
    assert isinstance(h, HsbProviderHandle)
    assert h.provider.name == "claude"


def test_env_var_routes_to_openai_with_codex_oauth(monkeypatch, tmp_path):
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "openai")
    (tmp_path / "config.toml").write_text('forced_login_method = "chatgpt"')
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    h = resolve_runtime("backlog")
    assert h.provider.name == "openai"


def test_codex_alias_for_openai_emits_warning(monkeypatch, tmp_path):
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "codex")
    (tmp_path / "config.toml").write_text('forced_login_method = "chatgpt"')
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    with pytest.warns(DeprecationWarning, match="codex.*openai"):
        h = resolve_runtime("backlog")
    assert h.provider.name == "openai"


def test_invalid_value_raises(monkeypatch):
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "nope")
    with pytest.raises(ValueError, match="not registered"):
        resolve_runtime("backlog")


def test_wio_blocked_from_openai(monkeypatch):
    monkeypatch.setenv("HSB_RUNTIME_WIO", "openai")
    with pytest.raises(ValueError, match="hard-blocked"):
        resolve_runtime("wio")


def test_wio_blocked_from_gemini(monkeypatch):
    """Phase A doesn't ship Gemini, but the hard-block list includes it.

    The block check fires before the registry lookup, so this raises
    ValueError(hard-blocked) rather than ProviderNotFoundError."""
    monkeypatch.setenv("HSB_RUNTIME_WIO", "gemini")
    with pytest.raises(ValueError, match="hard-blocked"):
        resolve_runtime("wio")


def test_wio_default_to_claude_works(monkeypatch):
    monkeypatch.delenv("HSB_RUNTIME_WIO", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
    h = resolve_runtime("wio")
    assert h.provider.name == "claude"
