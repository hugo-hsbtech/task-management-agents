"""HSB settings — FastAPI-style per-domain configuration.

Two access patterns, both first-class:

1. The `settings` singleton — recommended for production code:

       from hsb.settings import settings

       claim_delay_ms = settings.orchestrator.claim_delay_ms
       codex_home = settings.codex.home
       oauth_token = settings.runtime.claude_code_oauth_token

   Each attribute access returns a freshly-constructed per-domain Settings
   instance, so live env / .env changes between accesses are reflected.
   Validation cost is paid only for the sub-settings you touch.

2. Direct class import — recommended for tests that need to control
   instantiation timing or pass `_env_file=`:

       from hsb.settings.orchestrator import OrchestratorSettings

       assert OrchestratorSettings().claim_delay_ms == 200
"""

from hsb.settings.codex import CodexSettings
from hsb.settings.github import GitHubSettings
from hsb.settings.linear import LinearSettings
from hsb.settings.orchestrator import OrchestratorSettings
from hsb.settings.runtime import (
    FORBIDDEN_API_KEY_VARS,
    AgentRuntime,
    RuntimeSettings,
    assert_oauth2_only,
)
from hsb.settings.test_fixture import TestFixtureSettings
from hsb.settings.wio_ipc import WIOIPCSettings


class _Settings:
    """Aggregator namespace exposing each per-domain Settings class as a
    fresh-instance attribute.

    The attributes are `@property`-backed (not eager fields) so:

    - Validators run only for the sub-settings the caller actually touches.
    - Tests using `monkeypatch.setenv(...)` see updated values without
      re-importing the package.
    - The Work Item Orchestrator hard-block doesn't fire at module import
      time if `HSB_RUNTIME_WORK_ITEM_ORCHESTRATOR=codex` is set somewhere
      unrelated.
    """

    @property
    def codex(self) -> CodexSettings:
        return CodexSettings()

    @property
    def github(self) -> GitHubSettings:
        return GitHubSettings()

    @property
    def linear(self) -> LinearSettings:
        return LinearSettings()

    @property
    def orchestrator(self) -> OrchestratorSettings:
        return OrchestratorSettings()

    @property
    def runtime(self) -> RuntimeSettings:
        return RuntimeSettings()

    @property
    def test_fixture(self) -> TestFixtureSettings:
        return TestFixtureSettings()

    @property
    def wio_ipc(self) -> WIOIPCSettings:
        return WIOIPCSettings()


settings = _Settings()

__all__ = [
    "FORBIDDEN_API_KEY_VARS",
    "AgentRuntime",
    "CodexSettings",
    "GitHubSettings",
    "LinearSettings",
    "OrchestratorSettings",
    "RuntimeSettings",
    "TestFixtureSettings",
    "WIOIPCSettings",
    "assert_oauth2_only",
    "settings",
]
