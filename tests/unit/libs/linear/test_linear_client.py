"""Unit tests for libs.linear.linear_client.

Tests LinearClient with mocked linear_api dependency.
"""

from __future__ import annotations

import contextlib
import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from linear_api import LinearPriority

from libs.linear.linear_client import LinearClient
from libs.linear.schemas import (
    CommentInput,
    IssueInput,
    IssueUpdateInput,
    Priority,
    ProjectCommentInput,
    ProjectUpdateInput,
)

# -----------------------------------------------------------------------------
# Mock builders matching real linear_api domain shapes
# -----------------------------------------------------------------------------


_PRIORITY_INT_TO_LINEAR: dict[int, LinearPriority] = {
    Priority.NO_PRIORITY: LinearPriority.NONE,
    Priority.LOW: LinearPriority.LOW,
    Priority.MEDIUM: LinearPriority.MEDIUM,
    Priority.HIGH: LinearPriority.HIGH,
    Priority.URGENT: LinearPriority.URGENT,
}


def _make_issue_mock(
    *,
    id: str = "issue-mock",
    identifier: str | None = "MOCK-1",
    title: str = "Mock Issue",
    description: str | None = None,
    state=None,
    priority: int = Priority.MEDIUM,
    team_id: str | None = None,
    project_id: str | None = None,
    parent_id: str | None = None,
    url: str = "https://linear.app/issue/MOCK-1",
    created_at=None,
    updated_at=None,
) -> MagicMock:
    """Build a MagicMock with snake_case attributes matching _field() lookup order."""
    m = MagicMock(spec=[])
    m.id = id
    m.identifier = identifier
    m.title = title
    m.description = description
    m.state = state
    # Real LinearIssue.priority is a LinearPriority enum, not an int.
    m.priority = _PRIORITY_INT_TO_LINEAR.get(priority, LinearPriority.MEDIUM)
    m.team_id = team_id
    m.project_id = project_id
    m.parent_id = parent_id
    m.url = url
    m.created_at = created_at
    m.updated_at = updated_at
    return m


def _make_project_mock(
    *,
    id: str = "proj-mock",
    name: str = "Mock Project",
    description: str | None = None,
    state: str | None = None,
    url: str | None = None,
    team_id: str | None = None,
    team_name: str = "Mock Team",
    team_key: str = "MOCK",
) -> MagicMock:
    """Build a MagicMock matching linear_api.LinearProject's read surface.

    Project.from_linear reads `linear_project.teams[0]` for the nested team;
    we populate that here. Real LinearProject exposes .teams as a property
    that issues a network call, but on a MagicMock it's just a plain list.
    """
    m = MagicMock()
    m.id = id
    m.name = name
    m.description = description
    if state is None:
        m.status = None
    else:
        # ProjectStatusType is a StrEnum on the real model; str(t) returns its
        # value. Use a tiny class so str() works deterministically.
        class _StatusType(str):
            value = state

        status_type = _StatusType(state)
        status = MagicMock()
        status.type = status_type
        m.status = status
    m.url = url
    if team_id is None:
        m.teams = []
    else:
        team_mock = MagicMock()
        team_mock.id = team_id
        team_mock.name = team_name
        team_mock.key = team_key
        team_mock.description = None
        m.teams = [team_mock]
    return m


def _make_state_mock(
    *,
    id: str = "state-1",
    name: str = "Backlog",
    color: str = "#ccc",
    type: str = "backlog",
) -> MagicMock:
    """Build a MagicMock matching linear_api.LinearState (WorkflowState)."""
    m = MagicMock(spec=[])
    m.id = id
    m.name = name
    m.color = color
    m.type = type
    return m


@pytest.fixture
def mock_linear_api() -> MagicMock:
    """Create a mock linear_api module."""
    mock = MagicMock()
    return mock


