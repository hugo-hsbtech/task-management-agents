"""Pydantic schemas for Linear API entities.

These are our own types that abstract away the underlying linear-api library.
Consumers should only import from this module, not from linear_api directly.
"""

from enum import Enum
from typing import Any, Self

from linear_api import LinearTeam
from linear_api.domain import LinearIssue, LinearLabel, LinearProject
from pydantic import BaseModel, Field


class Priority(int, Enum):
    """Linear priority levels."""

    NO_PRIORITY = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class IssueState(BaseModel):
    """Linear issue state representation."""

    id: str
    name: str
    color: str | None = None
    type: str | None = None  # backlog, unstarted, started, completed, canceled

    model_config = {"frozen": True}

    @classmethod
    def from_linear(cls, linear_state: Any) -> Self:
        """Create an IssueState from a linear-api State object."""
        return cls(
            id=linear_state.id,
            name=linear_state.name,
            color=getattr(linear_state, "color", None),
            type=getattr(linear_state, "type", None),
        )


class Team(BaseModel):
    """Linear team representation."""

    id: str
    name: str
    key: str  # Team identifier prefix (e.g., "ENG", "PROD")
    description: str | None = None

    model_config = {"frozen": True}

    @classmethod
    def from_linear(cls, linear_team: LinearTeam) -> Self:
        """Create a Team from a linear-api Team object."""
        return cls(
            id=linear_team.id,
            name=linear_team.name,
            key=linear_team.key,
            description=linear_team.description,
        )


class Project(BaseModel):
    """Linear project representation."""

    id: str
    name: str
    description: str | None = None
    team_id: str = Field(alias="teamId")
    state: str | None = None  # planned, started, paused, completed, canceled

    model_config = {"frozen": True}

    @classmethod
    def from_linear(cls, linear_project: LinearProject) -> Self:
        """Create a Project from a linear-api Project object."""
        return cls(
            id=linear_project.id,
            name=linear_project.name,
            description=getattr(linear_project, "description", None),
            teamId=getattr(linear_project, "team_id", ""),
            state=getattr(linear_project, "state", None),
        )


class Issue(BaseModel):
    """Linear issue representation."""

    id: str
    identifier: str  # Human-readable ID like "ENG-123"
    title: str
    description: str | None = None
    state: IssueState | None = None
    priority: int = Priority.MEDIUM
    team_id: str | None = Field(alias="teamId", default=None)
    project_id: str | None = Field(alias="projectId", default=None)
    parent_id: str | None = Field(alias="parentId", default=None)
    url: str | None = None
    created_at: str | None = Field(alias="createdAt", default=None)
    updated_at: str | None = Field(alias="updatedAt", default=None)

    model_config = {"frozen": True}

    @classmethod
    def from_linear(cls, linear_issue: LinearIssue) -> Self:
        """Create an Issue from a linear-api Issue object."""
        return cls(
            id=linear_issue.id,
            identifier=linear_issue.identifier,
            title=linear_issue.title,
            description=linear_issue.description,
            state=IssueState.from_linear(linear_issue.state)
            if linear_issue.state
            else None,
            priority=getattr(linear_issue, "priority", Priority.MEDIUM),
            teamId=getattr(linear_issue, "team_id", None),
            projectId=getattr(linear_issue, "project_id", None),
            parentId=getattr(linear_issue, "parent_id", None),
            url=linear_issue.url,
            createdAt=getattr(linear_issue, "created_at", None),
            updatedAt=getattr(linear_issue, "updated_at", None),
        )


class IssueInput(BaseModel):
    """Input for creating a Linear issue."""

    title: str = Field(min_length=1, max_length=256)
    description: str | None = None
    team_id: str = Field(alias="teamId")  # Required
    project_id: str = Field(alias="projectId")  # Required per requirements
    priority: int = Priority.MEDIUM
    parent_id: str | None = Field(alias="parentId", default=None)

    model_config = {"populate_by_name": True}


class IssueUpdateInput(BaseModel):
    """Input for updating a Linear issue."""

    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    state: str | None = None
    priority: int | None = None

    model_config = {"populate_by_name": True}


class Label(BaseModel):
    """Linear label representation."""

    id: str
    name: str
    color: str | None = None
    description: str | None = None

    model_config = {"frozen": True}

    @classmethod
    def from_linear(cls, linear_label: LinearLabel) -> Self:
        """Create a Label from a linear-api Label object."""
        return cls(
            id=linear_label.id,
            name=linear_label.name,
            color=getattr(linear_label, "color", None),
            description=getattr(linear_label, "description", None),
        )


class IssueLabelInput(BaseModel):
    """Input for adding a label to an issue."""

    issue_id: str = Field(alias="issueId")
    label_name: str = Field(alias="labelName")  # Linear creates label if not exists

    model_config = {"populate_by_name": True}


class ProjectUpdateInput(BaseModel):
    """Input for updating a Linear project."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    state: str | None = None  # planned, started, paused, completed, canceled
    # For posting project updates (progress reports)
    update_message: str | None = Field(alias="updateMessage", default=None)

    model_config = {"populate_by_name": True}


# -----------------------------------------------------------------------------
# Helper functions for converting collections
# -----------------------------------------------------------------------------


def _map_priority_to_api(priority: int | str | None) -> Any:
    """Map our priority to linear_api LinearPriority enum."""
    from linear_api import LinearPriority

    if priority is None:
        return None

    mapping = {
        0: LinearPriority.NONE,
        1: LinearPriority.LOW,
        2: LinearPriority.MEDIUM,
        3: LinearPriority.HIGH,
        4: LinearPriority.URGENT,
    }

    if isinstance(priority, int):
        return mapping.get(priority, LinearPriority.MEDIUM)

    priority_map = {
        "low": LinearPriority.LOW,
        "medium": LinearPriority.MEDIUM,
        "high": LinearPriority.HIGH,
        "urgent": LinearPriority.URGENT,
        "no_priority": LinearPriority.NONE,
        "no priority": LinearPriority.NONE,
        "none": LinearPriority.NONE,
    }
    return priority_map.get(str(priority).lower(), LinearPriority.MEDIUM)
