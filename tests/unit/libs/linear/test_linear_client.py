"""Unit tests for libs.linear.linear_client.

Tests LinearClient with mocked linear_api dependency.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from libs.linear.linear_client import LinearClient
from libs.linear.schemas import (
    IssueInput,
    IssueLabelInput,
    IssueUpdateInput,
    Priority,
    ProjectUpdateInput,
)


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
    with pytest.raises(RuntimeError, match="Linear API key required"):
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
    mock_project1 = MagicMock()
    mock_project1.id = "proj-1"
    mock_project1.name = "Sprint 1"
    mock_project1.team_id = "team-123"
    mock_project1.state = "started"
    mock_project1.description = "First sprint"

    mock_project2 = MagicMock()
    mock_project2.id = "proj-2"
    mock_project2.name = "Sprint 2"
    mock_project2.team_id = "team-123"
    mock_project2.state = "planned"
    mock_project2.description = None

    client._client.projects.get_all.return_value = {
        "proj-1": mock_project1,
        "proj-2": mock_project2,
    }

    projects = client.list_projects("team-123")

    assert len(projects) == 2
    assert projects[0].id == "proj-1"
    assert projects[0].team_id == "team-123"
    client._client.projects.get_all.assert_called_once_with(team_id="team-123")


def test_list_projects_empty_team_id(client: LinearClient) -> None:
    """list_projects should return empty list for empty team_id."""
    projects = client.list_projects("")

    assert projects == []
    client._client.projects.get_all.assert_not_called()


def test_get_project_success(client: LinearClient) -> None:
    """get_project should return Project when found."""
    mock_project = MagicMock()
    mock_project.id = "proj-123"
    mock_project.name = "Sprint 1"
    mock_project.team_id = "team-456"
    mock_project.state = "started"
    mock_project.description = None

    client._client.projects.get.return_value = mock_project

    project = client.get_project("proj-123")

    assert project is not None
    assert project.id == "proj-123"
    assert project.name == "Sprint 1"


def test_get_project_not_found(client: LinearClient) -> None:
    """get_project should return None when project not found."""
    client._client.projects.get.side_effect = Exception("Not found")

    project = client.get_project("non-existent")

    assert project is None


def test_update_project(client: LinearClient) -> None:
    """update_project should update project fields."""
    mock_project = MagicMock()
    mock_project.id = "proj-123"
    mock_project.name = "Updated Name"
    mock_project.team_id = "team-456"
    mock_project.state = "completed"
    mock_project.description = "Updated description"

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
    mock_project = MagicMock()
    mock_project.id = "proj-123"
    mock_project.name = "Project"
    mock_project.team_id = "team-456"
    mock_project.description = None
    mock_project.state = None

    client._client.projects.get.return_value = mock_project

    update_input = ProjectUpdateInput(updateMessage="Project shipped!")

    # Mock _post_project_update to avoid GraphQL call
    with patch.object(client, "_post_project_update") as mock_post:
        client.update_project("proj-123", update_input)
        mock_post.assert_called_once_with("proj-123", "Project shipped!")


def test_update_project_error(client: LinearClient) -> None:
    """update_project should raise RuntimeError on failure."""
    client._client.projects.update.side_effect = Exception("API Error")

    update_input = ProjectUpdateInput(name="New Name")

    with pytest.raises(RuntimeError, match="Failed to update project"):
        client.update_project("proj-123", update_input)


def test_post_project_update_logs_on_failure(
    client: LinearClient, caplog: pytest.LogCaptureFixture
) -> None:
    """_post_project_update is best-effort but must log the cause so a
    failed GraphQL mutation isn't invisible to callers."""
    import logging

    # Force the raw GraphQL path to fail.
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
    mock_issue1 = MagicMock()
    mock_issue1.id = "issue-1"
    mock_issue1.identifier = "ENG-1"
    mock_issue1.title = "Bug fix"
    mock_issue1.description = "Fix the bug"
    mock_state1 = MagicMock()
    mock_state1.id = "state-1"
    mock_state1.name = "in_progress"
    mock_state1.color = "#00f"
    mock_state1.type = "started"
    mock_issue1.state = mock_state1
    mock_issue1.priority = 2
    mock_issue1.team_id = "team-123"
    mock_issue1.project_id = "proj-456"
    mock_issue1.parent_id = None
    mock_issue1.url = "https://linear.app/issue/ENG-1"
    mock_issue1.created_at = "2024-01-01"
    mock_issue1.updated_at = "2024-01-02"

    mock_issue2 = MagicMock()
    mock_issue2.id = "issue-2"
    mock_issue2.identifier = "ENG-2"
    mock_issue2.title = "Feature"
    mock_issue2.description = None
    mock_issue2.state = None
    mock_issue2.priority = 3
    mock_issue2.team_id = None
    mock_issue2.project_id = None
    mock_issue2.parent_id = None
    mock_issue2.url = "https://linear.app/issue/ENG-2"
    mock_issue2.created_at = None
    mock_issue2.updated_at = None

    client._client.projects.get_issues.return_value = [mock_issue1, mock_issue2]

    issues = client.list_issues("proj-456")

    assert len(issues) == 2
    assert issues[0].id == "issue-1"
    assert issues[0].identifier == "ENG-1"
    assert issues[0].state.name == "in_progress"  # IssueState object
    assert issues[1].id == "issue-2"
    assert issues[1].state is None
    client._client.projects.get_issues.assert_called_once_with(project_id="proj-456")


