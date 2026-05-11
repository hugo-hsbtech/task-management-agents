"""Tests for hsb.settings.github.GitHubSettings."""

from pydantic import SecretStr


def test_token_default_is_none(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    from hsb.settings.github import GitHubSettings

    assert GitHubSettings().token is None


def test_token_reads_env_as_secretstr(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    from hsb.settings.github import GitHubSettings

    settings = GitHubSettings()
    assert isinstance(settings.token, SecretStr)
    assert settings.token.get_secret_value() == "ghp_test_token_value"


def test_token_does_not_leak_in_repr(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    from hsb.settings.github import GitHubSettings

    settings = GitHubSettings()
    assert "ghp_test_token_value" not in repr(settings)
