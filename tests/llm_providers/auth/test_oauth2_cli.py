"""OAuth2CliToken strategy: env-var OR file-based detection."""

import json

import pytest

from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.errors import AuthDetectionFailed


def test_kind_classvar():
    assert OAuth2CliToken.kind == "oauth2_cli_token"


def test_detect_env_var_present(monkeypatch):
    monkeypatch.setenv("MY_OAUTH", "tok-abc")
    s = OAuth2CliToken(env_var="MY_OAUTH")
    assert s.detect() is True


def test_detect_env_var_empty(monkeypatch):
    monkeypatch.setenv("MY_OAUTH", "")
    s = OAuth2CliToken(env_var="MY_OAUTH")
    assert s.detect() is False


def test_detect_token_file_present(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_OAUTH", raising=False)
    f = tmp_path / "token.json"
    f.write_text(json.dumps({"access_token": "tok-xyz"}))
    s = OAuth2CliToken(token_path=f)
    assert s.detect() is True


def test_detect_token_file_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_OAUTH", raising=False)
    s = OAuth2CliToken(token_path=tmp_path / "missing.json")
    assert s.detect() is False


def test_resolve_env_var_returns_token(monkeypatch):
    monkeypatch.setenv("MY_OAUTH", "tok-abc")
    s = OAuth2CliToken(env_var="MY_OAUTH")
    cred = s.resolve()
    assert cred.kind == "oauth2_cli_token"
    assert cred.payload["token"] == "tok-abc"
    assert cred.payload["source"] == "env:MY_OAUTH"


def test_resolve_file_returns_token(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_OAUTH", raising=False)
    f = tmp_path / "token.json"
    f.write_text(json.dumps({"access_token": "tok-xyz"}))
    s = OAuth2CliToken(token_path=f)
    cred = s.resolve()
    assert cred.payload["token"] == "tok-xyz"
    assert cred.payload["source"] == f"file:{f}"


def test_resolve_file_plain_text(tmp_path, monkeypatch):
    """If the file is not JSON, treat its contents as the raw token."""
    monkeypatch.delenv("MY_OAUTH", raising=False)
    f = tmp_path / "token.txt"
    f.write_text("raw-token-string\n")
    s = OAuth2CliToken(token_path=f)
    cred = s.resolve()
    assert cred.payload["token"] == "raw-token-string"


def test_resolve_raises_when_nothing_available(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_OAUTH", raising=False)
    s = OAuth2CliToken(env_var="MY_OAUTH", token_path=tmp_path / "missing.json")
    with pytest.raises(AuthDetectionFailed):
        s.resolve()


def test_default_constructs_without_args():
    # Base OAuth2CliToken.default() has no env_var / token_path wired up;
    # subclasses (e.g. _ClaudeOAuth2CliToken) override default() to point at
    # a concrete source. So the base default must not advertise itself as
    # detectable — otherwise auto_resolve_auth would short-circuit on it
    # and then fail in resolve().
    s = OAuth2CliToken.default()
    assert isinstance(s, OAuth2CliToken)
    assert s.detect() is False


def test_from_settings_creates_token(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    monkeypatch.setenv("OAUTH_ENV", "tok-from-env")
    mock_auth = MagicMock()
    mock_auth.env_var = "OAUTH_ENV"
    mock_auth.token_path = None

    s = OAuth2CliToken.from_settings(mock_auth)
    assert s.detect() is True
    cred = s.resolve()
    assert cred.payload["token"] == "tok-from-env"


def test_extract_token_returns_raw_when_json_has_no_token_keys(tmp_path, monkeypatch):
    """If JSON object has no access_token or token keys, return raw JSON."""
    monkeypatch.delenv("MY_OAUTH", raising=False)
    f = tmp_path / "weird.json"
    f.write_text(json.dumps({"some_field": "value"}))
    s = OAuth2CliToken(token_path=f)
    cred = s.resolve()
    assert cred.payload["token"] == '{"some_field": "value"}'
