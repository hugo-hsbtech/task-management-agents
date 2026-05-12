"""Tests for hsb.settings.test_fixture.TestFixtureSettings."""

from pathlib import Path


def test_all_defaults_when_unset(monkeypatch):
    for var in (
        "HSB_TEST_FIXTURE_URL",
        "HSB_TEST_FIXTURE_PATH",
        "HSB_LIVE_CODEX",
        "TEST_WORK_ITEM_ID",
        "LINEAR_TEST_ISSUE_ID",
    ):
        monkeypatch.delenv(var, raising=False)

    from settings import TestFixtureSettings

    s = TestFixtureSettings()
    assert s.fixture_url is None
    assert s.fixture_path is None
    assert s.live_codex is False
    assert s.test_work_item_id is None
    assert s.linear_test_issue_id is None


def test_fixture_url_alias(monkeypatch):
    monkeypatch.setenv("HSB_TEST_FIXTURE_URL", "https://github.com/me/hsb-test-fixture")
    from settings import TestFixtureSettings

    assert TestFixtureSettings().fixture_url == "https://github.com/me/hsb-test-fixture"


def test_fixture_path_alias(monkeypatch):
    monkeypatch.setenv("HSB_TEST_FIXTURE_PATH", "/tmp/fixture")
    from settings import TestFixtureSettings

    assert TestFixtureSettings().fixture_path == Path("/tmp/fixture")


def test_live_codex_truthy(monkeypatch):
    monkeypatch.setenv("HSB_LIVE_CODEX", "1")
    from settings import TestFixtureSettings

    assert TestFixtureSettings().live_codex is True


def test_live_codex_falsy(monkeypatch):
    monkeypatch.setenv("HSB_LIVE_CODEX", "0")
    from settings import TestFixtureSettings

    assert TestFixtureSettings().live_codex is False


def test_test_work_item_id_alias(monkeypatch):
    monkeypatch.setenv("TEST_WORK_ITEM_ID", "LIN-999")
    from settings import TestFixtureSettings

    assert TestFixtureSettings().test_work_item_id == "LIN-999"


def test_linear_test_issue_id_alias(monkeypatch):
    monkeypatch.setenv("LINEAR_TEST_ISSUE_ID", "LIN-555")
    from settings import TestFixtureSettings

    assert TestFixtureSettings().linear_test_issue_id == "LIN-555"
