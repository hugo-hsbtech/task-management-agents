"""Pydantic schemas for Linear API entities.

These are our own types that abstract away the underlying linear-api library.
Consumers should only import from this module, not from linear_api directly.
"""

from enum import Enum
from typing import Any, Self

from linear_api import LinearTeam
from linear_api.domain import LinearLabel, LinearProject
from pydantic import BaseModel, Field

_MISSING = object()


def _field(source: Any, *names: str, default: Any = None) -> Any:
    """Read the first available field from a linear-api model or a raw dict.

    linear-api inconsistently returns parsed model instances (snake_case
    attributes) or raw GraphQL dicts (camelCase keys) depending on the
    call path — notably, projects.get_issues() returns dicts. Callers
    pass every plausible name; this helper picks the first that exists.
    """
    for name in names:
        if isinstance(source, dict):
            if name in source:
                return source[name]
        else:
            value = getattr(source, name, _MISSING)
            if value is not _MISSING:
                return value
    return default


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
        """Create an IssueState from a linear-api State object or a raw dict."""
        return cls(
            id=_field(linear_state, "id"),
            name=_field(linear_state, "name"),
            color=_field(linear_state, "color"),
            type=_field(linear_state, "type"),
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
    # Human-readable ID like "ENG-123". Optional because projects.get_issues()
    # in linear-api returns a GraphQL projection that omits this field.
    identifier: str | None = None
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

    model_config = {"frozen": True, "populate_by_name": True}

    @classmethod
    def from_linear(cls, linear_issue: Any) -> Self:
        """Create an Issue from a linear-api Issue object or a raw GraphQL dict.

        linear-api's projects.get_issues() returns raw dicts; issues.get()
        returns LinearIssue model instances. We accept both shapes.
        """
        state = _field(linear_issue, "state")
        return cls(
            id=_field(linear_issue, "id"),
            identifier=_field(linear_issue, "identifier"),
            title=_field(linear_issue, "title"),
            description=_field(linear_issue, "description"),
            state=IssueState.from_linear(state) if state else None,
            priority=_field(linear_issue, "priority", default=Priority.MEDIUM),
            team_id=_field(linear_issue, "team_id", "teamId"),
            project_id=_field(linear_issue, "project_id", "projectId"),
            parent_id=_field(linear_issue, "parent_id", "parentId"),
            url=_field(linear_issue, "url"),
            created_at=_field(linear_issue, "created_at", "createdAt"),
            updated_at=_field(linear_issue, "updated_at", "updatedAt"),
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
