"""Pydantic schemas for Linear API entities.

These are our own types that abstract away the underlying linear-api library.
Consumers should only import from this module, not from linear_api directly.

Mapping rules (verified against linear_api>=0.3 domain models):

* Priority is mapped by enum NAME, not numeric value. linear_api.LinearPriority
  uses URGENT=0..NONE=4 (inverted from Linear's public REST/GraphQL scheme),
  while our Priority follows the public scheme (NO_PRIORITY=0..URGENT=4). We
  must never compare or pass raw integer values across the boundary.
* LinearIssue.priority and .team are required on the source model.
  LinearIssue.project, .description, .identifier, .parentId, .createdAt,
  .updatedAt are optional and use camelCase attribute names.
* LinearProject does NOT expose teamId/team_id; .teams is a property that
  performs network I/O. Conversion never touches it. Pass team_id explicitly
  if known (e.g. from list_projects(team_id=...)).
* LinearProject exposes status: ProjectStatus (with .type: ProjectStatusType),
  not a flat .state string.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Self

from linear_api import LinearPriority, LinearTeam
from linear_api.domain import (
    Comment as LinearComment,
)
from linear_api.domain import (
    IssueRelation as LinearIssueRelation,
)
from linear_api.domain import (
    LinearLabel,
    LinearProject,
    LinearUser,
)
from linear_api.domain import (
    ProjectStatus as LinearProjectStatus,
)
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


def _map_priority_from_api(value: Any) -> int:
    """Map a linear-api priority (Enum or int) to our Priority int value.

    linear-api's LinearPriority is a plain Enum (NOT IntEnum) with
    URGENT=0, HIGH=1, MEDIUM=2, LOW=3, NONE=4 — the inverse ordering of
    our Priority (NO_PRIORITY=0, LOW=1, MEDIUM=2, HIGH=3, URGENT=4).

    Both `int(enum)` (fails on plain Enum) and `.value` (semantically wrong
    because of the inverse ordering) are unsafe; we map by name. Dicts from
    GraphQL responses carry the raw int — we invert that too.
    """
    if value is None:
        return int(Priority.MEDIUM)

    # Normalize to Linear's int value, however the value was carried.
    if isinstance(value, Enum):
        linear_value = value.value
    else:
        try:
            linear_value = int(value)
        except (TypeError, ValueError):
            return int(Priority.MEDIUM)

    linear_to_ours = {
        0: Priority.URGENT,
        1: Priority.HIGH,
        2: Priority.MEDIUM,
        3: Priority.LOW,
        4: Priority.NO_PRIORITY,
    }
    return int(linear_to_ours.get(linear_value, Priority.MEDIUM))


class Priority(int, Enum):
    """Wrapper priority levels (Linear public-API numeric scheme)."""

    NO_PRIORITY = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


# Bidirectional name maps between our Priority and linear_api.LinearPriority.
_OUR_BY_LINEAR_NAME: dict[str, Priority] = {
    "URGENT": Priority.URGENT,
    "HIGH": Priority.HIGH,
    "MEDIUM": Priority.MEDIUM,
    "LOW": Priority.LOW,
    "NONE": Priority.NO_PRIORITY,
}

_LINEAR_NAME_BY_OURS: dict[Priority, str] = {
    Priority.URGENT: "URGENT",
    Priority.HIGH: "HIGH",
    Priority.MEDIUM: "MEDIUM",
    Priority.LOW: "LOW",
    Priority.NO_PRIORITY: "NONE",
}


def _coerce_iso(value: Any) -> str | None:
    """Coerce a datetime/str/None into an ISO-formatted string or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class IssueState(BaseModel):
    """Linear issue state representation (maps from WorkflowState)."""

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
        return cls(
            id=linear_team.id,
            name=linear_team.name,
            key=linear_team.key,
            description=linear_team.description,
        )


