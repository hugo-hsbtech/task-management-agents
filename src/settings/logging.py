"""Logging configuration knobs.

Env vars: HSB_LOG_LEVEL, HSB_LOG_JSON.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingSettings(BaseSettings):
    """Process-wide logging toggles consumed by ``libs.logging.configure``."""

    model_config = SettingsConfigDict(env_prefix="HSB_LOG_")

    level: str = Field(default="INFO")
    # `json_output` avoids shadowing BaseSettings.json. Env: HSB_LOG_JSON_OUTPUT.
    json_output: bool = Field(default=False)
