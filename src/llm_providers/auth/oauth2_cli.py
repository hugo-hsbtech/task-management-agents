"""OAuth2CliToken auth strategy — OAuth2 token from explicit settings.

Token source is explicitly configured via OAuth2CliAuth:
  - env_var: read token from environment variable
  - token_path: read token from CLI-managed file
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.errors import AuthDetectionFailed

if TYPE_CHECKING:
    from pathlib import Path

    from settings.provider import OAuth2CliAuth


class OAuth2CliToken(AuthStrategy):
    """OAuth2 bearer token loaded from explicit settings configuration."""

    kind: ClassVar[str] = "oauth2_cli_token"

    def __init__(
        self,
        env_var: str | None = None,
        token_path: Path | None = None,
    ) -> None:
        self._env_var = env_var
        self._token_path = token_path

    def detect(self) -> bool:
        """Check if token source is configured. Always True when constructed from settings."""
        return True

    def resolve(self) -> Credential:
        """Resolve token from configured source."""
        # Try env_var first if configured
        if self._env_var:
            v = os.environ.get(self._env_var)
            if v:
                return Credential(
                    kind="oauth2_cli_token",
                    payload={"token": v, "source": f"env:{self._env_var}"},
                )

        # Try token_path if configured
        if self._token_path and self._token_path.exists():
            raw = self._token_path.read_text(encoding="utf-8").strip()
            token = self._extract_token(raw)
            return Credential(
                kind="oauth2_cli_token",
                payload={"token": token, "source": f"file:{self._token_path}"},
            )

        raise AuthDetectionFailed(
            f"OAuth2CliToken: neither env_var={self._env_var!r} nor "
            f"token_path={self._token_path!r} resolved a usable token."
        )

    @classmethod
    def from_settings(cls, auth_config: OAuth2CliAuth) -> OAuth2CliToken:
        """Create OAuth2CliToken from OAuth2CliAuth settings."""
        return cls(env_var=auth_config.env_var, token_path=auth_config.token_path)

    @classmethod
    def default(cls) -> OAuth2CliToken:
        """Default construction - requires explicit configuration."""
        return cls()

    @staticmethod
    def _extract_token(raw: str) -> str:
        """Extract token from JSON or return raw string."""
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(obj, dict):
            for key in ("access_token", "token"):
                value = obj.get(key)
                if isinstance(value, str):
                    return value
        return raw
