"""Per-agent runtime selection + Claude OAuth token.

Env vars: ``HSB_RUNTIME_<AGENT>`` (one per known agent — see fields below)
and ``CLAUDE_CODE_OAUTH_TOKEN`` (sourced via validation_alias because it
does not share the ``HSB_RUNTIME_`` prefix).

The Work Item Orchestrator is hard-frozen to ``claude`` because the
stateful ``ClaudeSDKClient`` session has no Codex equivalent (tracked
separately). Setting ``HSB_RUNTIME_WORK_ITEM_ORCHESTRATOR=codex`` raises
``ValidationError`` at construction with a project-specific explanation.
"""

from enum import StrEnum
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class _ForbiddenKeysProbe(BaseSettings):
    """Probe-only Settings class. ``assert_oauth2_only`` instantiates this
    to read the forbidden API-key env vars via pydantic instead of
    ``os.environ``. Never used as actual project configuration — the whole
    point is that these vars are NOT supposed to be set."""

    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias="ANTHROPIC_API_KEY",
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )


# Public list of env vars the G1 guard rejects. Derived from
# ``_ForbiddenKeysProbe`` so the two stay in sync.
FORBIDDEN_API_KEY_VARS: tuple[str, ...] = tuple(
    str(field.validation_alias)
    for field in _ForbiddenKeysProbe.model_fields.values()
    if field.validation_alias is not None
)


class AgentRuntime(StrEnum):
    """LLM backend an agent dispatches against. ``StrEnum`` makes values
    compare equal to plain strings (``"claude"``, ``"codex"``) — convenient
    for env vars, config files, and JSON serialization."""

    CLAUDE = "claude"
    CODEX = "codex"


def assert_oauth2_only() -> None:
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
    """
    probe = _ForbiddenKeysProbe()
    forbidden = [
        str(_ForbiddenKeysProbe.model_fields[name].validation_alias)
        for name, value in probe.model_dump().items()
        if value is not None
    ]
    if forbidden:
        raise RuntimeError(
            f"G1 violation: {', '.join(forbidden)} set — forbidden. "
            "Use OAuth tokens only (CLAUDE_CODE_OAUTH_TOKEN for Claude, "
            "`codex login --device-auth` for Codex)."
        )


class RuntimeSettings(BaseSettings):
    """Per-agent runtime selection + Claude OAuth token.

    Field names are full-word slugs (no acronyms) so env vars stay
    self-explanatory: ``HSB_RUNTIME_WORK_ITEM_ORCHESTRATOR``,
    ``HSB_RUNTIME_QUALITY_ASSURANCE``, ``HSB_RUNTIME_USER_ACCEPTANCE_TESTING``.
    """

    model_config = SettingsConfigDict(env_prefix="HSB_RUNTIME_")

    # OAuth token — sourced by validation_alias because it doesn't share
    # the HSB_RUNTIME_ prefix. In pydantic-settings v2, a field's
    # validation_alias bypasses the class-level env_prefix.
    claude_code_oauth_token: SecretStr | None = Field(
        default=None,
        validation_alias="CLAUDE_CODE_OAUTH_TOKEN",
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

    @field_validator(
        "backlog",
        "work_item_orchestrator",
        "quality_assurance",
        "user_acceptance_testing",
        "risk",
        "git",
        "builder",
        "intelligence",
        "linear",
        mode="before",
    )
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
