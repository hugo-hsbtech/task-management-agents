"""hsb.settings package-level re-exports — convenience surface."""


def test_orchestrator_settings_reexported():
    from settings import OrchestratorSettings as Original
    from settings import OrchestratorSettings as Reexport

    assert Reexport is Original


def test_codex_settings_reexported():
    from settings import CodexSettings as Original
    from settings import CodexSettings as Reexport

    assert Reexport is Original


def test_linear_settings_reexported():
    from settings import LinearSettings as Original
    from settings import LinearSettings as Reexport

    assert Reexport is Original


def test_github_settings_reexported():
    from settings import GitHubSettings as Original
    from settings import GitHubSettings as Reexport

    assert Reexport is Original


def test_wio_ipc_settings_reexported():
    from settings import WIOIPCSettings as Original
    from settings import WIOIPCSettings as Reexport

    assert Reexport is Original


def test_test_fixture_settings_reexported():
    from settings import TestFixtureSettings as Original
    from settings import TestFixtureSettings as Reexport

    assert Reexport is Original


def test_runtime_settings_reexported():
    from settings import RuntimeSettings as Original
    from settings import RuntimeSettings as Reexport

    assert Reexport is Original


def test_g1_helpers_reexported():
    from settings import FORBIDDEN_API_KEY_VARS, assert_oauth2_only
    from settings import (
        FORBIDDEN_API_KEY_VARS as Original_Const,
    )
    from settings import (
        assert_oauth2_only as Original_Fn,
    )

    assert FORBIDDEN_API_KEY_VARS is Original_Const
    assert assert_oauth2_only is Original_Fn
