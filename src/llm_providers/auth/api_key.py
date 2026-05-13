"""ApiKey auth strategy — opaque key holder.

The strategy itself never reads ``os.environ``. The settings layer
(``settings._env``) is responsible for resolving env vars and passing the
resolved string into ``ApiKey(api_key=...)`` or ``ApiKey.from_auth(cfg)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.errors import AuthDetectionFailed
from llm_providers.registry import AuthRegistry
from settings._env import read_env

if TYPE_CHECKING:
    from settings.provider import ApiKeyAuth


@AuthRegistry.register("api_key")
class ApiKey(AuthStrategy):
    """API-key credential.

    Construction:
      ApiKey(api_key="sk-...")   — explicit key (settings / test)
      ApiKey(env_var="MY_KEY")   — name of an env var, resolved at resolve-time
                                   via ``settings._env.read_env``
      ApiKey.from_auth(cfg)      — load from ``ApiKeyAuth`` settings
      ApiKey.default()           — raises ``AuthDetectionFailed``; callers must
                                   construct explicitly. (Historically defaulted
                                   to LLM_PROVIDERS_API_KEY which nothing set.)
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
        # `is not None` (not truthiness): an explicit empty string is a real
        # caller-supplied value — surface it as such rather than silently
        # falling back to the env-var source label, which would mask a
        # misconfiguration.
        self._source = source if api_key is not None else f"env:{env_var}"

    def detect(self) -> bool:
        """True when a usable key is available (explicit non-empty) or the env
        var is set."""
        if self._env_var:
            return bool(read_env(self._env_var))
        # Explicit empty string is treated as a misconfiguration, not as
        # "available" — keeps detect()/resolve() symmetric.
        return bool(self._api_key)

    def resolve(self) -> Credential:
        if self._env_var:
            key = read_env(self._env_var, "") or ""
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
        if not self._api_key:
            raise AuthDetectionFailed("ApiKey constructed with an empty api_key value.")
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
        """No safe default — ApiKey requires explicit construction.

        Historically returned ``cls(env_var="LLM_PROVIDERS_API_KEY")`` but no
        caller in the repo ever set that env var; every real provider
        subclasses ``ApiKey`` and overrides ``default()`` with the canonical
        env var for that vendor (e.g. ``ANTHROPIC_API_KEY``,
        ``OPENAI_API_KEY``). Raising here turns a silent miss into a loud one.
        """
        raise AuthDetectionFailed(
            "ApiKey.default() has no value to return. Either construct "
            "explicitly via ApiKey(env_var=...) / ApiKey.from_auth(cfg), or "
            "subclass ApiKey and override default() with the provider's "
            "canonical env var."
        )
