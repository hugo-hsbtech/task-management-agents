"""ApiKey auth strategy — explicit key or env-var detection.

Supports two modes:
  - Explicit key: ``ApiKey(api_key="sk-...")`` or ``ApiKey.from_auth(cfg)``
  - Env-var lazy: ``ApiKey(env_var="MY_KEY")`` — resolved at ``resolve()`` time.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.errors import AuthDetectionFailed

if TYPE_CHECKING:
    from settings.provider import ApiKeyAuth


class ApiKey(AuthStrategy):
    """API-key credential from settings or environment variable.

    Construction:
      ApiKey(api_key="sk-...")   — explicit key (settings / test)
      ApiKey(env_var="MY_KEY")   — lazy env-var resolution
      ApiKey.from_auth(cfg)      — load from ApiKeyAuth settings
      ApiKey.default()           — env-var auto-detect (LLM_PROVIDERS_API_KEY)
    """

    kind: ClassVar[str] = "api_key"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        env_var: str | None = None,
        source: str = "settings",
    ) -> None:
        if api_key is None and env_var is None:
            raise ValueError("ApiKey requires either api_key= or env_var=")
        self._api_key = api_key or ""
        self._env_var = env_var
        self._source = source if api_key else f"env:{env_var}"

    def detect(self) -> bool:
        """True when the key is available (explicit) or the env var is set."""
        if self._env_var:
            return bool(os.environ.get(self._env_var))
        return True

    def resolve(self) -> Credential:
        if self._env_var:
            key = os.environ.get(self._env_var, "")
            if not key:
                raise AuthDetectionFailed(f"{self._env_var} not set")
            return Credential(
                kind="api_key",
                payload={
                    "api_key": key,
                    "source": self._source,
                    "env_var": self._env_var,
                },
            )
        return Credential(
            kind="api_key",
            payload={"api_key": self._api_key, "source": self._source},
        )

    @classmethod
    def from_auth(cls, auth_config: ApiKeyAuth) -> ApiKey:
        """Create ApiKey from ApiKeyAuth settings."""
        return cls(api_key=auth_config.key.get_secret_value(), source="settings")

    @classmethod
    def default(cls) -> ApiKey:
        """Auto-detect from LLM_PROVIDERS_API_KEY env var."""
        return cls(env_var="LLM_PROVIDERS_API_KEY")