def test_get_issue_success(client: LinearClient) -> None:
    """get_issue should return Issue when found."""
    mock_issue = MagicMock()
    mock_issue.id = "issue-123"
    mock_issue.identifier = "ENG-42"
    mock_issue.title = "Test Issue"
    mock_issue.description = "Description"
    mock_state = MagicMock()
    mock_state.id = "state-backlog"
    mock_state.name = "backlog"
    mock_state.color = "#ccc"
    mock_state.type = "backlog"
    mock_issue.state = mock_state
    mock_issue.priority = 1
    mock_issue.team_id = None
    mock_issue.project_id = None
    mock_issue.parent_id = None
    mock_issue.url = "https://linear.app/issue/ENG-42"
    mock_issue.created_at = None
    mock_issue.updated_at = None

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
    mock_issue.priority = 4
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
    assert issue.priority == 4
    assert issue.state.name == "completed"
    client._client.issues.update.assert_called_once()
    # IssueUpdateInput.state must be forwarded as stateName (linear-api
    # resolves the workflow state name to an ID internally).
    sent_update = client._client.issues.update.call_args.args[1]
    assert sent_update.stateName == "completed"


def test_delete_issue_success(client: LinearClient) -> None:
    """delete_issue should return True on success."""
    client._client.issues.delete.return_value = None

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


def test_add_label_to_issue(client: LinearClient) -> None:
    """add_label_to_issue should add label and return updated Issue."""
    mock_issue = MagicMock()
    mock_issue.id = "issue-123"
    mock_issue.identifier = "ENG-42"
    mock_issue.title = "Issue with label"
    mock_issue.description = None
    mock_issue.labels = []
    mock_issue.state = None
    mock_issue.priority = 2
    mock_issue.team_id = None
    mock_issue.project_id = None
    mock_issue.parent_id = None
    mock_issue.url = "https://linear.app/issue/ENG-42"
    mock_issue.created_at = None
    mock_issue.updated_at = None

    client._client.issues.add_label.return_value = mock_issue

    input_data = IssueLabelInput(issueId="issue-123", labelName="bug")

    issue = client.add_label_to_issue(input_data)

    assert issue.id == "issue-123"
    client._client.issues.add_label.assert_called_once_with(
        issue_id="issue-123",
        label="bug",
    )


def test_add_label_to_issue_error(client: LinearClient) -> None:
    """add_label_to_issue should raise RuntimeError on failure."""
    client._client.issues.add_label.side_effect = Exception("Label add failed")

    input_data = IssueLabelInput(issueId="issue-123", labelName="bug")

    with pytest.raises(RuntimeError, match="Failed to add label to issue"):
        client.add_label_to_issue(input_data)


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

    client._client.issues.get.return_value = mock_issue

    labels = client.list_issue_labels("issue-123")

    assert len(labels) == 2
    assert labels[0].name == "bug"
    assert labels[1].name == "urgent"


def test_list_issue_labels_no_labels(client: LinearClient) -> None:
    """list_issue_labels should return empty list when issue has no labels."""
    mock_issue = MagicMock()
    mock_issue.id = "issue-123"
    mock_issue.identifier = "ENG-42"
    mock_issue.title = "Issue"
    mock_issue.description = None
    mock_issue.labels = []
    mock_issue.state = None
    mock_issue.priority = 2
    mock_issue.team_id = None
    mock_issue.project_id = None
    mock_issue.parent_id = None
    mock_issue.url = "https://linear.app/issue/ENG-42"
    mock_issue.created_at = None
    mock_issue.updated_at = None

    client._client.issues.get.return_value = mock_issue

    labels = client.list_issue_labels("issue-123")

    assert labels == []


def test_list_issue_labels_issue_not_found(client: LinearClient) -> None:
    """list_issue_labels should return empty list when issue not found."""
    client._client.issues.get.side_effect = Exception("Not found")

    labels = client.list_issue_labels("non-existent")

    assert labels == []


# -----------------------------------------------------------------------------
# Raw GraphQL Tests
# -----------------------------------------------------------------------------


def test_execute_raw_with_internal_method(client: LinearClient) -> None:
    """_execute_raw should use internal _execute method if available."""
    expected_result = {"data": {"test": "value"}}
    client._client._execute.return_value = expected_result

    result = client._execute_raw("query { test }", {"var": "value"})

    assert result == expected_result
    client._client._execute.assert_called_once_with("query { test }", {"var": "value"})


def test_execute_raw_with_public_method(client: LinearClient) -> None:
    """_execute_raw should fallback to public execute method."""
    del client._client._execute  # Remove _execute

    expected_result = {"data": {"test": "value"}}
    client._client.execute.return_value = expected_result

    result = client._execute_raw("query { test }", {"var": "value"})

    assert result == expected_result


def test_execute_raw_no_method_available(client: LinearClient) -> None:
    """_execute_raw should raise RuntimeError when no execute method available."""
    # Remove both execute methods
    if hasattr(client._client, "_execute"):
        delattr(client._client, "_execute")
    if hasattr(client._client, "execute"):
        delattr(client._client, "execute")

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
