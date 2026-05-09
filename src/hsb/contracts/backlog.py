"""Pydantic contracts for the Backlog Agent — mirrors agents/AGENT-CONTRACTS.md §1.

BKPK-01: BacklogInput.plan_source is required (no default; raises ValidationError if absent — D-02).
BKPK-05: BacklogOutput.traceability is required so every backlog can be traced back to plan.md.

All models declare model_config = {"extra": "forbid"} to prevent silent schema drift
(Pitfall 4 of 02-RESEARCH.md).
"""

from __future__ import annotations

from typing import Optional  # noqa: F401  (kept for forward-compat with future fields)

from pydantic import BaseModel, Field


class ProjectContext(BaseModel):
    """Project metadata embedded in BacklogInput."""

    name: str
    repository: str
    technical_stack: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class BacklogInput(BaseModel):
    """Input contract for the Backlog Planning Agent.

    Mirrors AGENT-CONTRACTS.md §1 Input exactly.
    plan_source is user-specified at runtime via --plan <path> per D-02.
    FAIL if absent — no default value (BKPK-01).
    """

    plan_source: str  # absolute path to plan.md (no default)
    project_context: ProjectContext

    model_config = {"extra": "forbid"}


class TaskItem(BaseModel):
    """A Task — leaf-level work item under a User Story or directly under an EPIC."""

    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class UserStory(BaseModel):
    """A User Story — child of an EPIC."""

    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    tasks: list[TaskItem] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class EpicItem(BaseModel):
    """An EPIC — top-level deliverable feature.

    Per skills/01-BACKLOG-PLANNING.md, EPIC titles MUST start with '[EPIC] '.
    Enforcement happens in the BACKLOG_SYSTEM_PROMPT — not as a Pydantic regex —
    because LLM-generated titles vary and a regex on the model would block valid
    recovery output during retry.
    """

    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    user_stories: list[UserStory] = Field(default_factory=list)
    tasks: list[TaskItem] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class BacklogTraceability(BaseModel):
    """Traceability metadata mapping the backlog back to its source plan (BKPK-05)."""

    plan_source: str

    model_config = {"extra": "forbid"}


class BacklogOutput(BaseModel):
    """Output contract for the Backlog Planning Agent.

    Mirrors AGENT-CONTRACTS.md §1 Output exactly.
    epics has min_length=1 — agent must produce at least one EPIC.
    """

    epics: list[EpicItem] = Field(min_length=1)
    traceability: BacklogTraceability

    model_config = {"extra": "forbid"}
