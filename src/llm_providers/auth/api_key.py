"""ApiKey auth strategy — typed value holder.

The strategy never reads ``os.environ`` or files. Build it via the auth
factory (``llm_providers.auth.factory.resolve_auth``) which routes through
``settings`` to read the right env var for the (provider, auth_kind)
combo. Tests construct directly with a literal value.
"""

from __future__ import annotations

from typing import ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.registry import AuthRegistry


@AuthRegistry.register("api_key")
class ApiKey(AuthStrategy):
    """API-key credential. Holds a resolved, non-empty key.

    Construction:
      ApiKey(api_key="sk-...")  — explicit value (tests, settings-resolved)

    There is no ``env_var`` parameter and no ``default()`` factory — the
    caller is expected to obtain the value from settings before construction.
    """

    kind: ClassVar[str] = "api_key"

    def __init__(self, *, api_key: str) -> None:
        if not api_key:
            raise ValueError("ApiKey requires a non-empty api_key")
        self._api_key = api_key

    def resolve(self) -> Credential:
        return Credential(
            kind="api_key",
            payload={"api_key": self._api_key, "source": "settings"},
        )
