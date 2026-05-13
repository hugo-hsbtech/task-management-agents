"""Per-agent runtime selection + provider credentials.

Env vars (no HSB_RUNTIME_ prefix, sourced via validation_alias):
  - ``CLAUDE_CODE_OAUTH_TOKEN`` — Claude OAuth2
  - ``ANTHROPIC_API_KEY`` — Claude API key (gated by G1 escape hatch)
  - ``OPENAI_API_KEY`` — OpenAI API key (gated by G1 escape hatch)

Env vars (HSB_RUNTIME_ prefix): one per known agent — see field list.

The Work Item Orchestrator is hard-frozen to ``claude`` because the
stateful ``ClaudeSDKClient`` session has no Codex equivalent (tracked
separately). Setting ``HSB_RUNTIME_WORK_ITEM_ORCHESTRATOR=codex`` raises
``ValidationError`` at construction with a project-specific explanation.
"""

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The forbidden env vars are listed here as the single source of truth.
# ``_G1Guard`` is generated from this tuple below so adding a new var only
# requires touching one place.
FORBIDDEN_API_KEY_VARS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
)


class _G1Guard(BaseSettings):
    """Pydantic-backed G1 enforcer. Constructing this class raises
    ``RuntimeError`` if any forbidden API-key env var is set. Pydantic
    propagates non-ValueError exceptions from validators unwrapped, so
    the historical ``RuntimeError`` contract is preserved.
    """

    anthropic_api_key: str | None = Field(
        default=None, validation_alias="ANTHROPIC_API_KEY"
    )
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    @model_validator(mode="after")
    def _refuse_forbidden(self) -> Self:
        forbidden = [
            alias
            for alias, name in zip(
                FORBIDDEN_API_KEY_VARS,
                ("anthropic_api_key", "openai_api_key"),
                strict=True,
            )
            if getattr(self, name) is not None
        ]
        if forbidden:
            raise RuntimeError(
                f"G1 violation: {', '.join(forbidden)} set — forbidden. "
                "Use OAuth tokens only (CLAUDE_CODE_OAUTH_TOKEN for Claude, "
                "`codex login --device-auth` for Codex)."
            )
        return self


class AgentRuntime(StrEnum):
    """LLM backend an agent dispatches against. ``StrEnum`` makes values
    compare equal to plain strings (``"claude"``, ``"codex"``) — convenient
    for env vars, config files, and JSON serialization."""

    CLAUDE = "claude"
    CODEX = "codex"


def assert_oauth2_only(agent_name: str | None = None) -> None:
    """G1 (AI-SPEC §6) — function-entry-time guard. Rejects metered API keys
    for either runtime. Operators must use OAuth tokens:
      - Claude:  CLAUDE_CODE_OAUTH_TOKEN  (from `claude setup-token`)
      - Codex:   ~/.codex/auth.json       (from `codex login --device-auth`)

    Called from :func:`make_options` before every ``ClaudeAgentOptions``
    construction. Function-time (NOT module-import-time) so test environments
    that legitimately have ``ANTHROPIC_API_KEY`` set for unrelated reasons do
    not break pytest collection. The defensive pairing is the session-scoped
    autouse fixture in ``tests/conftest.py`` that unsets the env var at
    session start.

    When ``agent_name`` is provided, delegates to
    :func:`hsb.runtime.policy.allowed_auth_kinds` for the per-agent escape
    hatch (``HSB_AUTH_ALLOW_API_KEY_<AGENT>=1``). When ``agent_name`` is
    ``None`` (legacy default), applies the strict pydantic-settings check
    unconditionally.
    """
    if agent_name is not None:
        # Lazy import — hsb.runtime.policy is in a sibling subpackage and
        # only relevant when a caller explicitly opts into per-agent G1.
        from hsb.runtime.policy import allowed_auth_kinds

        if "api_key" in allowed_auth_kinds(agent_name):
            return
    _G1Guard()


class RuntimeSettings(BaseSettings):
    """Per-agent runtime selection + Claude OAuth token.

    Field names are full-word slugs (no acronyms) so env vars stay
    self-explanatory: ``HSB_RUNTIME_WORK_ITEM_ORCHESTRATOR``,
    ``HSB_RUNTIME_QUALITY_ASSURANCE``, ``HSB_RUNTIME_USER_ACCEPTANCE_TESTING``.
    """

    model_config = SettingsConfigDict(env_prefix="HSB_RUNTIME_")

    # Provider credentials — sourced by validation_alias because they
    # don't share the HSB_RUNTIME_ prefix. In pydantic-settings v2, a
    # field's validation_alias bypasses the class-level env_prefix.
    #
    # All three are read unconditionally so callers can resolve any
    # (provider, auth_kind) combo via the auth factory. The G1 policy in
    # :func:`assert_oauth2_only` separately governs whether API-key kinds
    # are allowed at agent dispatch time.
    claude_code_oauth_token: SecretStr | None = Field(
        default=None,
        validation_alias="CLAUDE_CODE_OAUTH_TOKEN",
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="ANTHROPIC_API_KEY",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )

    # Per-agent runtime selection. Explicit fields, one per known agent.
    # `work_item_orchestrator` accepts AgentRuntime.CODEX at the field-validation
    # layer so the _work_item_orchestrator_is_claude_only model_validator can
    # intercept it and raise the project-specific explanation. Narrowing the
    # type to only AgentRuntime.CLAUDE would make pydantic reject CODEX with a
    # generic enum_error, never reaching the explanatory message about the
    # missing stateful-client Codex equivalent.
    backlog: AgentRuntime = AgentRuntime.CLAUDE
    work_item_orchestrator: AgentRuntime = AgentRuntime.CLAUDE
    quality_assurance: AgentRuntime = AgentRuntime.CLAUDE
    user_acceptance_testing: AgentRuntime = AgentRuntime.CLAUDE
    risk: AgentRuntime = AgentRuntime.CLAUDE
    git: AgentRuntime = AgentRuntime.CLAUDE
    builder: AgentRuntime = AgentRuntime.CLAUDE
    intelligence: AgentRuntime = AgentRuntime.CLAUDE
    linear: AgentRuntime = AgentRuntime.CLAUDE

    _AGENT_FIELDS: ClassVar[tuple[str, ...]] = (
        "backlog",
        "work_item_orchestrator",
        "quality_assurance",
        "user_acceptance_testing",
        "risk",
        "git",
        "builder",
        "intelligence",
        "linear",
    )

    @field_validator(*_AGENT_FIELDS, mode="before")
    @classmethod
    def _normalize_runtime(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @model_validator(mode="after")
    def _work_item_orchestrator_is_claude_only(self) -> Self:
        if self.work_item_orchestrator != AgentRuntime.CLAUDE:
            raise ValueError(
                "Work Item Orchestrator is not flippable yet — the stateful "
                "ClaudeSDKClient session has no Codex equivalent. Track "
                "separately when porting the orchestrator."
            )
        return self