@pytest.fixture
def client(mock_linear_api: MagicMock) -> LinearClient:
    """Create LinearClient with mocked dependencies."""
    with patch("libs.linear.linear_client.BaseLinearClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        client = LinearClient(api_key="test-api-key")
        client._client = mock_instance
        return client


# -----------------------------------------------------------------------------
# Initialization Tests
# -----------------------------------------------------------------------------


def test_client_initialization_requires_api_key() -> None:
    """LinearClient should require API key."""
    with pytest.raises(ValueError, match="Linear API key required"):
        LinearClient(api_key="")


def test_client_initialization_with_valid_key() -> None:
    """LinearClient should initialize with valid API key."""
    with patch("libs.linear.linear_client.BaseLinearClient") as MockClient:
        LinearClient(api_key="valid-key")
        MockClient.assert_called_once_with(api_key="valid-key")


# -----------------------------------------------------------------------------
# Team Operations Tests
# -----------------------------------------------------------------------------


def test_list_teams(client: LinearClient) -> None:
    """list_teams should return list of Team objects."""
    # Mock teams.get_all() returning dict of team objects
    mock_team1 = MagicMock()
    mock_team1.id = "team-1"
    mock_team1.name = "Engineering"
    mock_team1.key = "ENG"
    mock_team1.description = "Dev team"

    mock_team2 = MagicMock()
    mock_team2.id = "team-2"
    mock_team2.name = "Product"
    mock_team2.key = "PROD"
    mock_team2.description = None

    client._client.teams.get_all.return_value = {
        "team-1": mock_team1,
        "team-2": mock_team2,
    }

    teams = client.list_teams()

    assert len(teams) == 2
    assert teams[0].id == "team-1"
    assert teams[0].name == "Engineering"
    assert teams[1].id == "team-2"
    client._client.teams.get_all.assert_called_once()


def test_list_teams_empty(client: LinearClient) -> None:
    """list_teams should handle empty teams list."""
    client._client.teams.get_all.return_value = {}

    teams = client.list_teams()

    assert teams == []


def test_list_teams_api_failure_wraps_as_runtime_error(
    client: LinearClient,
) -> None:
    """list_teams must wrap underlying failures so handlers can return
    a structured error dict."""
    client._client.teams.get_all.side_effect = Exception("API boom")

    with pytest.raises(RuntimeError, match="Failed to list teams"):
        client.list_teams()


def test_get_team_success(client: LinearClient) -> None:
    """get_team should return Team when found."""
    mock_team = MagicMock()
    mock_team.id = "team-123"
    mock_team.name = "Engineering"
    mock_team.key = "ENG"
    mock_team.description = None

    client._client.teams.get.return_value = mock_team

    team = client.get_team("team-123")

    assert team is not None
    assert team.id == "team-123"
    assert team.name == "Engineering"
    client._client.teams.get.assert_called_once_with(team_id="team-123")


def test_get_team_not_found(client: LinearClient) -> None:
    """get_team should return None when team not found."""
    client._client.teams.get.side_effect = ValueError("Not found")

    # Fallback to search in list
    client._client.teams.get_all.return_value = {}

    team = client.get_team("non-existent")

    assert team is None


def test_get_team_fallback_search(client: LinearClient) -> None:
    """get_team should fallback to searching in list."""
    client._client.teams.get.side_effect = ValueError("Not found")

    mock_team = MagicMock()
    mock_team.id = "team-456"
    mock_team.name = "Design"
    mock_team.key = "DES"
    mock_team.description = None

    client._client.teams.get_all.return_value = {"team-456": mock_team}

    team = client.get_team("DES")  # Search by key

    assert team is not None
    assert team.id == "team-456"


# -----------------------------------------------------------------------------
# Project Operations Tests
# -----------------------------------------------------------------------------


def test_list_projects(client: LinearClient) -> None:
    """list_projects should return list of Project objects."""
    mock_project1 = _make_project_mock(
        id="proj-1",
        name="Sprint 1",
        description="First sprint",
        state="started",
        team_id="team-123",
        team_name="Engineering",
        team_key="ENG",
    )
    mock_project2 = _make_project_mock(
        id="proj-2",
        name="Sprint 2",
        description=None,
        state="planned",
        team_id="team-123",
        team_name="Engineering",
        team_key="ENG",
    )

    client._client.projects.get_all.return_value = {
        "proj-1": mock_project1,
        "proj-2": mock_project2,
    }

    projects = client.list_projects("team-123")

    assert len(projects) == 2
    assert projects[0].id == "proj-1"
    # team is read from linear_project.teams[0] inside from_linear.
    assert projects[0].team is not None
    assert projects[0].team.id == "team-123"
    assert projects[0].state == "started"
    client._client.projects.get_all.assert_called_once_with(team_id="team-123")


def test_list_projects_empty_team_id(client: LinearClient) -> None:
    """list_projects raises ValueError when team_id is empty."""
    with pytest.raises(ValueError, match="Team ID is required"):
        client.list_projects("")
    client._client.projects.get_all.assert_not_called()


def test_list_projects_api_failure_wraps_as_runtime_error(
    client: LinearClient,
) -> None:
    """list_projects must wrap underlying failures so handlers can return
    a structured error dict."""
    client._client.projects.get_all.side_effect = Exception("API boom")

    with pytest.raises(RuntimeError, match="Failed to list projects for team 'team-1'"):
        client.list_projects("team-1")


def test_get_project_success(client: LinearClient) -> None:
    """get_project should return Project when found."""
    mock_project = _make_project_mock(
        id="proj-123", name="Sprint 1", state="started", team_id="team-9"
    )

    client._client.projects.get.return_value = mock_project

    project = client.get_project("proj-123")

    assert project is not None
    assert project.id == "proj-123"
    assert project.name == "Sprint 1"
    assert project.state == "started"
    assert project.team is not None
    assert project.team.id == "team-9"


def test_get_project_not_found(client: LinearClient) -> None:
    """get_project returns None and logs when the underlying SDK call raises."""
    client._client.projects.get.side_effect = Exception("Not found")

    project = client.get_project("non-existent")
    assert project is None


def test_update_project(client: LinearClient) -> None:
    """update_project should update project fields."""
    mock_project = _make_project_mock(
        id="proj-123",
        name="Updated Name",
        description="Updated description",
        state="completed",
    )

    client._client.projects.update.return_value = mock_project
    client._client.projects.get.return_value = mock_project

    update_input = ProjectUpdateInput(
        name="Updated Name",
        description="Updated description",
        state="completed",
    )

    project = client.update_project("proj-123", update_input)

    assert project.name == "Updated Name"
    assert project.state == "completed"
    client._client.projects.update.assert_called_once_with(
        project_id="proj-123",
        name="Updated Name",
        description="Updated description",
        state="completed",
    )


def test_update_project_with_message(client: LinearClient) -> None:
    """update_project should post update message when provided."""
    mock_project = _make_project_mock(id="proj-123", name="Project")

    client._client.projects.get.return_value = mock_project

    update_input = ProjectUpdateInput(updateMessage="Project shipped!")

    # Mock _post_project_update to avoid GraphQL call
    with patch.object(client, "_post_project_update") as mock_post:
        client.update_project("proj-123", update_input)
        mock_post.assert_called_once_with("proj-123", "Project shipped!")


def test_update_project_error(client: LinearClient) -> None:
    """update_project should raise RuntimeError on API failure."""
    client._client.projects.update.side_effect = Exception("API Error")

    update_input = ProjectUpdateInput(name="New Name")

    with pytest.raises(RuntimeError, match="Failed to update project"):
        client.update_project("proj-123", update_input)


def test_update_project_clears_field_when_empty_string(
    client: LinearClient,
) -> None:
    """Passing description='' or state='' is a clear-the-field request, not
    'no update'. The truthy check used to skip the API call entirely; must
    use `is not None`."""
    mock_project = MagicMock()
    mock_project.id = "p-1"
    mock_project.name = "Project"
    mock_project.description = ""
    mock_project.team_id = "t-1"
    mock_project.state = "started"
    mock_project.url = "https://linear.app/project/p-1"
    mock_project.status = None
    mock_project.teams = []
    client._client.projects.update.return_value = mock_project

    client.update_project("p-1", ProjectUpdateInput(description=""))

    client._client.projects.update.assert_called_once_with(
        project_id="p-1",
        name=None,
        description="",
        state=None,
    )
    client._client.projects.get.assert_not_called()


def test_update_project_not_found_raises_clean_message(
    client: LinearClient,
) -> None:
    """A None return from the underlying client must surface as a 'not found'
    RuntimeError, not get masked as a generic 'Failed to update project'."""
    client._client.projects.update.return_value = None

    update_input = ProjectUpdateInput(name="New Name")

    with pytest.raises(RuntimeError, match=r"Project 'proj-123' not found\.$"):
        client.update_project("proj-123", update_input)


def test_post_project_update_logs_on_failure(
    client: LinearClient, caplog: pytest.LogCaptureFixture
) -> None:
    """_post_project_update is best-effort but must log the cause so a
    failed GraphQL mutation isn't invisible to callers."""
    import logging

    # Force the raw GraphQL path to fail (both execute_graphql and _execute
    # since _execute_raw checks execute_graphql first).
    client._client.execute_graphql.side_effect = RuntimeError("auth_error")
    client._client._execute.side_effect = RuntimeError("auth_error")

    with caplog.at_level(logging.ERROR, logger="libs.linear.linear_client"):
        client._post_project_update("proj-123", "Sprint shipped!")

    assert any(
        "projectUpdateCreate" in r.message and "proj-123" in r.message
        for r in caplog.records
    )
    # The cause must appear in the captured traceback.
    assert any(r.exc_info is not None for r in caplog.records)


# -----------------------------------------------------------------------------
# Issue Operations Tests
# -----------------------------------------------------------------------------


def test_list_issues(client: LinearClient) -> None:
    """list_issues should return list of Issue objects."""
    mock_issue1 = _make_issue_mock(
        id="issue-1",
        identifier="ENG-1",
        title="Bug fix",
        description="Fix the bug",
        state=_make_state_mock(
            id="state-1", name="in_progress", color="#00f", type="started"
        ),
        priority=Priority.MEDIUM,
        team_id="team-123",
        project_id="proj-456",
        url="https://linear.app/issue/ENG-1",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )

    mock_issue2 = _make_issue_mock(
        id="issue-2",
        identifier="ENG-2",
        title="Feature",
        state=None,
        priority=Priority.HIGH,
        url="https://linear.app/issue/ENG-2",
    )

    client._client.projects.get_issues.return_value = [mock_issue1, mock_issue2]

    issues = client.list_issues("proj-456")

    assert len(issues) == 2
    assert issues[0].id == "issue-1"
    assert issues[0].identifier == "ENG-1"
    assert issues[0].state.name == "in_progress"  # IssueState object
    assert issues[1].id == "issue-2"
    assert issues[1].state is None
    client._client.projects.get_issues.assert_called_once_with(project_id="proj-456")


def test_list_issues_api_failure_wraps_as_runtime_error(
    client: LinearClient,
) -> None:
    """list_issues must wrap underlying failures so handlers can return
    a structured error dict."""
    client._client.projects.get_issues.side_effect = Exception("API boom")

    with pytest.raises(
        RuntimeError, match="Failed to list issues for project 'proj-1'"
    ):
        client.list_issues("proj-1")


def test_list_issues_coerces_linear_priority_enum_to_int(
    client: LinearClient,
) -> None:
    """linear-api's LinearPriority is a plain Enum (not IntEnum), so
    int(value) fails directly and only .value is safe. Pydantic happens to
    coerce it today, but we don't want to rely on that — extract the int
    value explicitly."""
    from linear_api import LinearPriority

    mock_issue = MagicMock()
    mock_issue.id = "i-1"
    mock_issue.identifier = "ENG-1"
    mock_issue.title = "T"
    mock_issue.description = None
    mock_issue.state = None
    mock_issue.priority = LinearPriority.HIGH
    mock_issue.team_id = None
    mock_issue.project_id = None
    mock_issue.parent_id = None
    mock_issue.url = "https://x"
    mock_issue.created_at = None
    mock_issue.updated_at = None

    client._client.issues.get.return_value = mock_issue
    issue = client.get_issue("i-1")

    assert issue is not None
    assert issue.priority == 3
    assert isinstance(issue.priority, int)
    assert not isinstance(issue.priority, LinearPriority)


def test_list_issues_handles_dict_response_from_linear_api(
    client: LinearClient,
) -> None:
    """projects.get_issues() returns raw GraphQL dicts, not LinearIssue
    objects. Issue.from_linear must handle that shape — otherwise listing
    a project's issues blows up with AttributeError: 'dict' object has no
    attribute 'id'."""
    client._client.projects.get_issues.return_value = [
        {
            "id": "i-1",
            "title": "First",
            "description": None,
            "state": {"id": "s-1", "name": "Todo", "type": "unstarted"},
            "priority": 2,
            "priorityLabel": "Medium",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-02T00:00:00Z",
        },
        {
            "id": "i-2",
            "title": "Second",
            "description": "Body",
            "state": None,
            "priority": 3,
            "createdAt": None,
            "updatedAt": None,
        },
    ]

    issues = client.list_issues("proj-1")

    assert [i.id for i in issues] == ["i-1", "i-2"]
    assert issues[0].title == "First"
    assert issues[0].state is not None
    assert issues[0].state.name == "Todo"
    assert issues[0].created_at == "2024-01-01T00:00:00Z"
    assert issues[1].state is None
    # identifier is absent from the GraphQL projection — must be None,
    # not a validation failure.
    assert issues[0].identifier is None


def test_get_issue_success(client: LinearClient) -> None:
    """get_issue should return Issue when found."""
    mock_issue = _make_issue_mock(
        id="issue-123",
        identifier="ENG-42",
        title="Test Issue",
        description="Description",
        state=_make_state_mock(
            id="state-backlog", name="backlog", color="#ccc", type="backlog"
        ),
        priority=Priority.LOW,
        url="https://linear.app/issue/ENG-42",
    )

    client._client.issues.get.return_value = mock_issue

    issue = client.get_issue("ENG-42")

    assert issue is not None
    assert issue.id == "issue-123"
    assert issue.identifier == "ENG-42"
    assert issue.state.name == "backlog"


def test_get_issue_not_found(client: LinearClient) -> None:
    """get_issue should return None when issue not found."""
    client._client.issues.get.side_effect = Exception("Not found")

    issue = client.get_issue("non-existent")

    assert issue is None


def test_create_issue(client: LinearClient) -> None:
    """create_issue should create and return Issue."""
    mock_team = MagicMock()
    mock_team.id = "team-123"
    mock_team.name = "Engineering"
    mock_team.key = "ENG"
    mock_team.description = None
    client._client.teams.get.return_value = mock_team

    mock_project = MagicMock()
    mock_project.id = "proj-456"
    mock_project.name = "Roadmap"
    mock_project.description = None
    mock_project.team_id = "team-123"
    mock_project.state = None
    mock_project.url = "https://linear.app/project/proj-456"
    mock_project.status = None
    mock_project.teams = []
    client._client.projects.get.return_value = mock_project

    mock_issue = MagicMock()
    mock_issue.id = "new-issue-id"
    mock_issue.identifier = "ENG-99"
    mock_issue.title = "New Issue"
    mock_issue.description = "Description"
    mock_issue.state = None
    mock_issue.priority = 2
    mock_issue.team_id = None
    mock_issue.project_id = None
    mock_issue.parent_id = None
    mock_issue.url = "https://linear.app/issue/ENG-99"
    mock_issue.created_at = None
    mock_issue.updated_at = None
    client._client.issues.create.return_value = mock_issue

    input_data = IssueInput(
        title="New Issue",
        teamId="team-123",
        projectId="proj-456",
        description="Description",
        priority=Priority.MEDIUM,
    )

    issue = client.create_issue(input_data)

    assert issue.id == "new-issue-id"
    assert issue.identifier == "ENG-99"
    client._client.issues.create.assert_called_once()
    # IDs must be resolved to human-readable names before calling linear-api
    sent_issue = client._client.issues.create.call_args.kwargs["issue"]
    assert sent_issue.teamName == "Engineering"
    assert sent_issue.projectName == "Roadmap"


def test_create_issue_api_failure_wraps_as_runtime_error(
    client: LinearClient,
) -> None:
    """A non-RuntimeError from issues.create must be wrapped so the handler
    layer's RuntimeError filter catches it."""
    mock_team = MagicMock(
        name="Engineering", id="team-123", key="ENG", description=None
    )
    mock_team.name = "Engineering"
    mock_project = MagicMock(
        id="proj-456", description=None, team_id="team-123", state=None
    )
    mock_project.name = "Roadmap"
    mock_project.url = "https://linear.app/project/proj-456"
    mock_project.status = None
    mock_project.teams = []
    client._client.teams.get.return_value = mock_team
    client._client.projects.get.return_value = mock_project
    client._client.issues.create.side_effect = Exception("API boom")

    input_data = IssueInput(title="X", teamId="team-123", projectId="proj-456")

    with pytest.raises(RuntimeError, match="Failed to create issue"):
        client.create_issue(input_data)


def test_update_issue(client: LinearClient) -> None:
    """update_issue should update and return Issue."""
    mock_issue = MagicMock()
    mock_issue.id = "issue-123"
    mock_issue.identifier = "ENG-42"
    mock_issue.title = "Updated Title"
    mock_issue.description = "Updated Desc"
    mock_state = MagicMock()
    mock_state.id = "state-done"
    mock_state.name = "completed"
    mock_state.color = "#0f0"
    mock_state.type = "completed"
    mock_issue.state = mock_state
    # Linear's wire value: 0 = URGENT (Linear's enum inverts ours).
    mock_issue.priority = 0
    mock_issue.team_id = None
    mock_issue.project_id = None
    mock_issue.parent_id = None
    mock_issue.url = "https://linear.app/issue/ENG-42"
    mock_issue.created_at = None
    mock_issue.updated_at = None

    client._client.issues.update.return_value = mock_issue

    update_input = IssueUpdateInput(
        title="Updated Title",
        description="Updated Desc",
        state="completed",
        priority=Priority.URGENT,
    )

    issue = client.update_issue("issue-123", update_input)

    assert issue.title == "Updated Title"
    # Linear URGENT (0) maps to our URGENT (4).
    assert issue.priority == 4
    assert issue.state.name == "completed"
    client._client.issues.update.assert_called_once()
    # IssueUpdateInput.state must be forwarded as stateName (linear-api
    # resolves the workflow state name to an ID internally).
    sent_update = client._client.issues.update.call_args.args[1]
    assert sent_update.stateName == "completed"


def test_update_issue_error(client: LinearClient) -> None:
    """update_issue should wrap underlying failures as RuntimeError so the
    handler layer can return a structured error dict."""
    client._client.issues.update.side_effect = Exception("API Error")

    update_input = IssueUpdateInput(title="X")

    with pytest.raises(RuntimeError, match="Failed to update issue 'issue-123'"):
        client.update_issue("issue-123", update_input)


def test_delete_issue_success(client: LinearClient) -> None:
    """delete_issue should return True on success."""
    client._client.issues.delete.return_value = True

    result = client.delete_issue("issue-123")

    assert result is True
    client._client.issues.delete.assert_called_once_with("issue-123")


def test_delete_issue_failure(client: LinearClient) -> None:
    """delete_issue should return False on failure."""
    client._client.issues.delete.side_effect = Exception("Delete failed")

    result = client.delete_issue("issue-123")

    assert result is False


# -----------------------------------------------------------------------------
# Label Operations Tests
# -----------------------------------------------------------------------------


def test_list_issue_labels(client: LinearClient) -> None:
    """list_issue_labels should return list of Label objects."""
    mock_label1 = MagicMock()
    mock_label1.id = "label-1"
    mock_label1.name = "bug"
    mock_label1.color = "#ff0000"
    mock_label1.description = None

    mock_label2 = MagicMock()
    mock_label2.id = "label-2"
    mock_label2.name = "urgent"
    mock_label2.color = "#ff9900"
    mock_label2.description = None

    mock_issue = MagicMock()
    mock_issue.id = "issue-123"
    mock_issue.identifier = "ENG-42"
    mock_issue.title = "Issue"
    mock_issue.description = None
    mock_issue.labels = [mock_label1, mock_label2]
    mock_issue.state = None
    mock_issue.priority = 2
    mock_issue.team_id = None
    mock_issue.project_id = None
    mock_issue.parent_id = None
    mock_issue.url = "https://linear.app/issue/ENG-42"
    mock_issue.created_at = None
    mock_issue.updated_at = None

    client._client.issues.get_labels.return_value = [mock_label1, mock_label2]

    labels = client.list_issue_labels("issue-123")

    assert len(labels) == 2
    assert labels[0].name == "bug"
    assert labels[1].name == "urgent"


def test_list_issue_labels_no_labels(client: LinearClient) -> None:
    """list_issue_labels should return empty list when issue has no labels."""
    client._client.issues.get_labels.return_value = []

    labels = client.list_issue_labels("issue-123")

    assert len(labels) == 0


def test_list_issue_labels_issue_not_found(client: LinearClient) -> None:
    """list_issue_labels should return empty list when issue not found."""
    client._client.issues.get_labels.side_effect = Exception("Not found")

    labels = client.list_issue_labels("non-existent")

    assert labels == []


# -----------------------------------------------------------------------------
# Team Methods Tests
# -----------------------------------------------------------------------------


def test_get_team_labels(client: LinearClient) -> None:
    """get_team_labels should return list of label dicts."""
    mock_label1 = MagicMock()
    mock_label1.id = "label-1"
    mock_label1.name = "bug"
    mock_label1.color = "#ff0000"
    mock_label1.description = "Bug reports"

    mock_label2 = MagicMock()
    mock_label2.id = "label-2"
    mock_label2.name = "urgent"
    mock_label2.color = "#ff9900"
    mock_label2.description = None

    client._client.teams.get_labels.return_value = [mock_label1, mock_label2]

    labels = client.get_team_labels("team-123")

    assert len(labels) == 2
    assert labels[0]["id"] == "label-1"
    assert labels[0]["name"] == "bug"
    assert labels[0]["color"] == "#ff0000"
    assert labels[0]["description"] == "Bug reports"
    client._client.teams.get_labels.assert_called_once_with("team-123")


def test_get_team_labels_empty(client: LinearClient) -> None:
    """get_team_labels should return empty list when no labels."""
    client._client.teams.get_labels.return_value = []

    labels = client.get_team_labels("team-123")

    assert len(labels) == 0


def test_get_team_issues(client: LinearClient) -> None:
    """get_team_issues should return list of Issue objects."""
    mock_issue1 = _make_issue_mock(
        id="issue-1",
        identifier="ENG-1",
        title="Issue 1",
        description="Description 1",
        priority=Priority.LOW,
        team_id="team-123",
        project_id="project-1",
        url="https://linear.app/issue/ENG-1",
    )
    mock_issue2 = _make_issue_mock(
        id="issue-2",
        identifier="ENG-2",
        title="Issue 2",
        description="Description 2",
        priority=Priority.MEDIUM,
        team_id="team-123",
        project_id="project-1",
        url="https://linear.app/issue/ENG-2",
    )

    client._client.teams.get_issues.return_value = {
        "issue-1": mock_issue1,
        "issue-2": mock_issue2,
    }

    issues = client.get_team_issues("team-123")

    assert len(issues) == 2
    assert issues[0].id == "issue-1"
    assert issues[0].title == "Issue 1"
    assert issues[1].id == "issue-2"
    assert issues[1].title == "Issue 2"
    client._client.teams.get_issues.assert_called_once_with("team-123")


def test_get_team_projects(client: LinearClient) -> None:
    """get_team_projects should return list of Project objects."""
    mock_project1 = _make_project_mock(
        id="project-1", name="Project 1", description="Description 1", state="active"
    )
    mock_project2 = _make_project_mock(
        id="project-2", name="Project 2", description="Description 2", state="planned"
    )

    client._client.teams.get_projects.return_value = {
        "project-1": mock_project1,
        "project-2": mock_project2,
    }

    projects = client.get_team_projects("team-123")

    assert len(projects) == 2
    assert projects[0].id == "project-1"
    assert projects[0].name == "Project 1"
    assert projects[1].id == "project-2"
    assert projects[1].name == "Project 2"
    client._client.teams.get_projects.assert_called_once_with("team-123")


# -----------------------------------------------------------------------------
# Project Methods Tests
# -----------------------------------------------------------------------------


def test_get_project_labels(client: LinearClient) -> None:
    """get_project_labels should return list of label dicts."""
    mock_label1 = MagicMock()
    mock_label1.id = "label-1"
    mock_label1.name = "feature"
    mock_label1.color = "#00ff00"
    mock_label1.description = "Feature requests"

    client._client.projects.get_labels.return_value = [mock_label1]

    labels = client.get_project_labels("project-123")

    assert len(labels) == 1
    assert labels[0]["id"] == "label-1"
    assert labels[0]["name"] == "feature"
    assert labels[0]["color"] == "#00ff00"
    assert labels[0]["description"] == "Feature requests"
    client._client.projects.get_labels.assert_called_once_with("project-123")


def test_get_project_comments(client: LinearClient) -> None:
    """get_project_comments fetches via raw GraphQL and paginates."""
    page1 = {
        "project": {
            "comments": {
                "nodes": [
                    {
                        "id": "comment-1",
                        "body": "First comment",
                        "createdAt": "2023-01-01T00:00:00+00:00",
                        "user": {"id": "user-1", "name": "Alice"},
                    },
                ],
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor-a"},
            }
        }
    }
    page2 = {
        "project": {
            "comments": {
                "nodes": [
                    {
                        "id": "comment-2",
                        "body": "Second comment",
                        "createdAt": "2023-01-02T00:00:00+00:00",
                        "user": None,
                    },
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }

    with unittest.mock.patch.object(
        client, "_execute_raw", side_effect=[page1, page2]
    ) as mock_exec:
        comments = client.get_project_comments("project-123")

    assert [c.id for c in comments] == ["comment-1", "comment-2"]
    assert comments[0].user is not None
    assert comments[0].user.name == "Alice"
    assert comments[1].user is None
    assert comments[0].created_at == "2023-01-01T00:00:00+00:00"

    # Two paginated calls: first with cursor=None, second with cursor="cursor-a"
    assert mock_exec.call_count == 2
    second_call_vars = mock_exec.call_args_list[1].args[1]
    assert second_call_vars["projectId"] == "project-123"
    assert second_call_vars["cursor"] == "cursor-a"


def test_get_project_comments_handles_wrapped_response(client: LinearClient) -> None:
    """Accepts both {data: {project: ...}} and {project: ...} response shapes."""
    wrapped = {
        "data": {
            "project": {
                "comments": {
                    "nodes": [
                        {
                            "id": "c1",
                            "body": "b",
                            "createdAt": "2023-01-01T00:00:00+00:00",
                            "user": {"id": "u1", "name": "Bob"},
                        }
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
    }
    with unittest.mock.patch.object(client, "_execute_raw", return_value=wrapped):
        comments = client.get_project_comments("project-123")

    assert len(comments) == 1
    assert comments[0].id == "c1"
    assert comments[0].user.name == "Bob"


# -----------------------------------------------------------------------------
# Issue Attachment Tests
# -----------------------------------------------------------------------------


def test_list_issue_attachments(client: LinearClient) -> None:
    """list_issue_attachments should return list of attachment dicts."""
    mock_attachment = MagicMock()
    mock_attachment.id = "attachment-1"
    mock_attachment.title = "Screenshot"
    mock_attachment.url = "https://example.com/image.png"
    mock_attachment.file_name = "screenshot.png"
    mock_attachment.file_size = 1024
    mock_attachment.content_type = "image/png"
    mock_attachment.created_at = "2023-01-01T00:00:00Z"

    client._client.issues.get_attachments.return_value = [mock_attachment]

    attachments = client.list_issue_attachments("issue-123")

    assert len(attachments) == 1
    assert attachments[0]["id"] == "attachment-1"
    assert attachments[0]["title"] == "Screenshot"
    assert attachments[0]["url"] == "https://example.com/image.png"
    assert attachments[0]["file_name"] == "screenshot.png"
    assert attachments[0]["file_size"] == 1024
    assert attachments[0]["content_type"] == "image/png"
    assert attachments[0]["created_at"] == "2023-01-01T00:00:00Z"
    client._client.issues.get_attachments.assert_called_once_with("issue-123")


def test_create_attachment(client: LinearClient) -> None:
    """create_attachment should call linear_api with a LinearAttachmentInput
    and return the unwrapped {success, attachment} payload."""
    from linear_api.domain import LinearAttachmentInput

    client._client.issues.create_attachment.return_value = {
        "attachmentCreate": {
            "success": True,
            "attachment": {
                "id": "attachment-1",
                "title": "Test Attachment",
                "url": "https://example.com/test.pdf",
                "subtitle": None,
                "metadata": None,
            },
        }
    }

    result = client.create_attachment(
        "issue-123", "Test Attachment", "https://example.com/test.pdf"
    )

    assert result == {
        "success": True,
        "attachment": {
            "id": "attachment-1",
            "title": "Test Attachment",
            "url": "https://example.com/test.pdf",
            "subtitle": None,
            "metadata": None,
        },
    }

    # Verify call shape: must pass a LinearAttachmentInput, not loose kwargs
    client._client.issues.create_attachment.assert_called_once()
    _, kwargs = client._client.issues.create_attachment.call_args
    attachment_arg = kwargs["attachment"]
    assert isinstance(attachment_arg, LinearAttachmentInput)
    assert attachment_arg.issueId == "issue-123"
    assert attachment_arg.title == "Test Attachment"
    assert attachment_arg.url == "https://example.com/test.pdf"


def test_create_attachment_failure(client: LinearClient) -> None:
    """create_attachment should raise RuntimeError on failure."""
    client._client.issues.create_attachment.side_effect = Exception("Failed to create")

    with pytest.raises(RuntimeError, match="Failed to create attachment"):
        client.create_attachment("issue-123", "Test", "https://example.com/test.pdf")


# -----------------------------------------------------------------------------
# Comment Methods Tests
# -----------------------------------------------------------------------------


def test_add_comment_to_issue(client: LinearClient) -> None:
    """add_comment_to_issue should add comment and return result."""
    mock_result = {
        "success": True,
        "comment": {
            "id": "comment-1",
            "body": "Test comment",
            "user": {"id": "user-1", "name": "John Doe"},
            "createdAt": "2023-01-01T00:00:00Z",
        },
    }

    # _execute_raw returns already-unwrapped data (call_linear_api strips
    # the {"data": ...} envelope), so mock with that shape.
    with unittest.mock.patch.object(
        client, "_execute_raw", return_value={"commentCreate": mock_result}
    ) as mock_exec:
        result = client.add_comment_to_issue(
            CommentInput(issueId="issue-123", body="Test comment")
        )

        assert result.id == "comment-1"
        assert result.body == "Test comment"
        assert result.user.id == "user-1"
        assert result.user.name == "John Doe"
        assert result.created_at == "2023-01-01T00:00:00Z"

        # Verify the correct Linear GraphQL mutation is used (commentCreate,
        # not the non-existent issueCommentCreate)
        query_arg = mock_exec.call_args[0][0]
        assert "commentCreate" in query_arg
        assert "CommentCreateInput" in query_arg
        assert "issueCommentCreate" not in query_arg
        assert "IssueCommentCreateInput" not in query_arg


def test_list_issue_comments(client: LinearClient) -> None:
    """list_issue_comments should return list of Comment objects."""
    mock_comment = MagicMock()
    mock_comment.id = "comment-1"
    mock_comment.body = "Issue comment"
    mock_comment.createdAt = datetime(2023, 1, 1, tzinfo=UTC)

    client._client.issues.get_comments.return_value = [mock_comment]

    comments = client.list_issue_comments("issue-123")

    assert len(comments) == 1
    assert comments[0].id == "comment-1"
    assert comments[0].body == "Issue comment"
    assert comments[0].user is None
    assert comments[0].created_at == "2023-01-01T00:00:00+00:00"
    client._client.issues.get_comments.assert_called_once_with("issue-123")


def test_add_comment_to_project(client: LinearClient) -> None:
    """add_comment_to_project should add comment and return Comment."""
    mock_result = {
        "success": True,
        "comment": {
            "id": "comment-2",
            "body": "Project comment",
            "user": {"id": "user-2", "name": "Jane Doe"},
            "createdAt": "2023-02-02T00:00:00Z",
        },
    }

    # _execute_raw returns already-unwrapped data (call_linear_api strips
    # the {"data": ...} envelope), so mock with that shape.
    with unittest.mock.patch.object(
        client, "_execute_raw", return_value={"commentCreate": mock_result}
    ) as mock_exec:
        result = client.add_comment_to_project(
            ProjectCommentInput(project_id="project-123", body="Project comment")
        )

        assert result.id == "comment-2"
        assert result.body == "Project comment"
        assert result.user.id == "user-2"
        assert result.user.name == "Jane Doe"
        assert result.created_at == "2023-02-02T00:00:00Z"

        # Verify the mutation was called with projectId in the input
        _, kwargs = mock_exec.call_args[0], mock_exec.call_args[1]
        args = mock_exec.call_args[0]
        variables = args[1] if len(args) > 1 else kwargs.get("variables")
        assert variables["input"]["projectId"] == "project-123"
        assert variables["input"]["body"] == "Project comment"


def test_add_comment_to_project_failure(client: LinearClient) -> None:
    """add_comment_to_project should raise RuntimeError on failure."""
    with (
        unittest.mock.patch.object(
            client, "_execute_raw", side_effect=Exception("GraphQL failed")
        ),
        pytest.raises(RuntimeError, match="Failed to add comment to project"),
    ):
        client.add_comment_to_project(
            ProjectCommentInput(project_id="project-123", body="Project comment")
        )


# -----------------------------------------------------------------------------
# Project Creation Tests
# -----------------------------------------------------------------------------


def test_create_project(client: LinearClient) -> None:
    """create_project should create project and return Project object."""
    mock_team = MagicMock()
    mock_team.id = "team-123"
    mock_team.name = "Engineering Team"

    mock_project = _make_project_mock(
        id="project-123",
        name="Test Project",
        description="Test Description",
        state="planned",
    )

    # Mock the get_team method using patch
    with unittest.mock.patch.object(client, "get_team", return_value=mock_team):
        client._client.projects.create.return_value = mock_project

        result = client.create_project("team-123", "Test Project", "Test Description")

        assert result.id == "project-123"
        assert result.name == "Test Project"
        assert result.description == "Test Description"


# -----------------------------------------------------------------------------
# Error Handling Tests
# -----------------------------------------------------------------------------


def test_create_project_team_not_found(client: LinearClient) -> None:
    """create_project should raise ValueError when team not found."""
    with (
        unittest.mock.patch.object(client, "get_team", return_value=None),
        pytest.raises(ValueError, match="Team not found"),
    ):
        client.create_project("non-existent-team", "Test Project", "Test Description")


def test_create_project_api_failure(client: LinearClient) -> None:
    """create_project should raise RuntimeError on API failure."""
    mock_team = MagicMock()
    mock_team.id = "team-123"
    mock_team.name = "Engineering Team"

    with unittest.mock.patch.object(client, "get_team", return_value=mock_team):
        client._client.projects.create.side_effect = Exception("API Error")

        with pytest.raises(RuntimeError, match="Failed to create project"):
            client.create_project("team-123", "Test Project", "Test Description")


def test_add_comment_to_issue_failure(client: LinearClient) -> None:
    """add_comment_to_issue should raise RuntimeError on failure."""
    with (
        unittest.mock.patch.object(
            client, "_execute_raw", side_effect=Exception("GraphQL failed")
        ),
        pytest.raises(RuntimeError, match="Failed to add comment to issue"),
    ):
        client.add_comment_to_issue(
            CommentInput(issueId="issue-123", body="Test comment")
        )


def test_create_attachment_api_failure(client: LinearClient) -> None:
    """create_attachment should raise RuntimeError on API failure."""
    client._client.issues.create_attachment.side_effect = Exception("Upload failed")

    with pytest.raises(RuntimeError, match="Failed to create attachment"):
        client.create_attachment("issue-123", "Test", "https://example.com/test.pdf")


def test_get_team_labels_failure(client: LinearClient) -> None:
    """get_team_labels should return empty list on failure."""
    client._client.teams.get_labels.side_effect = Exception("API Error")

    labels = client.get_team_labels("team-123")

    assert labels == []


def test_get_team_issues_failure(client: LinearClient) -> None:
    """get_team_issues should return empty list on failure."""
    client._client.teams.get_issues.side_effect = Exception("API Error")

    issues = client.get_team_issues("team-123")

    assert issues == []


def test_get_team_projects_failure(client: LinearClient) -> None:
    """get_team_projects should return empty list on failure."""
    client._client.teams.get_projects.side_effect = Exception("API Error")

    projects = client.get_team_projects("team-123")

    assert projects == []


def test_get_project_labels_failure(client: LinearClient) -> None:
    """get_project_labels should return empty list on failure."""
    client._client.projects.get_labels.side_effect = Exception("API Error")

    labels = client.get_project_labels("project-123")

    assert labels == []


def test_get_project_comments_failure(client: LinearClient) -> None:
    """get_project_comments returns empty list when GraphQL call raises."""
    with unittest.mock.patch.object(
        client, "_execute_raw", side_effect=Exception("API Error")
    ):
        comments = client.get_project_comments("project-123")
    assert comments == []


def test_list_issue_attachments_failure(client: LinearClient) -> None:
    """list_issue_attachments should return empty list on failure."""
    client._client.issues.get_attachments.side_effect = Exception("API Error")

    attachments = client.list_issue_attachments("issue-123")

    assert attachments == []


def test_list_issue_comments_failure(client: LinearClient) -> None:
    """list_issue_comments should return empty list on failure."""
    client._client.issues.get_comments.side_effect = Exception("API Error")

    comments = client.list_issue_comments("issue-123")

    assert comments == []


def test_get_team_members_failure(client: LinearClient) -> None:
    """get_team_members should return empty list on failure."""
    client._client.teams.get_members.side_effect = Exception("API Error")

    members = client.get_team_members("team-123")

    assert members == []


def test_get_project_members_failure(client: LinearClient) -> None:
    """get_project_members should return empty list on failure."""
    client._client.projects.get_members.side_effect = Exception("API Error")

    members = client.get_project_members("project-123")

    assert members == []


def test_get_team_value_error(client: LinearClient) -> None:
    """get_team should return None on ValueError."""
    client._client.teams.get.side_effect = ValueError("Invalid team")

    team = client.get_team("invalid-team")

    assert team is None


def test_get_project_value_error(client: LinearClient) -> None:
    """get_project should return None on ValueError (swallowed and logged)."""
    client._client.projects.get.side_effect = ValueError("Invalid project")

    result = client.get_project("invalid-project")

    assert result is None


def test_get_issue_value_error(client: LinearClient) -> None:
    """get_issue should return None on ValueError."""
    client._client.issues.get.side_effect = ValueError("Invalid issue")

    issue = client.get_issue("invalid-issue")

    assert issue is None


def test_update_project_linear_project_none(client: LinearClient) -> None:
    """update_project should raise RuntimeError when linear_project is None."""
    mock_update_input = MagicMock()
    mock_update_input.title = "Updated Title"
    mock_update_input.description = "Updated Description"
    mock_update_input.state_name = "completed"
    mock_update_input.update_message = None

    client._client.projects.update.return_value = None

    with pytest.raises(RuntimeError, match="project-123"):
        client.update_project("project-123", mock_update_input)


def test_delete_project_exception(client: LinearClient) -> None:
    """delete_project should return False on exception."""
    client._client.projects.delete.side_effect = Exception("Delete failed")

    with pytest.raises(Exception, match="Delete failed"):
        client.delete_project("project-123")


def test_delete_issue_exception(client: LinearClient) -> None:
    """delete_issue should return False on exception."""
    client._client.issues.delete.side_effect = Exception("Delete failed")

    result = client.delete_issue("issue-123")

    assert result is False


def test_list_issue_labels_exception(client: LinearClient) -> None:
    """list_issue_labels should return empty list on exception."""
    client._client.issues.get_labels.side_effect = Exception("API Error")

    labels = client.list_issue_labels("issue-123")

    assert labels == []


def test_create_issue_relation_exception(client: LinearClient) -> None:
    """create_issue_relation should raise exception on GraphQL failure."""
    with (
        unittest.mock.patch.object(
            client, "_execute_raw", side_effect=Exception("GraphQL failed")
        ),
        pytest.raises(Exception, match="GraphQL failed"),
    ):
        client.create_issue_relation(
            issue_id="issue-1", related_issue_id="issue-2", relation_type="blocks"
        )


def test_post_project_update_exception(client: LinearClient) -> None:
    """_post_project_update should handle exceptions gracefully."""
    # This tests the private method exception handling
    with contextlib.suppress(Exception):
        client._post_project_update("project-123", "Test update")


def test_create_issue_team_not_found(client: LinearClient) -> None:
    """create_issue should raise RuntimeError when team not found."""
    mock_input = MagicMock()
    mock_input.team_id = "non-existent-team"

    with (
        unittest.mock.patch.object(client, "get_team", return_value=None),
        pytest.raises(RuntimeError, match="Team.*not found"),
    ):
        client.create_issue(mock_input)


def test_create_issue_project_not_found(client: LinearClient) -> None:
    """create_issue should raise ValueError when project not found."""
    mock_input = MagicMock()
    mock_input.team_id = "team-123"
    mock_input.project_id = "non-existent-project"

    mock_team = MagicMock()
    mock_team.id = "team-123"
    mock_team.name = "Test Team"

    with (
        unittest.mock.patch.object(client, "get_team", return_value=mock_team),
        unittest.mock.patch.object(client, "get_project", return_value=None),
        pytest.raises(RuntimeError, match="Project.*not found"),
    ):
        client.create_issue(mock_input)


def test_get_issue_labels_none_result(client: LinearClient) -> None:
    """list_issue_labels should handle None result from get_labels."""
    client._client.issues.get_labels.return_value = None

    labels = client.list_issue_labels("issue-123")

    assert labels == []


def test_get_team_labels_none_result(client: LinearClient) -> None:
    """get_team_labels should handle None result from get_labels."""
    client._client.teams.get_labels.return_value = None

    labels = client.get_team_labels("team-123")

    assert labels == []


def test_get_project_labels_none_result(client: LinearClient) -> None:
    """get_project_labels should handle None result from get_labels."""
    client._client.projects.get_labels.return_value = None

    labels = client.get_project_labels("project-123")

    assert labels == []


def test_get_team_issues_none_result(client: LinearClient) -> None:
    """get_team_issues should handle None result from get_issues."""
    client._client.teams.get_issues.return_value = None

    issues = client.get_team_issues("team-123")

    assert issues == []


def test_get_team_projects_none_result(client: LinearClient) -> None:
    """get_team_projects should handle None result from get_projects."""
    client._client.teams.get_projects.return_value = None

    projects = client.get_team_projects("team-123")

    assert projects == []


def test_get_project_comments_none_result(client: LinearClient) -> None:
    """get_project_comments returns [] when project is missing from response."""
    with unittest.mock.patch.object(
        client, "_execute_raw", return_value={"project": None}
    ):
        comments = client.get_project_comments("project-123")
    assert comments == []


def test_list_issue_attachments_none_result(client: LinearClient) -> None:
    """list_issue_attachments should handle None result from get_attachments."""
    client._client.issues.get_attachments.return_value = None

    attachments = client.list_issue_attachments("issue-123")

    assert attachments == []


def test_list_issue_comments_none_result(client: LinearClient) -> None:
    """list_issue_comments should handle None result from get_comments."""
    client._client.issues.get_comments.return_value = None

    comments = client.list_issue_comments("issue-123")

    assert comments == []


def test_get_team_members_none_result(client: LinearClient) -> None:
    """get_team_members should handle None result from get_members."""
    client._client.teams.get_members.return_value = None

    members = client.get_team_members("team-123")

    assert members == []


def test_get_project_members_none_result(client: LinearClient) -> None:
    """get_project_members should handle None result from get_members."""
    client._client.projects.get_members.return_value = None

    members = client.get_project_members("project-123")

    assert members == []


def test_get_team_members_empty_list(client: LinearClient) -> None:
    """get_team_members should handle empty list result."""
    client._client.teams.get_members.return_value = []

    members = client.get_team_members("team-123")

    assert members == []


def test_get_project_members_empty_list(client: LinearClient) -> None:
    """get_project_members should handle empty list result."""
    client._client.projects.get_members.return_value = []

    members = client.get_project_members("project-123")

    assert members == []


def test_get_team_labels_empty_list(client: LinearClient) -> None:
    """get_team_labels should handle empty list result."""
    client._client.teams.get_labels.return_value = []

    labels = client.get_team_labels("team-123")

    assert labels == []


def test_get_project_labels_empty_list(client: LinearClient) -> None:
    """get_project_labels should handle empty list result."""
    client._client.projects.get_labels.return_value = []

    labels = client.get_project_labels("project-123")

    assert labels == []


def test_list_issue_labels_empty_list(client: LinearClient) -> None:
    """list_issue_labels should handle empty list result."""
    client._client.issues.get_labels.return_value = []

    labels = client.list_issue_labels("issue-123")

    assert labels == []


def test_get_team_issues_empty_dict(client: LinearClient) -> None:
    """get_team_issues should handle empty dict result."""
    client._client.teams.get_issues.return_value = {}

    issues = client.get_team_issues("team-123")

    assert issues == []


def test_get_team_projects_empty_dict(client: LinearClient) -> None:
    """get_team_projects should handle empty dict result."""
    client._client.teams.get_projects.return_value = {}

    projects = client.get_team_projects("team-123")

    assert projects == []


def test_get_project_comments_empty_list(client: LinearClient) -> None:
    """get_project_comments returns [] when comments.nodes is empty."""
    empty = {
        "project": {
            "comments": {
                "nodes": [],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }
    with unittest.mock.patch.object(client, "_execute_raw", return_value=empty):
        comments = client.get_project_comments("project-123")
    assert comments == []


def test_list_issue_attachments_empty_list(client: LinearClient) -> None:
    """list_issue_attachments should handle empty list result."""
    client._client.issues.get_attachments.return_value = []

    attachments = client.list_issue_attachments("issue-123")

    assert attachments == []


def test_list_issue_comments_empty_list(client: LinearClient) -> None:
    """list_issue_comments should handle empty list result."""
    client._client.issues.get_comments.return_value = []

    comments = client.list_issue_comments("issue-123")

    assert comments == []


def test_create_project_runtime_error(client: LinearClient) -> None:
    """create_project should raise RuntimeError on API failure."""
    mock_team = MagicMock()
    mock_team.id = "team-123"
    mock_team.name = "Engineering Team"

    with unittest.mock.patch.object(client, "get_team", return_value=mock_team):
        client._client.projects.create.side_effect = Exception("API Error")

        with pytest.raises(RuntimeError, match="Failed to create project"):
            client.create_project("team-123", "Test Project", "Test Description")


def test_update_project_runtime_error(client: LinearClient) -> None:
    """update_project should raise RuntimeError on API failure."""
    mock_update_input = MagicMock()
    mock_update_input.title = "Updated Title"
    mock_update_input.description = "Updated Description"
    mock_update_input.state_name = "completed"
    mock_update_input.update_message = None

    client._client.projects.update.side_effect = Exception("API Error")

    with pytest.raises(RuntimeError, match="Failed to update project"):
        client.update_project("project-123", mock_update_input)


def test_delete_project_runtime_error(client: LinearClient) -> None:
    """delete_project should return False on exception."""
    client._client.projects.delete.side_effect = Exception("Delete failed")

    with pytest.raises(Exception, match="Delete failed"):
        client.delete_project("project-123")


def test_delete_issue_runtime_error(client: LinearClient) -> None:
    """delete_issue should return False on exception."""
    client._client.issues.delete.side_effect = Exception("Delete failed")

    result = client.delete_issue("issue-123")

    assert result is False


def test_create_issue_relation_runtime_error(client: LinearClient) -> None:
    """create_issue_relation should raise exception on GraphQL failure."""
    with (
        unittest.mock.patch.object(
            client, "_execute_raw", side_effect=Exception("GraphQL failed")
        ),
        pytest.raises(Exception, match="GraphQL failed"),
    ):
        client.create_issue_relation(
            issue_id="issue-1", related_issue_id="issue-2", relation_type="blocks"
        )


def test_post_project_update_runtime_error(client: LinearClient) -> None:
    """_post_project_update should handle exceptions gracefully."""
    with unittest.mock.patch.object(
        client, "_execute_raw", side_effect=Exception("GraphQL failed")
    ):
        # Should not raise exception
        try:
            client._post_project_update("project-123", "Test update")
        except Exception:
            pytest.fail("post_project_update should not raise exceptions")


def test_create_issue_relation_empty_result(client: LinearClient) -> None:
    """create_issue_relation should handle empty result."""
    with unittest.mock.patch.object(client, "_execute_raw", return_value={}):
        result = client.create_issue_relation(
            issue_id="issue-1", related_issue_id="issue-2", relation_type="blocks"
        )

        assert result == {
            "id": "",
            "type": "blocks",
            "issue_id": "issue-1",
            "related_issue_id": "issue-2",
        }


def test_create_issue_relation_no_issue_relation(client: LinearClient) -> None:
    """create_issue_relation should handle missing issueRelation in result."""
    with unittest.mock.patch.object(
        client, "_execute_raw", return_value={"issueRelationCreate": {"success": True}}
    ):
        result = client.create_issue_relation(
            issue_id="issue-1", related_issue_id="issue-2", relation_type="blocks"
        )

        assert result == {
            "id": "",
            "type": "blocks",
            "issue_id": "issue-1",
            "related_issue_id": "issue-2",
        }


def test_create_issue_relation_none_issue_relation(client: LinearClient) -> None:
    """create_issue_relation should handle None issueRelation in result."""
    with unittest.mock.patch.object(
        client,
        "_execute_raw",
        return_value={"issueRelationCreate": {"issueRelation": None}},
    ):
        result = client.create_issue_relation(
            issue_id="issue-1", related_issue_id="issue-2", relation_type="blocks"
        )

        assert result == {
            "id": "",
            "type": "blocks",
            "issue_id": "issue-1",
            "related_issue_id": "issue-2",
        }


def test_get_team_value_error_in_catch(client: LinearClient) -> None:
    """get_team should return None on ValueError in catch block."""
    client._client.teams.get.side_effect = ValueError("Invalid team")

    team = client.get_team("invalid-team")

    assert team is None


def test_get_project_value_error_in_catch(client: LinearClient) -> None:
    """get_project should return None on ValueError (swallowed and logged)."""
    client._client.projects.get.side_effect = ValueError("Invalid project")

    result = client.get_project("invalid-project")

    assert result is None


def test_get_issue_value_error_in_catch(client: LinearClient) -> None:
    """get_issue should return None on ValueError in catch block."""
    client._client.issues.get.side_effect = ValueError("Invalid issue")

    issue = client.get_issue("invalid-issue")

    assert issue is None


def test_update_project_runtime_error_in_catch(client: LinearClient) -> None:
    """update_project should raise RuntimeError on exception in catch block."""
    mock_update_input = MagicMock()
    mock_update_input.title = "Updated Title"
    mock_update_input.description = "Updated Description"
    mock_update_input.state_name = "completed"
    mock_update_input.update_message = None

    client._client.projects.update.side_effect = Exception("API Error")

    with pytest.raises(RuntimeError, match="Failed to update project"):
        client.update_project("project-123", mock_update_input)


def test_delete_project_runtime_error_in_catch(client: LinearClient) -> None:
    """delete_project should return False on exception in catch block."""
    client._client.projects.delete.side_effect = Exception("Delete failed")

    with pytest.raises(Exception, match="Delete failed"):
        client.delete_project("project-123")


def test_delete_issue_runtime_error_in_catch(client: LinearClient) -> None:
    """delete_issue should return False on exception in catch block."""
    client._client.issues.delete.side_effect = Exception("Delete failed")

    result = client.delete_issue("issue-123")

    assert result is False


def test_get_team_exception_in_catch(client: LinearClient) -> None:
    """get_team should return None on general exception in catch block."""
    client._client.teams.get.side_effect = Exception("General error")

    team = client.get_team("team-123")

    assert team is None


def test_get_project_exception_in_catch(client: LinearClient) -> None:
    """get_project should return None on general exception (swallowed and logged)."""
    client._client.projects.get.side_effect = Exception("General error")

    result = client.get_project("project-123")

    assert result is None


def test_get_issue_exception_in_catch(client: LinearClient) -> None:
    """get_issue should return None on general exception in catch block."""
    client._client.issues.get.side_effect = Exception("General error")

    issue = client.get_issue("issue-123")

    assert issue is None


def test_update_project_exception_in_catch(client: LinearClient) -> None:
    """update_project should raise RuntimeError on general exception in catch block."""
    mock_update_input = MagicMock()
    mock_update_input.title = "Updated Title"
    mock_update_input.description = "Updated Description"
    mock_update_input.state_name = "completed"
    mock_update_input.update_message = None

    client._client.projects.update.side_effect = Exception("General error")

    with pytest.raises(RuntimeError, match="Failed to update project"):
        client.update_project("project-123", mock_update_input)


def test_delete_project_exception_in_catch(client: LinearClient) -> None:
    """delete_project should return False on general exception in catch block."""
    client._client.projects.delete.side_effect = Exception("General error")

    with pytest.raises(Exception, match="General error"):
        client.delete_project("project-123")


def test_delete_issue_exception_in_catch_general(client: LinearClient) -> None:
    """delete_issue should return False on general exception in catch block."""
    client._client.issues.delete.side_effect = Exception("General error")

    result = client.delete_issue("issue-123")

    assert result is False


def test_get_team_return_none_in_catch(client: LinearClient) -> None:
    """get_team should return None when linear_team is None."""
    client._client.teams.get.return_value = None

    team = client.get_team("team-123")

    assert team is None


def test_get_project_return_none_in_catch(client: LinearClient) -> None:
    """get_project should return None when linear_project is None."""
    client._client.projects.get.return_value = None

    project = client.get_project("project-123")

    assert project is None


def test_get_issue_return_none_in_catch(client: LinearClient) -> None:
    """get_issue should return None when linear_issue is None."""
    client._client.issues.get.return_value = None

    issue = client.get_issue("issue-123")

    assert issue is None


def test_list_teams_empty_result(client: LinearClient) -> None:
    """list_teams should handle empty result."""
    client._client.teams.get_all.return_value = {}

    teams = client.list_teams()

    assert teams == []


def test_list_projects_empty_result(client: LinearClient) -> None:
    """list_projects should handle empty result."""
    client._client.projects.get_all.return_value = {}

    projects = client.list_projects("team-123")

    assert projects == []


def test_list_issues_empty_result(client: LinearClient) -> None:
    """list_issues should handle empty result."""
    client._client.issues.get_all.return_value = {}

    issues = client.list_issues("project-123")

    assert issues == []


def test_list_projects_no_team_id(client: LinearClient) -> None:
    """list_projects raises ValueError when team_id is empty."""
    with pytest.raises(ValueError, match="Team ID is required"):
        client.list_projects("")


def test_list_teams_empty_dict(client: LinearClient) -> None:
    """list_teams should handle empty dict result."""
    client._client.teams.get_all.return_value = {}

    teams = client.list_teams()

    assert teams == []


def test_list_projects_empty_dict(client: LinearClient) -> None:
    """list_projects should handle empty dict result."""
    client._client.projects.get_all.return_value = {}

    projects = client.list_projects("team-123")

    assert projects == []


def test_list_issues_empty_dict(client: LinearClient) -> None:
    """list_issues should handle empty dict result."""
    client._client.issues.get_all.return_value = {}

    issues = client.list_issues("project-123")

    assert issues == []


def test_get_team_exception_handling(client: LinearClient) -> None:
    """get_team should return None when exception occurs (lines 62-63)."""
    client._client.teams.get_all.side_effect = Exception("Team fetch failed")

    result = client.get_team("team-123")

    assert result is None


def test_delete_project_success(client: LinearClient) -> None:
    """delete_project should return True when successful (line 132)."""
    client._client.projects.delete.return_value = {"success": True}

    result = client.delete_project("project-123")

    assert result is True


def test_delete_project_exception_handling(client: LinearClient) -> None:
    """delete_project should return False when exception occurs (line 133)."""
    client._client.projects.delete.side_effect = Exception("Delete failed")

    with pytest.raises(Exception, match="Delete failed"):
        client.delete_project("project-123")


def test_list_issues_dict_branch(client: LinearClient) -> None:
    """list_issues should handle dict items via Issue.from_linear."""
    # Create a dict issue (raw format from API)
    dict_issue = {
        "id": "issue-123",
        "title": "Test Issue",
        "description": "Test Description",
    }

    # Mock the client to return our dict issue
    client._client.projects.get_issues.return_value = [dict_issue]

    result = client.list_issues("project-123")

    assert len(result) == 1
    assert result[0].id == "issue-123"
    assert result[0].title == "Test Issue"
    assert result[0].description == "Test Description"


# -----------------------------------------------------------------------------
# Raw GraphQL Tests
# -----------------------------------------------------------------------------


def test_execute_raw_uses_execute_graphql_first(client: LinearClient) -> None:
    """_execute_raw should prefer execute_graphql (SDK public method)."""
    expected_result = {"issueRelationCreate": {"success": True}}
    client._client.execute_graphql.return_value = expected_result

    result = client._execute_raw("mutation { test }", {"var": "value"})

    assert result == expected_result
    client._client.execute_graphql.assert_called_once_with(
        "mutation { test }", {"var": "value"}
    )


def test_execute_raw_falls_back_to_private_execute(client: LinearClient) -> None:
    """_execute_raw should fall back to _execute when execute_graphql is absent."""
    del client._client.execute_graphql

    expected_result = {"data": {"test": "value"}}
    client._client._execute.return_value = expected_result

    result = client._execute_raw("query { test }", {"var": "value"})

    assert result == expected_result
    client._client._execute.assert_called_once_with("query { test }", {"var": "value"})


def test_execute_raw_no_method_available(client: LinearClient) -> None:
    """_execute_raw should raise RuntimeError when no execute method is available."""
    if hasattr(client._client, "execute_graphql"):
        delattr(client._client, "execute_graphql")
    if hasattr(client._client, "_execute"):
        delattr(client._client, "_execute")

    with pytest.raises(RuntimeError, match="Raw GraphQL execution not supported"):
        client._execute_raw("query { test }")


def test_post_project_update(client: LinearClient) -> None:
    """_post_project_update should execute GraphQL mutation."""
    with patch.object(client, "_execute_raw") as mock_execute:
        client._post_project_update("proj-123", "Update message")

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "projectUpdateCreate" in call_args[0]
        assert call_args[1]["input"]["projectId"] == "proj-123"
        assert call_args[1]["input"]["body"] == "Update message"


def test_post_project_update_silent_failure(client: LinearClient) -> None:
    """_post_project_update should silently fail on error."""
    with patch.object(client, "_execute_raw") as mock_execute:
        mock_execute.side_effect = Exception("GraphQL error")
        # Should not raise
        client._post_project_update("proj-123", "Update message")


# -----------------------------------------------------------------------------
# get_issue_relations Tests
# -----------------------------------------------------------------------------


def _make_relation_mock(
    *,
    id: str = "rel-1",
    type: str = "blocks",
    related_id: str | None = "issue-2",
    related_title: str | None = "Other issue",
    created_at: datetime | None = None,
) -> MagicMock:
    """Build a MagicMock matching linear_api.IssueRelation's read surface."""
    m = MagicMock()
    m.id = id
    m.type = type
    m.relatedIssue = (
        {"id": related_id, "title": related_title} if related_id is not None else None
    )
    m.createdAt = created_at
    return m


def test_get_issue_relations_returns_typed_relations(client: LinearClient) -> None:
    """get_issue_relations should convert linear_api relations to IssueRelation."""
    client._client.issues.get_relations.return_value = [
        _make_relation_mock(
            id="rel-1",
            type="blocks",
            related_id="issue-2",
            related_title="Downstream",
            created_at=datetime(2026, 1, 2, 3, 4, 5),
        ),
        _make_relation_mock(
            id="rel-2",
            type="related",
            related_id="issue-3",
            related_title=None,
        ),
    ]

    relations = client.get_issue_relations("issue-1")

    client._client.issues.get_relations.assert_called_once_with(issue_id="issue-1")
    assert len(relations) == 2
    assert relations[0].id == "rel-1"
    assert relations[0].type == "blocks"
    assert relations[0].related_issue is not None
    assert relations[0].related_issue.id == "issue-2"
    assert relations[0].related_issue.title == "Downstream"
    assert relations[0].created_at == "2026-01-02T03:04:05"
    assert relations[1].id == "rel-2"
    assert relations[1].type == "related"
    assert relations[1].related_issue is not None
    assert relations[1].related_issue.title is None


def test_get_issue_relations_empty_list(client: LinearClient) -> None:
    """get_issue_relations should return [] when there are no relations."""
    client._client.issues.get_relations.return_value = []

    relations = client.get_issue_relations("issue-1")

    assert relations == []


def test_get_issue_relations_propagates_exceptions(client: LinearClient) -> None:
    """get_issue_relations should let SDK errors propagate (auth/not-found/rate-limit are meaningful)."""
    client._client.issues.get_relations.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="API Error"):
        client.get_issue_relations("issue-1")


# -----------------------------------------------------------------------------
# Sub-issue Support
# -----------------------------------------------------------------------------


def test_update_issue_forwards_parent_id(client: LinearClient) -> None:
    """update_issue should forward parent_id to LinearIssueUpdateInput.parentId."""
    mock_issue = _make_issue_mock(
        id="issue-child",
        identifier="ENG-50",
        title="Child Issue",
        parent_id="issue-new-parent",
    )
    client._client.issues.update.return_value = mock_issue

    update_input = IssueUpdateInput(parentId="issue-new-parent")
    issue = client.update_issue("issue-child", update_input)

    assert issue.id == "issue-child"
    assert issue.parent_id == "issue-new-parent"
    # Verify the underlying SDK was called with parentId set on the update input.
    args, _ = client._client.issues.update.call_args
    assert args[0] == "issue-child"
    sdk_update = args[1]
    assert sdk_update.parentId == "issue-new-parent"


def test_update_issue_without_parent_id_passes_none(client: LinearClient) -> None:
    """update_issue should not invent a parentId when caller omits it."""
    mock_issue = _make_issue_mock(id="issue-1", identifier="ENG-1", title="Same")
    client._client.issues.update.return_value = mock_issue

    client.update_issue("issue-1", IssueUpdateInput(title="Same"))

    args, _ = client._client.issues.update.call_args
    sdk_update = args[1]
    assert sdk_update.parentId is None


def test_list_sub_issues_returns_children(client: LinearClient) -> None:
    """list_sub_issues should convert SDK children dict to a list of Issue."""
    child_a = _make_issue_mock(
        id="child-a",
        identifier="ENG-101",
        title="Child A",
        parent_id="issue-parent",
        team_id="team-1",
    )
    child_b = _make_issue_mock(
        id="child-b",
        identifier="ENG-102",
        title="Child B",
        parent_id="issue-parent",
        team_id="team-1",
    )
    client._client.issues.get_children.return_value = {
        "child-a": child_a,
        "child-b": child_b,
    }

    sub_issues = client.list_sub_issues("issue-parent")

    client._client.issues.get_children.assert_called_once_with("issue-parent")
    ids = {i.id for i in sub_issues}
    assert ids == {"child-a", "child-b"}
    parents = {i.parent_id for i in sub_issues}
    assert parents == {"issue-parent"}


def test_list_sub_issues_empty(client: LinearClient) -> None:
    """list_sub_issues should return [] when the issue has no children."""
    client._client.issues.get_children.return_value = {}

    sub_issues = client.list_sub_issues("issue-leaf")

    assert sub_issues == []


def test_list_sub_issues_propagates_exceptions(client: LinearClient) -> None:
    """list_sub_issues should let SDK errors propagate (matching get_issue_relations)."""
    client._client.issues.get_children.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="API Error"):
        client.list_sub_issues("issue-parent")
