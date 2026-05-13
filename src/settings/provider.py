"""Provider and model configuration."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, SecretStr, model_validator


class ClaudeModel(StrEnum):
    # Canonical 1M-context model IDs use lowercase ``[1m]`` — verified against
    # the model index used by the Claude Code CLI and Anthropic dashboard.
    opus_1m = "claude-opus[1m]"
    opus_4_7 = "claude-opus-4-7"
    opus_4_6 = "claude-opus-4-6"
    opus_4_5 = "claude-opus-4-5"
    sonnet_1m = "claude-sonnet[1m]"
    sonnet_4_6 = "claude-sonnet-4-6"
    haiku_4_5 = "claude-haiku-4-5"


class OpenAIModel(StrEnum):
    gpt_4o = "gpt-4o"
    o4_mini = "o4-mini"


class GeminiModel(StrEnum):
    gemini_2_5_pro = "gemini-2.5-pro"
    gemini_2_5_flash = "gemini-2.5-flash"
    gemini_2_5_flash_lite = "gemini-2.5-flash-lite"
    gemini_2_0_flash = "gemini-2.0-flash"


class CodexModel(StrEnum):
    # ChatGPT-Codex-supported slugs. The legacy `codex-mini-latest` /
    # `o4-mini` slugs are API-key-only and rejected by ChatGPT OAuth seats —
    # this project mandates OAuth, so the enum exposes only ChatGPT-supported
    # models. The Python identifier `codex_mini_latest` is kept for source
    # compatibility but now points at the ChatGPT-Codex mini variant.
    codex_mini_latest = "gpt-5.4-mini"
    # Flagship ChatGPT-Codex model — "strongest agentic coding model"
    # (per codex CLI v0.130 release notes). Use for high-quality structured
    # output where the mini variant under-performs.
    gpt_5_5 = "gpt-5.5"
    # Intentionally mirrors OpenAIModel.o4_mini — both backends can target this model.
    o4_mini = "o4-mini"


class ProviderName(StrEnum):
    claude = "claude"
    openai = "openai"
    gemini = "gemini"
    codex = "codex"


# ============================================================================
# Auth Configurations (discriminated union)
# ============================================================================


class ApiKeyAuth(BaseModel):
    """API key authentication for providers that support it."""

    kind: Literal["api_key"] = "api_key"
    key: SecretStr  # Loaded from env or explicit config


class OAuth2CliAuth(BaseModel):
    """OAuth2 token from a CLI-managed credential source.

    Strict-direct — there are no ``env_var`` / ``token_path`` parameters.
    The source is determined by ``(provider name, "oauth2_cli_token")``:
      - Claude → ``CLAUDE_CODE_OAUTH_TOKEN`` env var
      - OpenAI / Codex → ``<settings.codex.home>/auth.json`` file

    See :func:`llm_providers.auth.factory.resolve_auth` for the matrix.
    """

    kind: Literal["oauth2_cli"] = "oauth2_cli"


class OAuth2ADCAuth(BaseModel):
    """Google Cloud Application Default Credentials for GCP services."""

    kind: Literal["oauth2_adc"] = "oauth2_adc"
    # ADC uses gcloud SDK or GOOGLE_APPLICATION_CREDENTIALS env var


AuthConfig = Annotated[
    ApiKeyAuth | OAuth2CliAuth | OAuth2ADCAuth,
    Field(discriminator="kind"),
]


# ============================================================================
# Provider-Specific Configurations
# ============================================================================


class GeminiConfig(BaseModel):
    """Gemini-specific GCP configuration for Vertex AI."""

    project_id: str | None = None
    location: str = "us-central1"


class ClaudeConfig(BaseModel):
    """Claude-specific configuration (placeholder for future options)."""

    pass


class OpenAIConfig(BaseModel):
    """OpenAI-specific configuration."""

    organization: str | None = None


# ============================================================================
# Main Provider Settings
# ============================================================================


class ProviderSettings(BaseModel):
    """Provider configuration with discriminated auth + provider-specific configs.

    Examples:
        # Claude with OAuth2 CLI (token sourced from CLAUDE_CODE_OAUTH_TOKEN)
        ProviderSettings(
            name=ProviderName.claude,
            model="claude-opus-4-5",
            auth=OAuth2CliAuth(),
        )

        # Gemini with API key
        ProviderSettings(
            name=ProviderName.gemini,
            model="gemini-2.5-pro",
            auth=ApiKeyAuth(key="..."),
        )

        # Gemini with ADC on GCP
        ProviderSettings(
            name=ProviderName.gemini,
            model="gemini-2.5-pro",
            auth=OAuth2ADCAuth(),
            gemini=GeminiConfig(project_id="my-gcp-project", location="us-east4"),
        )
    """

    name: ProviderName = ProviderName.claude
    model: str = ClaudeModel.haiku_4_5
    auth: AuthConfig = Field(default_factory=OAuth2CliAuth)

    # Provider-specific configs (only relevant when name matches)
    gemini: GeminiConfig | None = None
    claude: ClaudeConfig | None = None
    openai: OpenAIConfig | None = None

    @model_validator(mode="after")
    def model_matches_provider(self) -> Self:
        valid: dict[ProviderName, type[StrEnum]] = {
            ProviderName.claude: ClaudeModel,
            ProviderName.openai: OpenAIModel,
            ProviderName.codex: CodexModel,
            ProviderName.gemini: GeminiModel,
        }
        allowed = set(valid[self.name])
        if self.model not in allowed:
            raise ValueError(
                f"Model {self.model!r} is not valid for provider {self.name!r}. "
                f"Valid: {sorted(allowed)}"
            )
        return self

    @model_validator(mode="after")
    def validate_provider_config(self) -> Self:
        """Validate provider-specific configs match the selected provider."""
        if self.gemini is not None and self.name != ProviderName.gemini:
            raise ValueError(
                f"gemini config only valid when name='gemini', got {self.name!r}"
            )

        if self.claude is not None and self.name != ProviderName.claude:
            raise ValueError(
                f"claude config only valid when name='claude', got {self.name!r}"
            )

        if self.openai is not None and self.name != ProviderName.openai:
            raise ValueError(
                f"openai config only valid when name='openai', got {self.name!r}"
            )

        # Codex check must precede the ADC check below — codex+ADC should
        # fail with the codex-specific message, not the gemini-only message.
        if self.name == ProviderName.codex and self.auth.kind != "oauth2_cli":
            raise ValueError(
                f"codex requires oauth2_cli auth (got {self.auth.kind!r}). "
                "Run: codex login --device-auth"
            )

        # ADC auth requires Gemini + project_id
        if self.auth.kind == "oauth2_adc":
            if self.name != ProviderName.gemini:
                raise ValueError(f"oauth2_adc only valid for gemini, got {self.name!r}")
            if self.gemini is None or self.gemini.project_id is None:
                raise ValueError("oauth2_adc requires gemini.project_id to be set")

        return self

    def is_claude(self) -> bool:
        return self.name == ProviderName.claude

    def is_openai(self) -> bool:
        return self.name == ProviderName.openai

    def is_gemini(self) -> bool:
        return self.name == ProviderName.gemini

    def is_codex(self) -> bool:
        return self.name == ProviderName.codex
