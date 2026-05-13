"""Contracts for turning a product plan into platform-specific backlog work."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from backlog.platforms import LinearPlatform, SupportedPlatform


class BacklogInput(BaseModel):
    """Input contract for backlog generation from a plan."""

    plan_content: str = Field(min_length=1)
    stacks: list[str] = Field(default_factory=list)
    platform: SupportedPlatform
    context: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class IssueType(StrEnum):
    """Backlog issue roles produced from a plan."""

    epic = "epic"
    user_story = "user_story"
    task = "task"


class IssueAction(StrEnum):
    """Write intent for a generated backlog issue."""

    create = "create"
    update = "update"


class IssueRelationType(StrEnum):
    """Directional relation between two backlog issues."""

    blocks = "blocks"
    blocked_by = "blocked_by"
    relates_to = "relates_to"
    duplicate_of = "duplicate_of"


class IssueRelation(BaseModel):
    """A directed relation from this issue to another issue."""

    type: IssueRelationType
    target_title: str = Field(min_length=1)

    model_config = {"extra": "forbid"}


class IssueFields(BaseModel):
    """Common fields accepted by backlog issue tooling."""

    title: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1)
    priority: int = Field(default=2, ge=0, le=4)
    parent_id: str | None = Field(
        default=None,
        description=(
            "Plan-local temp id of the parent issue (matches IssuePlan.id of "
            "another issue in the same BacklogOutput). Resolved to a real "
            "platform issue id at execution time."
        ),
    )
    labels: list[str] = Field(default_factory=list)
    platform_fields: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class IssuePlan(BaseModel):
    """One write-ready backlog issue."""

    id: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Plan-local temp id (e.g. '1', '2'). Required by the prompt for "
            "referential integrity; other issues reference it via parent_id "
            "and depends_on. Optional here so callers building outputs "
            "programmatically aren't forced to assign one."
        ),
    )
    action: IssueAction = IssueAction.create
    issue_type: IssueType
    fields: IssueFields
    depends_on: list[str] = Field(
        default_factory=list,
        description=(
            "Plan-local temp ids of issues this one depends on. Informational "
            "for the LLM; formal blocking relationships must use relations."
        ),
    )
    relations: list[IssueRelation] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class BacklogOutput(BaseModel):
    """Output contract for platform-specific backlog work."""

    platform: SupportedPlatform
    issues: list[IssuePlan] = Field(min_length=1)

    model_config = {"extra": "forbid"}

    def is_linear(self) -> bool:
        return isinstance(self.platform, LinearPlatform)
