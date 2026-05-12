"""ApiKey auth strategy — literal key from an env var."""

from __future__ import annotations

import os
from typing import ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.errors import AuthDetectionFailed


class ApiKey(AuthStrategy):
    """API-key credential read from an environment variable.

    Construction:
      ApiKey(env_var="ANTHROPIC_API_KEY")  — explicit
      ApiKey.default()                     — uses LLM_PROVIDERS_API_KEY
                                             (callers usually pass explicit
                                             env_var; default() exists for
                                             auto_resolve_auth's walk).
    """

    kind: ClassVar[str] = "api_key"
    _DEFAULT_ENV_VAR: ClassVar[str] = "LLM_PROVIDERS_API_KEY"

    def __init__(self, env_var: str = _DEFAULT_ENV_VAR) -> None:
        self._env_var = env_var

    def detect(self) -> bool:
        return bool(os.environ.get(self._env_var))

    def resolve(self) -> Credential:
        value = os.environ.get(self._env_var)
        if not value:
            raise AuthDetectionFailed(
                f"ApiKey: env var {self._env_var!r} is not set or empty."
            )
        return Credential(
            kind="api_key",
            payload={"api_key": value, "env_var": self._env_var},
        )

    @classmethod
    def default(cls) -> ApiKey:
        return cls()
