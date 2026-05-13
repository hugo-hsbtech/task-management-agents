"""hsb.settings package-level re-exports — convenience surface."""


def test_orchestrator_settings_reexported():
    from settings import OrchestratorSettings as Reexport
    from settings.orchestrator import OrchestratorSettings as Original

    assert Reexport is Original


def test_codex_settings_reexported():
    from settings import CodexSettings as Reexport
    from settings.codex import CodexSettings as Original

    assert Reexport is Original


def test_linear_settings_reexported():
    from settings import LinearSettings as Reexport
    from settings.linear import LinearSettings as Original

    assert Reexport is Original


def test_github_settings_reexported():
    from settings import GitHubSettings as Reexport
    from settings.github import GitHubSettings as Original

    assert Reexport is Original


def test_wio_ipc_settings_reexported():
    from settings import WIOIPCSettings as Reexport
    from settings.wio_ipc import WIOIPCSettings as Original

    assert Reexport is Original


def test_test_fixture_settings_reexported():
    from settings import TestFixtureSettings as Reexport
    from settings.test_fixture import TestFixtureSettings as Original

    assert Reexport is Original


def test_runtime_settings_reexported():
    from settings import RuntimeSettings as Reexport
    from settings.runtime import RuntimeSettings as Original

    assert Reexport is Original


def test_g1_helpers_reexported():
    from settings import FORBIDDEN_API_KEY_VARS, assert_oauth2_only
    from settings.runtime import (
        FORBIDDEN_API_KEY_VARS as Original_Const,
    )
    from settings.runtime import (
        assert_oauth2_only as Original_Fn,
    )

    assert FORBIDDEN_API_KEY_VARS is Original_Const
    assert assert_oauth2_only is Original_Fn


def test_codex_model_reexported():
    from settings import CodexModel  # noqa: F401 — import check
    assert CodexModel.codex_mini_latest == "codex-mini-latest"