class Project(BaseModel):
    """Linear project representation.

    `team_id` is NOT populated automatically. linear_api.LinearProject has no
    teamId field, and accessing `.teams` would issue a network call. Callers
    that already know the team (e.g. list_projects(team_id=...)) should pass
    `team_id` explicitly to `from_linear`.
    """

    id: str
    name: str
    description: str | None = None
    team: Team | None = None
    state: str | None = None  # ProjectStatusType value
    url: str | None = None

    model_config = {"frozen": True}

    @classmethod
    def from_linear(cls, linear_project: LinearProject) -> Self:
        # status is a required ProjectStatus on LinearProject; .type is a
        # ProjectStatusType (StrEnum). Be defensive against partial payloads.
        status: LinearProjectStatus | None = getattr(linear_project, "status", None)
        status_value: str | None = str(status.type) if status else None

        try:
            linear_teams = linear_project.teams or []
        except Exception:
            linear_teams = []
        team = None
        if linear_teams and isinstance(linear_teams, list):
            try:
                team = Team.from_linear(linear_team=linear_teams[0])
            except Exception:
                team = None

        return cls(
            id=linear_project.id,
            name=linear_project.name,
            description=linear_project.description,
            team=team,
            state=status_value,
            url=linear_project.url,
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
            priority=_map_priority_from_api(_field(linear_issue, "priority")),
            team_id=_field(linear_issue, "team_id", "teamId"),
            project_id=_field(linear_issue, "project_id", "projectId"),
            parent_id=_field(linear_issue, "parent_id", "parentId"),
            url=_field(linear_issue, "url"),
            created_at=_coerce_iso(_field(linear_issue, "created_at", "createdAt")),
            updated_at=_coerce_iso(_field(linear_issue, "updated_at", "updatedAt")),
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
    """Input for updating a Linear issue.

    `parent_id` re-parents the issue under a different parent (making it a
    sub-issue). Consistent with the other update fields, leaving it as the
    default (`None`/unset) means "no change". Detaching an issue from its
    parent is not currently supported through this input.
    """

    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    state: str | None = None
    priority: int | None = None
    parent_id: str | None = Field(alias="parentId", default=None)

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
        # color is required on LinearLabel; description is optional.
        return cls(
            id=linear_label.id,
            name=linear_label.name,
            color=getattr(linear_label, "color", None),
            description=getattr(linear_label, "description", None),
        )


class RelatedIssueRef(BaseModel):
    """Minimal issue reference embedded inside an IssueRelation."""

    id: str
    title: str | None = None

    model_config = {"frozen": True}


class IssueRelation(BaseModel):
    """Linear issue relation (blocks / duplicate / related).

    Mirrors the shape returned by linear_api.IssueRelation. Relations are
    directional: `related_issue` is the *target* of the relation from the
    perspective of the issue the relation was fetched for.
    """

    id: str
    type: str  # 'blocks' | 'duplicate' | 'related'
    related_issue: RelatedIssueRef | None = Field(alias="relatedIssue", default=None)
    created_at: str | None = Field(alias="createdAt", default=None)

    model_config = {"frozen": True, "populate_by_name": True}

    @classmethod
    def from_linear(cls, linear_relation: LinearIssueRelation) -> Self:
        """Convert a linear_api IssueRelation to our IssueRelation.

        `relatedIssue` arrives as a raw dict ({"id", "title"}) per the
        linear_api domain model — flatten it into a typed RelatedIssueRef.
        """
        related = getattr(linear_relation, "relatedIssue", None)
        related_ref: RelatedIssueRef | None = None
        if isinstance(related, dict) and related.get("id"):
            related_ref = RelatedIssueRef(
                id=related["id"],
                title=related.get("title"),
            )
        return cls(
            id=linear_relation.id,
            type=linear_relation.type,
            relatedIssue=related_ref,
            createdAt=_coerce_iso(getattr(linear_relation, "createdAt", None)),
        )


class CommentUser(BaseModel):
    """Minimal user representation within a comment."""

    id: str | None = None
    name: str | None = None
    displayName: str | None = None
    email: str | None = None

    model_config = {"frozen": True}

    @classmethod
    def from_linear(cls, linear_user: LinearUser) -> Self:
        return cls(
            id=linear_user.id,
            name=linear_user.name,
            displayName=linear_user.displayName,
            email=linear_user.email,
        )


class Comment(BaseModel):
    """Linear comment representation."""

    id: str
    body: str
    user: CommentUser | None = (
        None  # populated only on create (raw GraphQL); None when listed via linear_api
    )
    created_at: str | None = Field(alias="createdAt", default=None)

    model_config = {"frozen": True}

    @classmethod
    def from_linear(cls, linear_comment: LinearComment) -> Self:
        # LinearComment.createdAt is a required datetime.
        return cls(
            id=linear_comment.id,
            body=linear_comment.body,
            createdAt=_coerce_iso(getattr(linear_comment, "createdAt", None)),
        )


class CommentInput(BaseModel):
    """Input for creating a comment on a Linear issue."""

    issue_id: str = Field(alias="issueId")
    body: str = Field(min_length=1)

    model_config = {"populate_by_name": True}


class ProjectCommentInput(BaseModel):
    """Input for creating a comment on a Linear project."""

    project_id: str
    body: str = Field(min_length=1)

    model_config = {"populate_by_name": True}


class IssueLabelInput(BaseModel):
    """Input for adding a label to an issue."""

    issue_id: str = Field(alias="issueId")
    label_name: str = Field(alias="labelName")

    model_config = {"populate_by_name": True}


class ProjectUpdateInput(BaseModel):
    """Input for updating a Linear project."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    state: str | None = None  # planned, started, paused, completed, canceled
    # For posting project updates (progress reports)
    update_message: str | None = Field(alias="updateMessage", default=None)

    model_config = {"populate_by_name": True}


def _map_priority_to_api(priority: int | str | None) -> Any:
    """Map our priority (int or string label) to a linear_api LinearPriority.

    Maps by NAME, not numeric value, because the two enums have inverted
    underlying values.
    """
    if priority is None:
        return None

    if isinstance(priority, int):
        try:
            ours = Priority(priority)
        except ValueError:
            return LinearPriority.MEDIUM
        return LinearPriority[_LINEAR_NAME_BY_OURS[ours]]

    aliases = {
        "low": "LOW",
        "medium": "MEDIUM",
        "high": "HIGH",
        "urgent": "URGENT",
        "no_priority": "NONE",
        "no priority": "NONE",
        "none": "NONE",
    }
    return LinearPriority[aliases.get(str(priority).lower(), "MEDIUM")]
