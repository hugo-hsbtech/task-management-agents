"""OAuth2CliToken auth strategy — typed value holder.

Holds a resolved bearer token. Build via the auth factory
(:func:`llm_providers.auth.factory.resolve_auth`) which knows which env
var or file to read for each (provider, auth_kind) combo. Tests
construct directly with a literal token.
"""

from __future__ import annotations

from typing import ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.registry import AuthRegistry


@AuthRegistry.register("oauth2_cli_token")
class OAuth2CliToken(AuthStrategy):
    """OAuth2 bearer token. Holds a resolved, non-empty token."""

    kind: ClassVar[str] = "oauth2_cli_token"

    def __init__(self, *, token: str) -> None:
        if not token:
            raise ValueError("OAuth2CliToken requires a non-empty token")
        self._token = token

    def resolve(self) -> Credential:
        return Credential(
            kind="oauth2_cli_token",
            payload={"token": self._token, "source": "settings"},
        )
