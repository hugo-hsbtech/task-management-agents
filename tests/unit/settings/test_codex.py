"""Tests for hsb.settings.codex.CodexSettings."""

from pathlib import Path


def test_home_default_is_container_root_codex(monkeypatch):
    """Project deploys via Docker as root user; `/root/.codex` is where
    `codex login` writes inside the container image. Host developers
    override via env var."""
    monkeypatch.delenv("CODEX_HOME", raising=False)
    from hsb.settings.codex import CodexSettings

    settings = CodexSettings()
    assert settings.home == Path("/root/.codex")
    assert isinstance(settings.home, Path)


def test_home_reads_env_as_path(monkeypatch):
    monkeypatch.setenv("CODEX_HOME", "/home/dev/.codex")
    from hsb.settings.codex import CodexSettings

    settings = CodexSettings()
    assert settings.home == Path("/home/dev/.codex")
    assert isinstance(settings.home, Path)


def test_path_override_default_is_none(monkeypatch):
    monkeypatch.delenv("CODEX_PATH_OVERRIDE", raising=False)
    from hsb.settings.codex import CodexSettings

    assert CodexSettings().path_override is None


def test_path_override_reads_env_as_path(monkeypatch):
    monkeypatch.setenv("CODEX_PATH_OVERRIDE", "/usr/local/bin/codex")
    from hsb.settings.codex import CodexSettings

    assert CodexSettings().path_override == Path("/usr/local/bin/codex")
