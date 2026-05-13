"""Strict-direct auth resolution.

Each (provider name, auth kind) pair maps to exactly one credential source.
``resolve_auth(provider_name, auth_kind)`` reads that source from settings
(env vars via pydantic-settings, or a known file path) and returns a
constructed ``AuthStrategy`` carrying the resolved value. Missing sources
fail fast with a message naming the env var or file the operator must set.

This replaces the prior env-var-name plumbing on ``ApiKey`` and
``OAuth2CliToken`` — strategies are now pure value holders, and there is
exactly one place that touches the environment.

Design rationale: Walk-and-detect (try each strategy's detect() until one
succeeds) was replaced with explicit (provider, auth_kind) mapping because:
  - Reduces ambiguity: no "which strategy wins if multiple detect()" cases
  - Improves error messages: tells the operator exactly what env var is missing
  - Enables priority order: OAuth2 first (matches G1 policy), API-key fallback
  - Simplifies testing: no dynamic strategy selection to mock
  - Centralizes env access: a single factory function is the only env reader
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.errors import AuthResolutionError

if TYPE_CHECKING:
    from pathlib import Path


def _extract_codex_token(raw: str) -> str:
    """Pull the bearer token out of a Codex ``auth.json`` payload.

    The Codex CLI writes the file as JSON with an ``access_token`` field
    (sometimes ``token`` on older versions). For maximum forward-compat we
    accept either, and fall back to the raw text only when it isn't JSON
    at all — that lets a hand-rolled fixture be a plain token string.
    """
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    if isinstance(obj, dict):
        for key in ("access_token", "token"):
            value = obj.get(key)
            if isinstance(value, str) and value:
                return value
    return raw.strip()


def resolve_auth(provider_name: str, auth_kind: str) -> AuthStrategy:
    """Return a fully-resolved ``AuthStrategy`` for the given combo.

    Supported combos (every other call fails with ``AuthResolutionError``):

    ===========  ======================  ===========================================
    Provider     Auth kind               Source
    ===========  ======================  ===========================================
    ``claude``   ``oauth2_cli_token``    ``CLAUDE_CODE_OAUTH_TOKEN`` env var
    ``claude``   ``api_key``             ``ANTHROPIC_API_KEY`` env var
    ``openai``   ``oauth2_cli_token``    ``<settings.codex.home>/auth.json``
    ``openai``   ``api_key``             ``OPENAI_API_KEY`` env var
    ===========  ======================  ===========================================
    """
    # Lazy import so this module stays cheap to import when only the
    # strategies are needed (avoids pulling pydantic-settings at import).
    # CredentialsSettings is independent of RuntimeSettings so reading
    # credentials never triggers agent-runtime field validation.
    from settings.codex import CodexSettings
    from settings.credentials import CredentialsSettings

    creds = CredentialsSettings()

    if provider_name == "claude":
        if auth_kind == "oauth2_cli_token":
            tok = creds.claude_code_oauth_token
            if tok is None:
                raise AuthResolutionError(
                    "Claude OAuth2 token auth requires CLAUDE_CODE_OAUTH_TOKEN to be set. "
                    "Run `claude setup-token` to obtain one."
                )
            return OAuth2CliToken(token=tok.get_secret_value())
        if auth_kind == "api_key":
            key = creds.anthropic_api_key
            if key is None:
                raise AuthResolutionError(
                    "Claude API-key auth requires ANTHROPIC_API_KEY to be set."
                )
            return ApiKey(api_key=key.get_secret_value())

    if provider_name == "openai":
        if auth_kind == "oauth2_cli_token":
            auth_file = _codex_auth_file(CodexSettings().home)
            if not auth_file.exists():
                raise AuthResolutionError(
                    f"OpenAI/Codex OAuth2 requires {auth_file} to exist. "
                    "Run `codex login --device-auth` to create it."
                )
            return OAuth2CliToken(
                token=_extract_codex_token(auth_file.read_text(encoding="utf-8"))
            )
        if auth_kind == "api_key":
            key = creds.openai_api_key
            if key is None:
                raise AuthResolutionError(
                    "OpenAI api_key auth requires OPENAI_API_KEY to be set."
                )
            return ApiKey(api_key=key.get_secret_value())

    raise AuthResolutionError(
        f"Unsupported (provider, auth_kind) combination: "
        f"({provider_name!r}, {auth_kind!r}). "
        "See resolve_auth docstring for the supported matrix."
    )


def _codex_auth_file(codex_home: Path) -> Path:
    """The file Codex CLI writes after `codex login --device-auth`."""
    return codex_home / "auth.json"


__all__ = ["AuthResolutionError", "resolve_auth"]
