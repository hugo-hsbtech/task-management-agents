"""Pydantic contracts for the Git Agent — mirrors agents/AGENT-CONTRACTS.md §5.

GITA-05 schema-level guard: extra='forbid' on every model. If the agent emits
merged_to_main / linear_status fields the validator rejects.

D-07: base_pr in ExistingPRContext is ALWAYS None in Phase 2 — kept only for
forward-compat with Phase 4+ chained-base support.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class ExistingPRContext(BaseModel):
    epic_pr: Optional[str] = None
    base_pr: Optional[str] = None  # NOT used in Phase 2 per D-07
    model_config = {"extra": "forbid"}


class GitInput(BaseModel):
    """Input contract for the Git Agent. Mirrors AGENT-CONTRACTS.md §5 Input."""
    work_item_id: str
    implementation_output: dict  # serialized BuilderOutput.model_dump()
    epic_id: str
    dependencies: list[str] = Field(default_factory=list)
    existing_pr_context: ExistingPRContext = Field(default_factory=ExistingPRContext)
    model_config = {"extra": "forbid"}


class PullRequest(BaseModel):
    """A GitHub PR. Title MUST match `[LIN-{id}] {description}` (GITA-03; integration test regex)."""
    url: str
    title: str
    base: str
    head: str
    model_config = {"extra": "forbid"}


class GitOutput(BaseModel):
    """Output contract. Branch MUST match `feature/LIN-{id}-{slug}` (GITA-01).
    Git MUST NOT include Linear update fields or code change fields (GITA-05)."""
    work_item_id: str
    branch: str
    commits: list[str] = Field(default_factory=list)
    pull_request: PullRequest
    model_config = {"extra": "forbid"}
