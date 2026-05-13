"""OAuth2CliToken auth strategy — OAuth2 bearer-token holder.

Token source is configured explicitly via ``env_var`` or ``token_path``;
env reads are routed through ``settings._env.read_env`` so this module
never touches ``os.environ`` directly.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.errors import AuthDetectionFailed
from llm_providers.registry import AuthRegistry
from settings._env import read_env

if TYPE_CHECKING:
    from pathlib import Path

    from settings.provider import OAuth2CliAuth


@AuthRegistry.register("oauth2_cli_token")
class OAuth2CliToken(AuthStrategy):
    """OAuth2 bearer token loaded from a configured env var or file path."""

    kind: ClassVar[str] = "oauth2_cli_token"

    def __init__(
        self,
        env_var: str | None = None,
        token_path: Path | None = None,
    ) -> None:
        self._env_var = env_var
        self._token_path = token_path

    def detect(self) -> bool:
        """True iff the configured token source is present.

        env_var → the env var is set and non-empty.
        token_path → the file exists.
        Otherwise (no source configured, or source empty) → False, so
        ``auto_resolve_auth`` moves to the next strategy.
        """
        if self._env_var and read_env(self._env_var):
            return True
        return bool(self._token_path and self._token_path.exists())

    def resolve(self) -> Credential:
        """Resolve token from configured source."""
        if self._env_var:
            v = read_env(self._env_var)
            if v:
                return Credential(
                    kind="oauth2_cli_token",
                    payload={"token": v, "source": f"env:{self._env_var}"},
                )

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
        """Default construction — no preconfigured source.

        Returns an instance with no env_var / token_path. ``detect()`` will
        return False and ``auto_resolve_auth`` will fall through. Real
        providers subclass this and override ``default()`` with the canonical
        token source (``CLAUDE_CODE_OAUTH_TOKEN``, ``~/.codex/auth.json``, …).
        """
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
