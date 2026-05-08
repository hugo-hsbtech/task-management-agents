from __future__ import annotations

from pydantic import BaseModel, Field

from hsb.contracts.risk import AutoImprovementTrigger


class ReadyTask(BaseModel):
    """A single ready work item returned by the Global Orchestrator."""

    model_config = {"extra": "forbid"}

    id: str
    title: str
    priority: int = 999
    dependencies: list[str] = Field(default_factory=list)


class GlobalOrchestratorOutput(BaseModel):
    """
    Output contract for the Global Orchestrator.
    Mirrors AGENT-CONTRACTS.md §0 + CONTEXT.md D-03 exactly.

    Phase 5 extension (additive): two optional fields surface UAT activity
    and improvement-trigger candidates for operator review. Per-cycle path
    leaves ``improvement_triggers`` empty (RISK-04 + D-09 require explicit
    operator delegation before any Linear write); a future CLI surfacer
    populates the field.
    """

    model_config = {"extra": "forbid"}

    ready_tasks: list[ReadyTask]
    is_backlog_empty: bool
    is_epic_ready: bool
    uat_dispatched: list[str] = Field(default_factory=list)
    improvement_triggers: list[AutoImprovementTrigger] = Field(default_factory=list)
