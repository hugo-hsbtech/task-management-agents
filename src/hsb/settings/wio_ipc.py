"""File paths for the WIO subprocess IPC handshake.

Set by Main Orchestrator before invoking the WIO subprocess; read by WIO
at startup. Env vars: HSB_WIO_INPUT_FILE, HSB_WIO_OUTPUT_FILE.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class WIOIPCSettings(BaseSettings):
    """Subprocess IPC paths written by main_orchestrator, read by WIO."""

    model_config = SettingsConfigDict(env_prefix="HSB_WIO_")

    input_file: Path | None = None
    output_file: Path | None = None
