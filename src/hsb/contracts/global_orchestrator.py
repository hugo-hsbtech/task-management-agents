from __future__ import annotations
from pydantic import BaseModel, Field


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
    """
    model_config = {"extra": "forbid"}

    ready_tasks: list[ReadyTask]
    is_backlog_empty: bool
    is_epic_ready: bool
