from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ClaimResult(BaseModel):
    """Internal result of a single claiming attempt (D-04 optimistic lock)."""

    model_config = {"extra": "forbid"}

    work_item_id: str
    claimed: bool
    pre_updated_at: str
    post_updated_at: str


class DispatchedItem(BaseModel):
    """Record of a single dispatched work item within a cycle."""

    model_config = {"extra": "forbid"}

    work_item_id: str
    orchestrator_instance: str
    claim_status: Literal["claimed", "skipped"]
    final_status: Literal["completed", "failed", "blocked", "exception"]


class MainOrchestratorOutput(BaseModel):
    """
    Output contract for the Main Orchestrator cycle.
    Mirrors AGENT-CONTRACTS.md §0 Output exactly (MORD-05 format).
    """

    model_config = {"extra": "forbid"}

    mode: Literal["cascade", "parallel"]
    dispatched: list[DispatchedItem] = Field(default_factory=list)
    cycle_summary: str
