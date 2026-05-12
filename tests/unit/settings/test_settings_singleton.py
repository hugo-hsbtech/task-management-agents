"""Tests for the top-level `settings` singleton in `hsb.settings`.

The singleton exposes each per-domain Settings class as a property that
freshly constructs the instance on every access, so monkeypatched env
values are picked up without needing to reload the module."""

from pathlib import Path

from pydantic import SecretStr


def test_orchestrator_attribute_reads_live_env(monkeypatch):
    monkeypatch.delenv("HSB_CLAIM_DELAY_MS", raising=False)
    from settings import settings

    assert settings.orchestrator.claim_delay_ms == 200

    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "999")
    # Re-accessing the property yields a fresh instance — no reload needed.
    assert settings.orchestrator.claim_delay_ms == 999


def test_codex_attribute(monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CODEX_PATH_OVERRIDE", raising=False)
    from settings import settings

    # Docker-container default — see CodexSettings.
    assert settings.codex.home == Path("/root/.codex")
    assert settings.codex.path_override is None


def test_linear_attribute(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "lin_singleton_test")
    from settings import settings

    assert isinstance(settings.linear.api_key, SecretStr)
    assert settings.linear.api_key.get_secret_value() == "lin_singleton_test"


def test_github_attribute(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_singleton_test")
    from settings import settings

    assert isinstance(settings.github.token, SecretStr)
    assert settings.github.token.get_secret_value() == "ghp_singleton_test"


def test_runtime_attribute(monkeypatch):
    monkeypatch.delenv("HSB_RUNTIME_BACKLOG", raising=False)
    monkeypatch.delenv("HSB_RUNTIME_WORK_ITEM_ORCHESTRATOR", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    from settings import settings

    assert settings.runtime.backlog == "claude"
    assert settings.runtime.work_item_orchestrator == "claude"
    assert settings.runtime.claude_code_oauth_token is None


def test_test_fixture_attribute(monkeypatch):
    monkeypatch.delenv("HSB_TEST_FIXTURE_URL", raising=False)
    monkeypatch.delenv("HSB_LIVE_CODEX", raising=False)
    from settings import settings

    assert settings.test_fixture.fixture_url is None
    assert settings.test_fixture.live_codex is False


def test_wio_ipc_attribute(monkeypatch):
    monkeypatch.delenv("HSB_WIO_INPUT_FILE", raising=False)
    monkeypatch.delenv("HSB_WIO_OUTPUT_FILE", raising=False)
    from settings import settings

    assert settings.wio_ipc.input_file is None
    assert settings.wio_ipc.output_file is None


def test_singleton_is_lazy_per_access(monkeypatch):
    """Each attribute access returns a fresh instance — proves env reads
    happen at the moment of access, not at module import."""
    from settings import settings

    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "111")
    first = settings.orchestrator

    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "222")
    second = settings.orchestrator

    assert first.claim_delay_ms == 111
    assert second.claim_delay_ms == 222
    assert first is not second
