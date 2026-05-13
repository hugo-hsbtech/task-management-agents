"""Provider and model configuration."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, SecretStr, model_validator


class ClaudeModel(StrEnum):
    opus_1M = "claude-opus[1m]"
    opus_4_7 = "claude-opus-4-7"
    opus_4_6 = "claude-opus-4-6"
    opus_4_5 = "claude-opus-4-5"
    sonnet_1M = "claude-sonnet[1M]"
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


class ProviderName(StrEnum):
    claude = "claude"
    openai = "openai"
    gemini = "gemini"


# ============================================================================
# Auth Configurations (discriminated union)
# ============================================================================


class ApiKeyAuth(BaseModel):
    """API key authentication for providers that support it."""

    kind: Literal["api_key"] = "api_key"
    key: SecretStr  # Loaded from env or explicit config


class OAuth2CliAuth(BaseModel):
    """OAuth2 token from CLI-managed file or environment variable."""

    kind: Literal["oauth2_cli"] = "oauth2_cli"
    env_var: str | None = None
    token_path: Path | None = None

    @model_validator(mode="after")
    def at_least_one_source(self) -> "OAuth2CliAuth":
        if self.env_var is None and self.token_path is None:
            raise ValueError("OAuth2CliAuth: must provide env_var or token_path")
        return self


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
        # Claude with OAuth2 CLI
        ProviderSettings(
            name=ProviderName.claude,
            model="claude-opus-4-5",
            auth=OAuth2CliAuth(env_var="CLAUDE_CODE_OAUTH_TOKEN"),
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
    auth: AuthConfig = Field(
        default_factory=lambda: OAuth2CliAuth(env_var="CLAUDE_CODE_OAUTH_TOKEN")
    )

    # Provider-specific configs (only relevant when name matches)
    gemini: GeminiConfig | None = None
    claude: ClaudeConfig | None = None
    openai: OpenAIConfig | None = None

    @model_validator(mode="after")
    def model_matches_provider(self) -> Self:
        valid: dict[ProviderName, type[StrEnum]] = {
            ProviderName.claude: ClaudeModel,
            ProviderName.openai: OpenAIModel,
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
