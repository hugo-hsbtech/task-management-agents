"""OAuth2CliToken auth strategy — token written by a vendor CLI.

Reads from one of:
  - an environment variable (e.g. CLAUDE_CODE_OAUTH_TOKEN)
  - a token file (e.g. ~/.codex/auth.json, ~/.gemini/oauth.json)

If both are configured, env var wins. The file is parsed as JSON when possible
(looking for "access_token" or "token" keys); otherwise its raw contents are
treated as the token string.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.errors import AuthDetectionFailed

if TYPE_CHECKING:
    from pathlib import Path


class OAuth2CliToken(AuthStrategy):
    """OAuth2 bearer token sourced from an env var or a CLI-managed file."""

    kind: ClassVar[str] = "oauth2_cli_token"

    def __init__(
        self,
        env_var: str | None = None,
        token_path: Path | None = None,
    ) -> None:
        self._env_var = env_var
        self._token_path = token_path

    @classmethod
    def default(cls) -> OAuth2CliToken:
        # Caller must supply explicit env_var / token_path for detection to
        # succeed. default() exists so auto_resolve_auth can walk uniformly.
        return cls()

    def detect(self) -> bool:
        if self._env_var and os.environ.get(self._env_var):
            return True
        return bool(self._token_path and self._token_path.exists())

    def resolve(self) -> Credential:
        if self._env_var:
            v = os.environ.get(self._env_var)
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

    @staticmethod
    def _extract_token(raw: str) -> str:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(obj, dict):
            for key in ("access_token", "token"):
                value = obj.get(key)
                if isinstance(value, str):
                    return value
        # JSON but unknown shape — return the raw text. Providers can override
        # _extract_token via subclassing if a specific shape is required.
        return raw
