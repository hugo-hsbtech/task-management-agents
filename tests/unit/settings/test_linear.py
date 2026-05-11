"""Tests for hsb.settings.linear.LinearSettings."""

from pydantic import SecretStr


def test_api_key_default_is_none(monkeypatch):
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    from hsb.settings.linear import LinearSettings

    assert LinearSettings().api_key is None


def test_api_key_reads_env_as_secretstr(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test_token")
    from hsb.settings.linear import LinearSettings

    settings = LinearSettings()
    assert isinstance(settings.api_key, SecretStr)
    assert settings.api_key.get_secret_value() == "lin_api_test_token"


def test_api_key_does_not_leak_in_repr(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test_token")
    from hsb.settings.linear import LinearSettings

    settings = LinearSettings()
    assert "lin_api_test_token" not in repr(settings)
    assert "lin_api_test_token" not in str(settings)
