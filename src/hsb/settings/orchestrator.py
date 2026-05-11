"""Operational tuning knobs read by Main Orchestrator and Docker Compose
scaffolding.

Env vars: HSB_CLAIM_DELAY_MS, HSB_PROJECT.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorSettings(BaseSettings):
    """HSB_CLAIM_DELAY_MS (claim debounce, ms) and HSB_PROJECT (Docker Compose project scope)."""

    model_config = SettingsConfigDict(env_prefix="HSB_")

    claim_delay_ms: int = Field(default=200, ge=0)
    project: str = "task-management-agents"
