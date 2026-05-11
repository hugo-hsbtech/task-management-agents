"""Per-agent runtime selection + Claude OAuth token.

Env vars: HSB_RUNTIME_<AGENT> (one per known agent) and
CLAUDE_CODE_OAUTH_TOKEN (sourced via validation_alias because it does
not share the HSB_RUNTIME_ prefix).

WIO is hard-frozen to "claude" because the stateful ClaudeSDKClient
session has no Codex equivalent (tracked separately). Passing
HSB_RUNTIME_WIO=codex raises ValidationError at construction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    """Per-agent runtime selection + Claude OAuth token."""

    model_config = SettingsConfigDict(env_prefix="HSB_RUNTIME_")

    # OAuth token — sourced by validation_alias because it doesn't share
    # the HSB_RUNTIME_ prefix. In pydantic-settings v2, a field's
    # validation_alias bypasses the class-level env_prefix.
    claude_code_oauth_token: SecretStr | None = Field(
        default=None,
        validation_alias="CLAUDE_CODE_OAUTH_TOKEN",
    )

    # Per-agent runtime selection. Explicit fields, one per known agent.
    backlog: Literal["claude", "codex"] = "claude"
    wio: Literal["claude"] = "claude"  # hard-blocked from "codex"
    qa: Literal["claude", "codex"] = "claude"
    uat: Literal["claude", "codex"] = "claude"
    risk: Literal["claude", "codex"] = "claude"
    git: Literal["claude", "codex"] = "claude"
    builder: Literal["claude", "codex"] = "claude"
    intelligence: Literal["claude", "codex"] = "claude"
    linear: Literal["claude", "codex"] = "claude"

    @field_validator(
        "backlog",
        "qa",
        "uat",
        "risk",
        "git",
        "builder",
        "intelligence",
        "linear",
        "wio",
        mode="before",
    )
    @classmethod
    def _normalize_runtime(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @model_validator(mode="after")
    def _wio_is_claude_only(self) -> RuntimeSettings:
        if self.wio != "claude":
            raise ValueError(
                "WIO is not flippable yet — stateful ClaudeSDKClient session "
                "has no Codex equivalent. Track separately when porting WIO."
            )
        return self
