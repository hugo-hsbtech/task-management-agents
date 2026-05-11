"""hsb.settings package-level re-exports — convenience surface."""


def test_orchestrator_settings_reexported():
    from hsb.settings import OrchestratorSettings as Reexport
    from hsb.settings.orchestrator import OrchestratorSettings as Original

    assert Reexport is Original


def test_codex_settings_reexported():
    from hsb.settings import CodexSettings as Reexport
    from hsb.settings.codex import CodexSettings as Original

    assert Reexport is Original


def test_linear_settings_reexported():
    from hsb.settings import LinearSettings as Reexport
    from hsb.settings.linear import LinearSettings as Original

    assert Reexport is Original


def test_github_settings_reexported():
    from hsb.settings import GitHubSettings as Reexport
    from hsb.settings.github import GitHubSettings as Original

    assert Reexport is Original


def test_wio_ipc_settings_reexported():
    from hsb.settings import WIOIPCSettings as Reexport
    from hsb.settings.wio_ipc import WIOIPCSettings as Original

    assert Reexport is Original


def test_test_fixture_settings_reexported():
    from hsb.settings import TestFixtureSettings as Reexport
    from hsb.settings.test_fixture import TestFixtureSettings as Original

    assert Reexport is Original


def test_runtime_settings_reexported():
    from hsb.settings import RuntimeSettings as Reexport
    from hsb.settings.runtime import RuntimeSettings as Original

    assert Reexport is Original


def test_g1_helpers_reexported():
    from hsb.settings import FORBIDDEN_API_KEY_VARS, assert_oauth2_only
    from hsb.settings.runtime import (
        FORBIDDEN_API_KEY_VARS as Original_Const,
    )
    from hsb.settings.runtime import (
        assert_oauth2_only as Original_Fn,
    )

    assert FORBIDDEN_API_KEY_VARS is Original_Const
    assert assert_oauth2_only is Original_Fn
