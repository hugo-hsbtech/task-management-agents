"""Unit tests for libs.linear.schemas.

Tests all Pydantic models and from_linear conversion methods.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from libs.linear.schemas import (
    Issue,
    IssueInput,
    IssueRelation,
    IssueUpdateInput,
    Label,
    Priority,
    Project,
    ProjectUpdateInput,
    RelatedIssueRef,
    Team,
    _map_priority_to_api,
)

# -----------------------------------------------------------------------------
# Priority Enum Tests
# -----------------------------------------------------------------------------


def test_priority_enum_values() -> None:
    """Priority enum should have correct integer values."""
    assert Priority.NO_PRIORITY == 0
    assert Priority.LOW == 1
    assert Priority.MEDIUM == 2
    assert Priority.HIGH == 3
    assert Priority.URGENT == 4


# -----------------------------------------------------------------------------
# Team Model Tests
# -----------------------------------------------------------------------------


def test_team_creation() -> None:
    """Team model should be created with required fields."""
    team = Team(id="team-123", name="Engineering", key="ENG")
    assert team.id == "team-123"
    assert team.name == "Engineering"
    assert team.key == "ENG"
    assert team.description is None


def test_team_with_description() -> None:
    """Team model should accept optional description."""
    team = Team(
        id="team-123", name="Engineering", key="ENG", description="Core dev team"
    )
    assert team.description == "Core dev team"


def test_team_frozen() -> None:
    """Team model should be immutable (frozen)."""
    team = Team(id="team-123", name="Engineering", key="ENG")
    with pytest.raises(ValidationError):
        team.name = "New Name"


def test_team_from_linear() -> None:
    """Team.from_linear should convert linear_api Team object."""

    # Mock linear_api Team object
    class MockLinearTeam:
        id = "team-456"
        name = "Product"
        key = "PROD"
        description = "Product team"

    team = Team.from_linear(MockLinearTeam())
    assert team.id == "team-456"
    assert team.name == "Product"
    assert team.key == "PROD"
    assert team.description == "Product team"


def test_team_from_linear_no_description() -> None:
    """Team.from_linear should handle missing description."""

    class MockLinearTeam:
        id = "team-789"
        name = "Design"
        key = "DES"
        description = None  # Explicit None

    team = Team.from_linear(MockLinearTeam())
    assert team.description is None


# -----------------------------------------------------------------------------
# Project Model Tests
# -----------------------------------------------------------------------------


def test_project_creation() -> None:
    """Project model should be created with required fields."""
    project = Project(id="proj-123", name="Sprint 1")
    assert project.id == "proj-123"
    assert project.name == "Sprint 1"
    assert project.team is None
    assert project.state is None
    assert project.description is None


def test_project_with_optional_fields() -> None:
    """Project model should accept optional fields."""
    team = Team(id="team-456", name="Engineering", key="ENG")
    project = Project(
        id="proj-123",
        name="Sprint 1",
        team=team,
        description="Q1 sprint",
        state="started",
    )
    assert project.description == "Q1 sprint"
    assert project.state == "started"
    assert project.team is not None
    assert project.team.id == "team-456"


def test_project_from_linear() -> None:
    """Project.from_linear should convert a linear_api LinearProject.

    State is derived from status.type (a ProjectStatusType StrEnum, where str(t)
    returns its value). team is read from linear_project.teams[0].
    """

    class _StatusType(str):
        value = "completed"

    class MockStatus:
        type = _StatusType("completed")

    class MockTeam:
        id = "team-123"
        name = "Engineering"
        key = "ENG"
        description = None

    class MockLinearProject:
        id = "proj-789"
        name = "Sprint 2"
        description = None
        status = MockStatus()
        url = "https://linear.app/p/proj-789"
        teams = [MockTeam()]

    project = Project.from_linear(MockLinearProject())
    assert project.id == "proj-789"
    assert project.name == "Sprint 2"
    assert project.team is not None
    assert project.team.id == "team-123"
    assert project.state == "completed"
    assert project.url == "https://linear.app/p/proj-789"


def test_project_from_linear_no_state() -> None:
    """Project.from_linear tolerates a missing status and empty teams."""

    class MockLinearProject:
        id = "proj-x"
        name = "X"
        description = None
        url = None
        status = None
        teams: list[object] = []

    project = Project.from_linear(MockLinearProject())
    assert project.state is None
    assert project.team is None


# -----------------------------------------------------------------------------
# Issue Model Tests
# -----------------------------------------------------------------------------


def test_issue_creation() -> None:
    """Issue model should be created with required fields."""
    issue = Issue(
        id="issue-123",
        identifier="ENG-42",
        title="Fix bug",
        url="https://linear.app/issue/ENG-42",
    )
    assert issue.id == "issue-123"
    assert issue.identifier == "ENG-42"
    assert issue.title == "Fix bug"
    assert issue.url == "https://linear.app/issue/ENG-42"
    assert issue.priority == Priority.MEDIUM  # default
    assert issue.state is None


def test_issue_with_all_fields() -> None:
    """Issue model should accept all optional fields."""
    from libs.linear.schemas import IssueState

    state = IssueState(id="state-1", name="In Progress", color="#00f", type="started")
    issue = Issue(
        id="issue-123",
        identifier="ENG-42",
        title="Fix bug",
        description="Detailed description",
        state=state,
        priority=Priority.HIGH,
        teamId="team-456",
        projectId="proj-789",
        parentId="issue-parent",
        url="https://linear.app/issue/ENG-42",
        createdAt="2024-01-01",
        updatedAt="2024-01-02",
    )
    assert issue.description == "Detailed description"
    assert issue.state.name == "In Progress"
    assert issue.priority == 3
    assert issue.team_id == "team-456"
    assert issue.project_id == "proj-789"
    assert issue.parent_id == "issue-parent"
    assert issue.created_at == "2024-01-01"
    assert issue.updated_at == "2024-01-02"


def test_issue_frozen() -> None:
    """Issue model should be immutable."""
    issue = Issue(id="issue-123", identifier="ENG-42", title="Fix bug", url="url")
    with pytest.raises(ValidationError):
        issue.title = "New Title"


def test_issue_from_linear() -> None:
    """Issue.from_linear should convert a linear_api LinearIssue.

    LinearIssue uses camelCase attributes (createdAt, updatedAt, parentId),
    a required LinearTeam, an optional LinearProject, and a LinearPriority
    enum for priority. Datetimes are real datetime instances.
    """
    from datetime import datetime

    class MockState:
        id = "state-review"
        name = "in_review"
        color = "#ff0"
        type = "started"

    class MockTeam:
        id = "team-789"

    class MockProject:
        id = "proj-000"

    class MockLinearIssue:
        id = "issue-456"
        identifier = "PROD-123"
        title = "Feature request"
        description = "Need this feature"
        state = MockState()
        # Linear's int: 4 = NONE (Linear's enum ordering is inverse of ours).
        priority = 4
        # Real LinearIssue: team is a required nested LinearTeam, project is
        # an optional nested LinearProject, parent is flattened to parentId.
        team = MockTeam()
        project = MockProject()
        parentId = "issue-parent"
        url = "https://linear.app/issue/PROD-123"
        createdAt = datetime(2024, 1, 1, 12, 0, 0)
        updatedAt = datetime(2024, 1, 2, 12, 0, 0)

    issue = Issue.from_linear(MockLinearIssue())
    assert issue.id == "issue-456"
    assert issue.identifier == "PROD-123"
    assert issue.title == "Feature request"
    assert issue.state is not None
    assert issue.state.name == "in_review"
    assert issue.state.id == "state-review"
    # Linear NONE (4) maps to our NO_PRIORITY (0).
    assert issue.priority == 0
    assert issue.team_id == "team-789"
    assert issue.project_id == "proj-000"
    assert issue.parent_id == "issue-parent"


def test_issue_from_linear_no_state() -> None:
    """Issue.from_linear handles missing state, team, and project."""
    from linear_api import LinearPriority

    class MockLinearIssue:
        id = "issue-789"
        identifier = "ENG-1"
        title = "Task"
        description = None
        state = None
        priority = LinearPriority.MEDIUM
        team = None
        project = None
        parentId = None
        url = "https://linear.app/issue/ENG-1"
        createdAt = None
        updatedAt = None

    issue = Issue.from_linear(MockLinearIssue())
    assert issue.state is None
    assert issue.team_id is None
    assert issue.project_id is None
    assert issue.created_at is None
    assert issue.updated_at is None


def test_issue_from_linear_maps_priority_by_name() -> None:
    """Issue.from_linear maps every LinearPriority to the Priority of the same name.

    Catches the historical bug where LinearPriority's inverted integer values
    silently produced wrong Priority values.
    """
    from linear_api import LinearPriority

    cases = [
        (LinearPriority.URGENT, Priority.URGENT),
        (LinearPriority.HIGH, Priority.HIGH),
        (LinearPriority.MEDIUM, Priority.MEDIUM),
        (LinearPriority.LOW, Priority.LOW),
        (LinearPriority.NONE, Priority.NO_PRIORITY),
    ]
    for linear_p, expected in cases:

        class _M:
            id = "i"
            identifier = None
            title = "t"
            description = None
            state = None
            priority = linear_p
            team = None
            project = None
            parentId = None
            url = None
            createdAt = None
            updatedAt = None

        assert Issue.from_linear(_M()).priority == expected, (
            f"{linear_p!r} should map to {expected!r}"
        )


# -----------------------------------------------------------------------------
# IssueInput Model Tests
# -----------------------------------------------------------------------------


def test_issue_input_creation() -> None:
    """IssueInput should be created with required fields."""
    input_data = IssueInput(
        title="New Issue",
        teamId="team-123",
        projectId="proj-456",
    )
    assert input_data.title == "New Issue"
    assert input_data.team_id == "team-123"
    assert input_data.project_id == "proj-456"
    assert input_data.priority == Priority.MEDIUM  # default
    assert input_data.description is None
    assert input_data.parent_id is None


def test_issue_input_with_all_fields() -> None:
    """IssueInput should accept all fields."""
    input_data = IssueInput(
        title="New Issue",
        teamId="team-123",
        projectId="proj-456",
        description="Description",
        priority=Priority.HIGH,
        parentId="issue-parent",
    )
    assert input_data.description == "Description"
    assert input_data.priority == 3
    assert input_data.parent_id == "issue-parent"


def test_issue_input_title_required() -> None:
    """IssueInput should require title."""
    with pytest.raises(ValidationError):
        IssueInput(teamId="team-123", projectId="proj-456")  # missing title


def test_issue_input_title_too_long() -> None:
    """IssueInput should validate title max length."""
    with pytest.raises(ValidationError):
        IssueInput(title="x" * 300, teamId="team-123", projectId="proj-456")


def test_issue_input_populate_by_name() -> None:
    """IssueInput should accept both snake_case and camelCase."""
    input1 = IssueInput(title="Test", teamId="team-1", projectId="proj-1")
    input2 = IssueInput(title="Test", team_id="team-1", project_id="proj-1")
    assert input1.team_id == input2.team_id


# -----------------------------------------------------------------------------
# IssueUpdateInput Model Tests
# -----------------------------------------------------------------------------


def test_issue_update_input_empty() -> None:
    """IssueUpdateInput can be empty (partial update)."""
    update = IssueUpdateInput()
    assert update.title is None
    assert update.description is None
    assert update.state is None
    assert update.priority is None
    assert update.parent_id is None


def test_issue_update_input_partial() -> None:
    """IssueUpdateInput can have partial fields."""
    update = IssueUpdateInput(title="New Title", priority=Priority.LOW)
    assert update.title == "New Title"
    assert update.priority == 1


def test_issue_update_input_all_fields() -> None:
    """IssueUpdateInput can have all fields."""
    update = IssueUpdateInput(
        title="New Title",
        description="New Desc",
        state="completed",
        priority=Priority.URGENT,
        parentId="issue-parent",
    )
    assert update.state == "completed"
    assert update.priority == 4
    assert update.parent_id == "issue-parent"


def test_issue_update_input_with_parent_id_snake_case() -> None:
    """IssueUpdateInput accepts parent_id via snake_case."""
    update = IssueUpdateInput(parent_id="issue-parent")
    assert update.parent_id == "issue-parent"


def test_issue_update_input_with_parent_id_camel_alias() -> None:
    """IssueUpdateInput accepts parent_id via the camelCase alias."""
    update = IssueUpdateInput(parentId="issue-parent")
    assert update.parent_id == "issue-parent"


# -----------------------------------------------------------------------------
# Label Model Tests
# -----------------------------------------------------------------------------


def test_label_creation() -> None:
    """Label model should be created with required fields."""
    label = Label(id="label-123", name="bug")
    assert label.id == "label-123"
    assert label.name == "bug"
    assert label.color is None
    assert label.description is None


def test_label_with_optional_fields() -> None:
    """Label model should accept optional fields."""
    label = Label(
        id="label-456",
        name="feature",
        color="#ff0000",
        description="New feature request",
    )
    assert label.color == "#ff0000"
    assert label.description == "New feature request"


def test_label_from_linear() -> None:
    """Label.from_linear should convert linear_api Label object."""

    class MockLinearLabel:
        id = "label-789"
        name = "urgent"
        color = "#ff0000"
        description = "Urgent items"

    label = Label.from_linear(MockLinearLabel())
    assert label.id == "label-789"
    assert label.name == "urgent"
    assert label.color == "#ff0000"


# -----------------------------------------------------------------------------
# ProjectUpdateInput Model Tests
# -----------------------------------------------------------------------------


def test_project_update_input_empty() -> None:
    """ProjectUpdateInput can be empty."""
    update = ProjectUpdateInput()
    assert update.name is None
    assert update.description is None
    assert update.state is None
    assert update.update_message is None


def test_project_update_input_partial() -> None:
    """ProjectUpdateInput can have partial fields."""
    update = ProjectUpdateInput(name="New Name", state="completed")
    assert update.name == "New Name"
    assert update.state == "completed"


def test_project_update_input_with_message() -> None:
    """ProjectUpdateInput should support update_message for progress posts."""
    update = ProjectUpdateInput(
        state="started",
        updateMessage="Sprint started!",
    )
    assert update.update_message == "Sprint started!"


def test_project_update_input_aliases() -> None:
    """ProjectUpdateInput should accept both snake_case and camelCase."""
    update = ProjectUpdateInput(updateMessage="Update")
    assert update.update_message == "Update"


# -----------------------------------------------------------------------------
# _map_priority_to_api Tests
# -----------------------------------------------------------------------------


def test_map_priority_to_api_int_values() -> None:
    """_map_priority_to_api should map integer priorities."""
    from linear_api import LinearPriority

    assert _map_priority_to_api(0) == LinearPriority.NONE
    assert _map_priority_to_api(1) == LinearPriority.LOW
    assert _map_priority_to_api(2) == LinearPriority.MEDIUM
    assert _map_priority_to_api(3) == LinearPriority.HIGH
    assert _map_priority_to_api(4) == LinearPriority.URGENT


def test_map_priority_to_api_string_values() -> None:
    """_map_priority_to_api should map string priorities."""
    from linear_api import LinearPriority

    assert _map_priority_to_api("low") == LinearPriority.LOW
    assert _map_priority_to_api("medium") == LinearPriority.MEDIUM
    assert _map_priority_to_api("high") == LinearPriority.HIGH
    assert _map_priority_to_api("urgent") == LinearPriority.URGENT
    assert _map_priority_to_api("no_priority") == LinearPriority.NONE
    assert _map_priority_to_api("no priority") == LinearPriority.NONE
    assert _map_priority_to_api("none") == LinearPriority.NONE


def test_map_priority_to_api_none() -> None:
    """_map_priority_to_api should return None for None input."""
    assert _map_priority_to_api(None) is None


def test_map_priority_to_api_invalid() -> None:
    """_map_priority_to_api should default to MEDIUM for invalid values."""
    from linear_api import LinearPriority

    assert _map_priority_to_api(999) == LinearPriority.MEDIUM
    assert _map_priority_to_api("invalid") == LinearPriority.MEDIUM


# -----------------------------------------------------------------------------
# IssueRelation Model Tests
# -----------------------------------------------------------------------------


def test_related_issue_ref_creation() -> None:
    """RelatedIssueRef requires id and accepts optional title."""
    ref = RelatedIssueRef(id="issue-1", title="Fix bug")
    assert ref.id == "issue-1"
    assert ref.title == "Fix bug"


def test_related_issue_ref_optional_title() -> None:
    """RelatedIssueRef should accept None title."""
    ref = RelatedIssueRef(id="issue-1")
    assert ref.title is None


def test_issue_relation_creation_with_alias() -> None:
    """IssueRelation should accept both snake_case and camelCase."""
    rel = IssueRelation(
        id="rel-1",
        type="blocks",
        relatedIssue=RelatedIssueRef(id="issue-2", title="Other"),
        createdAt="2026-01-01T00:00:00",
    )
    assert rel.id == "rel-1"
    assert rel.type == "blocks"
    assert rel.related_issue is not None
    assert rel.related_issue.id == "issue-2"
    assert rel.created_at == "2026-01-01T00:00:00"


def test_issue_relation_optional_fields_default_none() -> None:
    """IssueRelation defaults related_issue and created_at to None."""
    rel = IssueRelation(id="rel-1", type="related")
    assert rel.related_issue is None
    assert rel.created_at is None


def test_issue_relation_from_linear_full() -> None:
    """IssueRelation.from_linear converts a linear_api IssueRelation."""
    from datetime import datetime

    class MockLinearRelation:
        id = "rel-123"
        type = "blocks"
        relatedIssue = {"id": "issue-9", "title": "Downstream task"}
        createdAt = datetime(2026, 1, 2, 3, 4, 5)

    rel = IssueRelation.from_linear(MockLinearRelation())
    assert rel.id == "rel-123"
    assert rel.type == "blocks"
    assert rel.related_issue is not None
    assert rel.related_issue.id == "issue-9"
    assert rel.related_issue.title == "Downstream task"
    assert rel.created_at == "2026-01-02T03:04:05"


def test_issue_relation_from_linear_missing_related_issue() -> None:
    """from_linear leaves related_issue as None when source dict is None."""

    class MockLinearRelation:
        id = "rel-2"
        type = "related"
        relatedIssue = None
        createdAt = None

    rel = IssueRelation.from_linear(MockLinearRelation())
    assert rel.related_issue is None
    assert rel.created_at is None


def test_issue_relation_from_linear_related_issue_without_id() -> None:
    """from_linear ignores a relatedIssue dict that has no id."""

    class MockLinearRelation:
        id = "rel-3"
        type = "duplicate"
        relatedIssue = {"title": "orphan"}
        createdAt = None

    rel = IssueRelation.from_linear(MockLinearRelation())
    assert rel.related_issue is None


def test_issue_relation_from_linear_related_issue_without_title() -> None:
    """from_linear preserves an id-only relatedIssue dict (title optional)."""

    class MockLinearRelation:
        id = "rel-4"
        type = "blocks"
        relatedIssue = {"id": "issue-x"}
        createdAt = None

    rel = IssueRelation.from_linear(MockLinearRelation())
    assert rel.related_issue is not None
    assert rel.related_issue.id == "issue-x"
    assert rel.related_issue.title is None


def test_map_priority_from_api_unknown_types() -> None:
    """_map_priority_from_api defaults to MEDIUM for unrecognised inputs.

    Real LinearIssue.priority is always a LinearPriority enum, but the helper
    must still be safe against partial GraphQL responses (None, raw ints, junk).
    """
    from libs.linear.schemas import _map_priority_from_api

    assert _map_priority_from_api(None) == Priority.MEDIUM
    assert _map_priority_from_api("medium") == Priority.MEDIUM  # not int/enum
    assert _map_priority_from_api(99) == Priority.MEDIUM  # out of range
    assert _map_priority_from_api(object()) == Priority.MEDIUM
