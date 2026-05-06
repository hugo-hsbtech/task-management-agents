"""Pydantic contracts for the Builder Agent — mirrors agents/AGENT-CONTRACTS.md §4.

BLDR-03: BuilderOutput validates a complete implementation contract.
BLDR-04: extra='forbid' on every model — Builder cannot leak git_branch / pr_url /
         linear_status fields. The agent's allowed_tools list is the primary defense;
         this schema-level guard is the second.

Pitfall 6: BuilderInput must be constructed with FRESH Linear state — never cached.
The CLI in src/hsb/cli/builder.py enforces this; the model itself cannot.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class RepositoryContext(BaseModel):
    """Repo context — root_path is required so the agent's cwd is unambiguous."""
    root_path: str
    technical_stack: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class BuilderInput(BaseModel):
    """Input contract for the Builder Agent.

    Mirrors AGENT-CONTRACTS.md §4 Input exactly.
    ALWAYS fetch fresh Linear state immediately before constructing BuilderInput
    (Pitfall 6). Never pass a cached linear_issue / issue_description.
    """
    work_item_id: str
    issue_description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    epic_context: dict = Field(default_factory=dict)
    plan_source: str
    repository_context: RepositoryContext
    knowledge_context: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class FileChanged(BaseModel):
    """A single file changed by the Builder Agent — path + summary of change."""
    path: str
    change_summary: str

    model_config = {"extra": "forbid"}


class ValidationResults(BaseModel):
    """Per-validation status. 'not_run' is the safe default when a tool is absent."""
    build: Literal["passed", "failed", "not_run"]
    tests: Literal["passed", "failed", "not_run"]
    lint: Literal["passed", "failed", "not_run"]
    typecheck: Literal["passed", "failed", "not_run"]

    model_config = {"extra": "forbid"}


class ImplementationNotes(BaseModel):
    """Free-form notes from the Builder for QA + downstream agents."""
    decisions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    qa_notes: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class BuilderOutput(BaseModel):
    """Output contract for the Builder Agent.

    Mirrors AGENT-CONTRACTS.md §4 Output exactly.
    Builder MUST NOT include git commits, branch names, or Linear updates here (BLDR-04).
    If those fields appear, model_config={'extra':'forbid'} rejects the output and the
    retry loop in builder_agent.py forces the agent to correct itself.
    """
    work_item_id: str
    implementation_status: Literal["completed", "blocked", "failed"]
    summary: str
    files_changed: list[FileChanged] = Field(default_factory=list)
    validation: ValidationResults
    implementation_notes: ImplementationNotes

    model_config = {"extra": "forbid"}
