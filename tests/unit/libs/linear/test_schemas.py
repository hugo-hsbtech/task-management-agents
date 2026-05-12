"""Unit tests for libs.linear.schemas.

Tests all Pydantic models and from_linear conversion methods.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from libs.linear.schemas import (
    Issue,
    IssueInput,
    IssueLabelInput,
    IssueUpdateInput,
    Label,
    Priority,
    Project,
    ProjectUpdateInput,
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
    project = Project(id="proj-123", name="Sprint 1", teamId="team-456")
    assert project.id == "proj-123"
    assert project.name == "Sprint 1"
    assert project.team_id == "team-456"
    assert project.state is None
    assert project.description is None


def test_project_with_optional_fields() -> None:
    """Project model should accept optional fields."""
    project = Project(
        id="proj-123",
        name="Sprint 1",
        teamId="team-456",
        description="Q1 sprint",
        state="started",
    )
    assert project.description == "Q1 sprint"
    assert project.state == "started"


def test_project_from_linear() -> None:
    """Project.from_linear should convert linear_api Project object."""

    class MockLinearProject:
        id = "proj-789"
        name = "Sprint 2"
        team_id = "team-123"
        state = "completed"

    project = Project.from_linear(MockLinearProject())
    assert project.id == "proj-789"
    assert project.name == "Sprint 2"
    assert project.team_id == "team-123"
    assert project.state == "completed"


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
    """Issue.from_linear should convert linear_api Issue object."""

    class MockState:
        id = "state-review"
        name = "in_review"
        color = "#ff0"
        type = "started"

    class MockLinearIssue:
        id = "issue-456"
        identifier = "PROD-123"
        title = "Feature request"
        description = "Need this feature"
        state = MockState()
        # Linear's int: 4 = NONE (Linear's enum ordering is inverse of ours).
        priority = 4
        team_id = "team-789"
        project_id = "proj-000"
        parent_id = "issue-parent"
        url = "https://linear.app/issue/PROD-123"
        created_at = "2024-01-01"
        updated_at = "2024-01-02"

    issue = Issue.from_linear(MockLinearIssue())
    assert issue.id == "issue-456"
    assert issue.identifier == "PROD-123"
    assert issue.title == "Feature request"
    assert issue.state.name == "in_review"
    assert issue.state.id == "state-review"
    # Linear NONE (4) maps to our NO_PRIORITY (0).
    assert issue.priority == 0


def test_issue_from_linear_no_state() -> None:
    """Issue.from_linear should handle issue with no state."""

    class MockLinearIssue:
        id = "issue-789"
        identifier = "ENG-1"
        title = "Task"
        description = None
        state = None
        priority = 2
        url = "https://linear.app/issue/ENG-1"
        team_id = None
        project_id = None
        parent_id = None
        created_at = None
        updated_at = None

    issue = Issue.from_linear(MockLinearIssue())
    assert issue.state is None


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
    )
    assert update.state == "completed"
    assert update.priority == 4


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
# IssueLabelInput Model Tests
# -----------------------------------------------------------------------------


def test_issue_label_input_creation() -> None:
    """IssueLabelInput should be created with required fields."""
    input_data = IssueLabelInput(issueId="issue-123", labelName="bug")
    assert input_data.issue_id == "issue-123"
    assert input_data.label_name == "bug"


def test_issue_label_input_aliases() -> None:
    """IssueLabelInput should accept both snake_case and camelCase."""
    input1 = IssueLabelInput(issueId="issue-1", labelName="bug")
    input2 = IssueLabelInput(issue_id="issue-1", label_name="bug")
    assert input1.issue_id == input2.issue_id


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
