"""Provider credentials sourced from env vars.

These three env vars (``CLAUDE_CODE_OAUTH_TOKEN``, ``ANTHROPIC_API_KEY``,
``OPENAI_API_KEY``) are read independently of agent-runtime settings so
that constructing one doesn't validate the other. The G1 policy in
:mod:`settings.runtime` separately governs whether API-key kinds are
allowed at agent dispatch time.
"""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class CredentialsSettings(BaseSettings):
    """Vendor credential env vars consumed by the auth factory."""

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
