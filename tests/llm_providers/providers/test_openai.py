"""OpenAIProvider — dual-backend routing (Codex CLI vs raw OpenAI)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.registry import ProviderRegistry


@pytest.fixture(autouse=True)
def _isolate_openai_registration():
    """Each test re-imports llm_providers.providers.openai under a fresh
    stubbed SDK. patch.dict("sys.modules", ...) evicts the re-imported
    module on exit, so the decorator re-runs the next time — which would
    collide with the prior registration. Pop the entry around each test
    so re-registration is clean."""
    import sys

    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)
    yield
    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)


def _stub_codex_sdk():
    return SimpleNamespace(
        Codex=MagicMock(),
        TextInput=MagicMock(),
        ThreadOptions=MagicMock(),
        TurnOptions=MagicMock(),
        TurnCompletedEvent=type("TurnCompletedEvent", (), {}),
        TurnFailedEvent=type("TurnFailedEvent", (), {}),
        types=SimpleNamespace(CodexOptions=MagicMock()),
    )


def _stub_openai_sdk():
    return SimpleNamespace(OpenAI=MagicMock())


def test_codex_backend_selected_for_oauth_token(monkeypatch, tmp_path):
    # Set up a valid Codex config so the backend init guard passes.
    (tmp_path / "config.toml").write_text('forced_login_method = "chatgpt"')
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))

    sdks = {
        "openai_codex_sdk": _stub_codex_sdk(),
        "openai_codex_sdk.types": _stub_codex_sdk().types,
    }
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider, _CodexBackend

        p = OpenAIProvider(auth=OAuth2CliToken(token_path=tmp_path / "auth.json"))
        assert isinstance(p._backend, _CodexBackend)


def test_raw_openai_backend_selected_for_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abc")
    sdks = {"openai": _stub_openai_sdk()}
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider, _RawOpenAIBackend

        p = OpenAIProvider(auth=ApiKey(env_var="OPENAI_API_KEY"))
        assert isinstance(p._backend, _RawOpenAIBackend)


def test_capabilities_differ_by_backend(monkeypatch, tmp_path):
    """supports_mcp is True only on the Codex backend."""
    (tmp_path / "config.toml").write_text('forced_login_method = "chatgpt"')
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk")

    sdks_codex = {
        "openai_codex_sdk": _stub_codex_sdk(),
        "openai_codex_sdk.types": _stub_codex_sdk().types,
    }
    sdks_raw = {"openai": _stub_openai_sdk()}

    with patch.dict("sys.modules", sdks_codex):
        from llm_providers.providers.openai import OpenAIProvider

        p_codex = OpenAIProvider(auth=OAuth2CliToken(token_path=tmp_path / "auth.json"))
        assert p_codex.capabilities.supports_mcp is True

    # Reset registration so the second import re-runs the decorator cleanly.
    import sys

    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)

    with patch.dict("sys.modules", sdks_raw):
        from llm_providers.providers.openai import OpenAIProvider

        p_raw = OpenAIProvider(auth=ApiKey(env_var="OPENAI_API_KEY"))
        assert p_raw.capabilities.supports_mcp is False


def test_supported_auth():
    sdks = {"openai": _stub_openai_sdk()}
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider

        assert OAuth2CliToken in OpenAIProvider.supported_auth
        assert ApiKey in OpenAIProvider.supported_auth


def test_codex_backend_init_calls_oauth_guard(monkeypatch, tmp_path):
    """The Codex backend must verify ~/.codex/config.toml at init."""
    # auth.json exists so OAuth2CliToken.resolve() succeeds, but no config.toml
    # → the Codex backend's init-time guard should raise.
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    sdks = {
        "openai_codex_sdk": _stub_codex_sdk(),
        "openai_codex_sdk.types": _stub_codex_sdk().types,
    }
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider

        with pytest.raises(RuntimeError, match="config.toml not found"):
            OpenAIProvider(auth=OAuth2CliToken(token_path=tmp_path / "auth.json"))
