"""Per-domain settings classes. Import the one your code needs:

    from hsb.settings.orchestrator import OrchestratorSettings

This package has no top-level aggregator by design — see
docs/superpowers/specs/2026-05-11-settings-consistent-module-design.md §4.
The re-exports below are a convenience surface; per-module imports remain
the canonical pattern.
"""

from hsb.settings.codex import CodexSettings
from hsb.settings.github import GitHubSettings
from hsb.settings.linear import LinearSettings
from hsb.settings.orchestrator import OrchestratorSettings
from hsb.settings.runtime import (
    FORBIDDEN_API_KEY_VARS,
    RuntimeSettings,
    assert_oauth2_only,
)
from hsb.settings.test_fixture import TestFixtureSettings
from hsb.settings.wio_ipc import WIOIPCSettings

__all__ = [
    "FORBIDDEN_API_KEY_VARS",
    "CodexSettings",
    "GitHubSettings",
    "LinearSettings",
    "OrchestratorSettings",
    "RuntimeSettings",
    "TestFixtureSettings",
    "WIOIPCSettings",
    "assert_oauth2_only",
]
