"""Unit tests for tools.linear module.

Tests LinearTools with mocked libs.linear.LinearClient.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.linear import LinearTools


@pytest.fixture
def mock_linear_client() -> MagicMock:
    """Create a mock LinearClient."""
    with patch("tools.linear.LinearClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def linear_tools(mock_linear_client: MagicMock) -> LinearTools:
    """Create LinearTools with mocked client."""
    return LinearTools(api_key="test-api-key")


# -----------------------------------------------------------------------------
# Initialization Tests
# -----------------------------------------------------------------------------


def test_linear_tools_initialization() -> None:
    """LinearTools should initialize with API key."""
    with patch("tools.linear.LinearClient") as MockClient:
        MockClient.return_value = MagicMock()
        LinearTools(api_key="test-key")
        MockClient.assert_called_once_with(api_key="test-key")


# -----------------------------------------------------------------------------
# Tool Spec Tests
# -----------------------------------------------------------------------------


def test_get_tool_specs_all(linear_tools: LinearTools) -> None:
    """get_tool_specs should return all tools when no filter."""
    specs = linear_tools.get_tool_specs()
    assert len(specs) == 14

    tool_names = {s.name for s in specs}
    expected = {
        "linear_create_issue",
        "linear_update_issue",
        "linear_delete_issue",
        "linear_add_label",
        "linear_list_teams",
        "linear_get_team",
        "linear_list_projects",
        "linear_get_project",
        "linear_update_project",
        "linear_list_issues",
        "linear_get_issue",
        "linear_create_issue_relation",
        "linear_get_issue_relations",
        "linear_list_sub_issues",
    }
    assert tool_names == expected


def test_get_tool_specs_filtered(linear_tools: LinearTools) -> None:
    """get_tool_specs should filter to requested tools."""
    specs = linear_tools.get_tool_specs(["linear_create_issue", "linear_update_issue"])
    assert len(specs) == 2
    assert specs[0].name == "linear_create_issue"
    assert specs[1].name == "linear_update_issue"


def test_get_tool_specs_empty_filter(linear_tools: LinearTools) -> None:
    """get_tool_specs with empty list returns empty tuple."""
    specs = linear_tools.get_tool_specs([])
    assert len(specs) == 0


def test_tool_spec_structure(linear_tools: LinearTools) -> None:
    """Each ToolSpec should have required fields."""
    specs = linear_tools.get_tool_specs()

    for spec in specs:
        assert spec.name.startswith("linear_")
        assert spec.description
        assert spec.input_schema["type"] == "object"
        assert spec.handler is not None


def test_get_policy_tools(linear_tools: LinearTools) -> None:
    """get_policy_tools should return dict of handlers."""
    handlers = linear_tools.get_policy_tools()

    assert len(handlers) == 14
    assert "linear_create_issue" in handlers
    assert callable(handlers["linear_create_issue"])


# -----------------------------------------------------------------------------
# Create Issue Handler Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_create_issue(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_create_issue should create and return issue."""
    mock_issue = MagicMock()
    mock_issue.id = "issue-123"
    mock_issue.identifier = "ENG-1"
    mock_issue.title = "Test Issue"
    mock_issue.url = "https://linear.app/issue/ENG-1"
    mock_issue.model_dump.return_value = {
        "id": "issue-123",
        "identifier": "ENG-1",
        "title": "Test Issue",
        "url": "https://linear.app/issue/ENG-1",
    }
    mock_linear_client.create_issue.return_value = mock_issue

    result = await linear_tools._handle_create_issue(
        {
            "title": "Test Issue",
            "team_id": "team-456",
            "project_id": "proj-789",
        }
    )

    assert result["id"] == "issue-123"
    assert result["identifier"] == "ENG-1"
    mock_linear_client.create_issue.assert_called_once()


@pytest.mark.asyncio
async def test_handle_create_issue_with_all_fields(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_create_issue should handle all optional fields."""
    mock_issue = MagicMock()
    mock_issue.id = "issue-456"
    mock_issue.identifier = "ENG-2"
    mock_issue.title = "Issue with details"
    mock_issue.model_dump.return_value = {"id": "issue-456"}
    mock_linear_client.create_issue.return_value = mock_issue

    result = await linear_tools._handle_create_issue(
        {
            "title": "Issue with details",
            "team_id": "team-1",
            "project_id": "proj-1",
            "description": "Description text",
            "priority": 3,
            "parent_id": "parent-123",
        }
    )

    assert result["id"] == "issue-456"


@pytest.mark.asyncio
async def test_handle_create_issue_default_priority(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_create_issue should default priority to MEDIUM."""
    mock_issue = MagicMock()
    mock_issue.model_dump.return_value = {"id": "issue-789"}
    mock_linear_client.create_issue.return_value = mock_issue

    await linear_tools._handle_create_issue(
        {
            "title": "Test",
            "team_id": "team-1",
            "project_id": "proj-1",
        }
    )

    call_args = mock_linear_client.create_issue.call_args[0][0]
    assert call_args.priority == 2  # MEDIUM


@pytest.mark.asyncio
async def test_handle_create_issue_missing_team(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_create_issue should return structured error, not raise, when
    the client reports a missing team or project."""
    mock_linear_client.create_issue.side_effect = RuntimeError(
        "Team 'team-missing' not found."
    )

    result = await linear_tools._handle_create_issue(
        {
            "title": "Test",
            "team_id": "team-missing",
            "project_id": "proj-1",
        }
    )

    assert "error" in result
    assert "team-missing" in result["error"]


# -----------------------------------------------------------------------------
# Update Issue Handler Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_update_issue(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_update_issue should update and return issue."""
    mock_issue = MagicMock()
    mock_issue.id = "issue-123"
    mock_issue.identifier = "ENG-1"
    mock_issue.title = "Updated Title"
    mock_issue.url = "https://linear.app/issue/ENG-1"
    mock_issue.model_dump.return_value = {
        "id": "issue-123",
        "identifier": "ENG-1",
        "title": "Updated Title",
    }
    mock_linear_client.update_issue.return_value = mock_issue

    result = await linear_tools._handle_update_issue(
        {
            "issue_id": "issue-123",
            "title": "Updated Title",
            "priority": 4,
        }
    )

    assert result["id"] == "issue-123"
    assert result["title"] == "Updated Title"
    mock_linear_client.update_issue.assert_called_once_with(
        "issue-123", mock_linear_client.update_issue.call_args[0][1]
    )


@pytest.mark.asyncio
async def test_handle_update_issue_partial(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_update_issue should handle partial updates."""
    mock_issue = MagicMock()
    mock_issue.model_dump.return_value = {"id": "issue-123"}
    mock_linear_client.update_issue.return_value = mock_issue

    result = await linear_tools._handle_update_issue(
        {
            "issue_id": "issue-123",
            "state": "completed",
        }
    )

    assert result["id"] == "issue-123"


@pytest.mark.asyncio
async def test_handle_update_issue_client_error(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_update_issue should return structured error, not raise, on
    client RuntimeError."""
    mock_linear_client.update_issue.side_effect = RuntimeError(
        "Failed to update issue 'MISSING-1': not found"
    )

    result = await linear_tools._handle_update_issue(
        {"issue_id": "MISSING-1", "title": "Whatever"}
    )

    assert "error" in result
    assert "MISSING-1" in result["error"]


# -----------------------------------------------------------------------------
# Delete Issue Handler Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_delete_issue_success(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_delete_issue should return success on deletion."""
    mock_linear_client.delete_issue.return_value = True

    result = await linear_tools._handle_delete_issue({"issue_id": "issue-123"})

    assert result["success"] is True
    assert result["issue_id"] == "issue-123"
    mock_linear_client.delete_issue.assert_called_once_with("issue-123")


@pytest.mark.asyncio
async def test_handle_delete_issue_failure(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_delete_issue should return failure on error."""
    mock_linear_client.delete_issue.return_value = False

    result = await linear_tools._handle_delete_issue({"issue_id": "issue-456"})

    assert result["success"] is False
    assert result["issue_id"] == "issue-456"


# -----------------------------------------------------------------------------
# Add Label Handler Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_add_label(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_add_label should add label and return issue."""
    mock_issue = MagicMock()
    mock_issue.id = "issue-123"
    mock_issue.identifier = "ENG-1"
    mock_issue.title = "Labeled Issue"
    mock_issue.model_dump.return_value = {
        "id": "issue-123",
        "identifier": "ENG-1",
        "title": "Labeled Issue",
    }
    mock_linear_client.add_label_to_issue.return_value = mock_issue

    result = await linear_tools._handle_add_label(
        {
            "issue_id": "issue-123",
            "label_name": "bug",
        }
    )

    assert result["id"] == "issue-123"
    mock_linear_client.add_label_to_issue.assert_called_once()


@pytest.mark.asyncio
async def test_handle_add_label_client_error(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_add_label should return structured error, not raise, on
    client RuntimeError."""
    mock_linear_client.add_label_to_issue.side_effect = RuntimeError(
        "Failed to add label to issue: boom"
    )

    result = await linear_tools._handle_add_label(
        {"issue_id": "issue-123", "label_name": "bug"}
    )

    assert "error" in result
    assert "Failed to add label" in result["error"]


# -----------------------------------------------------------------------------
# Team Handler Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_list_teams(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_list_teams should return list of teams."""
    mock_team = MagicMock()
    mock_team.id = "team-1"
    mock_team.name = "Engineering"
    mock_team.key = "ENG"
    mock_team.description = "Dev team"
    mock_team.model_dump.return_value = {
        "id": "team-1",
        "name": "Engineering",
        "key": "ENG",
        "description": "Dev team",
    }
    mock_linear_client.list_teams.return_value = [mock_team]

    result = await linear_tools._handle_list_teams({})

    assert "teams" in result
    assert len(result["teams"]) == 1
    assert result["teams"][0]["id"] == "team-1"
    assert result["teams"][0]["name"] == "Engineering"


@pytest.mark.asyncio
async def test_handle_list_teams_empty(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_list_teams should handle empty list."""
    mock_linear_client.list_teams.return_value = []

    result = await linear_tools._handle_list_teams({})

    assert result["teams"] == []


@pytest.mark.asyncio
async def test_handle_list_teams_client_error(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_list_teams should return structured error, not raise, on
    client RuntimeError."""
    mock_linear_client.list_teams.side_effect = RuntimeError(
        "Failed to list teams: API boom"
    )

    result = await linear_tools._handle_list_teams({})

    assert "error" in result
    assert "Failed to list teams" in result["error"]


@pytest.mark.asyncio
async def test_handle_get_team_success(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_get_team should return team when found."""
    mock_team = MagicMock()
    mock_team.id = "team-123"
    mock_team.name = "Engineering"
    mock_team.key = "ENG"
    mock_team.description = None
    mock_team.model_dump.return_value = {
        "id": "team-123",
        "name": "Engineering",
        "key": "ENG",
        "description": None,
    }
    mock_linear_client.get_team.return_value = mock_team

    result = await linear_tools._handle_get_team({"team_id": "team-123"})

    assert result["id"] == "team-123"
    assert result["name"] == "Engineering"


@pytest.mark.asyncio
async def test_handle_get_team_not_found(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_get_team should return error when team not found."""
    mock_linear_client.get_team.return_value = None

    result = await linear_tools._handle_get_team({"team_id": "non-existent"})

    assert "error" in result
    assert "non-existent" in result["error"]


# -----------------------------------------------------------------------------
# Project Handler Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_list_projects(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_list_projects should return list of projects."""
    mock_project = MagicMock()
    mock_project.id = "proj-1"
    mock_project.name = "Sprint 1"
    mock_project.description = "Q1 sprint"
    mock_project.team_id = "team-1"
    mock_project.state = "started"
    mock_project.model_dump.return_value = {
        "id": "proj-1",
        "name": "Sprint 1",
        "description": "Q1 sprint",
        "team_id": "team-1",
        "state": "started",
    }
    mock_linear_client.list_projects.return_value = [mock_project]

    result = await linear_tools._handle_list_projects({"team_id": "team-1"})

    assert "projects" in result
    assert len(result["projects"]) == 1
    assert result["projects"][0]["id"] == "proj-1"


@pytest.mark.asyncio
async def test_handle_list_projects_client_error(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_list_projects should return structured error, not raise, on
    client RuntimeError."""
    mock_linear_client.list_projects.side_effect = RuntimeError(
        "Failed to list projects for team 'team-1': API boom"
    )

    result = await linear_tools._handle_list_projects({"team_id": "team-1"})

    assert "error" in result
    assert "team-1" in result["error"]


@pytest.mark.asyncio
async def test_handle_get_project_success(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_get_project should return project when found."""
    mock_project = MagicMock()
    mock_project.id = "proj-123"
    mock_project.name = "Project Name"
    mock_project.description = "Description"
    mock_project.team_id = "team-1"
    mock_project.state = "completed"
    mock_project.model_dump.return_value = {
        "id": "proj-123",
        "name": "Project Name",
        "description": "Description",
        "team_id": "team-1",
        "state": "completed",
    }
    mock_linear_client.get_project.return_value = mock_project

    result = await linear_tools._handle_get_project({"project_id": "proj-123"})

    assert result["id"] == "proj-123"
    assert result["name"] == "Project Name"


@pytest.mark.asyncio
async def test_handle_get_project_not_found(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_get_project should return error when project not found."""
    mock_linear_client.get_project.return_value = None

    result = await linear_tools._handle_get_project({"project_id": "missing"})

    assert "error" in result
    assert "missing" in result["error"]


@pytest.mark.asyncio
async def test_handle_update_project(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_update_project should update and return project."""
    mock_project = MagicMock()
    mock_project.id = "proj-123"
    mock_project.name = "Updated Name"
    mock_project.description = "Updated description"
    mock_project.state = "completed"
    mock_project.model_dump.return_value = {
        "id": "proj-123",
        "name": "Updated Name",
        "description": "Updated description",
        "state": "completed",
    }
    mock_linear_client.update_project.return_value = mock_project

    result = await linear_tools._handle_update_project(
        {
            "project_id": "proj-123",
            "name": "Updated Name",
            "description": "Updated description",
            "state": "completed",
        }
    )

    assert result["id"] == "proj-123"
    assert result["state"] == "completed"


@pytest.mark.asyncio
async def test_handle_update_project_with_message(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_update_project should handle update_message field."""
    mock_project = MagicMock()
    mock_project.id = "proj-123"
    mock_project.name = "Project"
    mock_project.state = "started"
    mock_project.model_dump.return_value = {"id": "proj-123"}
    mock_linear_client.update_project.return_value = mock_project

    result = await linear_tools._handle_update_project(
        {
            "project_id": "proj-123",
            "update_message": "Sprint started!",
        }
    )

    assert result["id"] == "proj-123"


@pytest.mark.asyncio
async def test_handle_update_project_not_found(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_update_project should return structured error matching the
    pattern used by _handle_get_project, not propagate RuntimeError."""
    mock_linear_client.update_project.side_effect = RuntimeError(
        "Failed to update project: Project 'missing' not found."
    )

    result = await linear_tools._handle_update_project(
        {"project_id": "missing", "name": "Whatever"}
    )

    assert "error" in result
    assert "missing" in result["error"]


# -----------------------------------------------------------------------------
# Issue Handler Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_list_issues(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_list_issues should return list of issues."""
    mock_state = MagicMock()
    mock_state.id = "state-1"
    mock_state.name = "In Progress"
    mock_state.color = "#00f"
    mock_state.type = "started"

    mock_issue = MagicMock()
    mock_issue.id = "issue-1"
    mock_issue.identifier = "ENG-1"
    mock_issue.title = "Issue 1"
    mock_issue.state = mock_state
    mock_issue.priority = 2
    mock_issue.url = "https://linear.app/issue/ENG-1"
    mock_issue.model_dump.return_value = {
        "id": "issue-1",
        "identifier": "ENG-1",
        "title": "Issue 1",
        "state": {"name": "In Progress"},
        "priority": 2,
    }
    mock_linear_client.list_issues.return_value = [mock_issue]

    result = await linear_tools._handle_list_issues({"project_id": "proj-1"})

    assert "issues" in result
    assert len(result["issues"]) == 1
    assert result["issues"][0]["id"] == "issue-1"


@pytest.mark.asyncio
async def test_handle_list_issues_client_error(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_list_issues should return structured error, not raise, on
    client RuntimeError."""
    mock_linear_client.list_issues.side_effect = RuntimeError(
        "Failed to list issues for project 'proj-1': API boom"
    )

    result = await linear_tools._handle_list_issues({"project_id": "proj-1"})

    assert "error" in result
    assert "proj-1" in result["error"]


@pytest.mark.asyncio
async def test_handle_get_issue_success(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_get_issue should return issue when found."""
    mock_state = MagicMock()
    mock_state.id = "state-1"
    mock_state.name = "In Progress"

    mock_issue = MagicMock()
    mock_issue.id = "issue-123"
    mock_issue.identifier = "ENG-42"
    mock_issue.title = "Test Issue"
    mock_issue.description = "Description"
    mock_issue.state = mock_state
    mock_issue.priority = 3
    mock_issue.team_id = "team-1"
    mock_issue.project_id = "proj-1"
    mock_issue.url = "https://linear.app/issue/ENG-42"
    mock_issue.model_dump.return_value = {
        "id": "issue-123",
        "identifier": "ENG-42",
        "title": "Test Issue",
        "state": {"name": "In Progress"},
    }
    mock_linear_client.get_issue.return_value = mock_issue

    result = await linear_tools._handle_get_issue({"issue_id": "ENG-42"})

    assert result["id"] == "issue-123"
    assert result["identifier"] == "ENG-42"


@pytest.mark.asyncio
async def test_handle_get_issue_not_found(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_get_issue should return error when issue not found."""
    mock_linear_client.get_issue.return_value = None

    result = await linear_tools._handle_get_issue({"issue_id": "MISSING-1"})

    assert "error" in result
    assert "MISSING-1" in result["error"]


# -----------------------------------------------------------------------------
# Schema Validation Tests
# -----------------------------------------------------------------------------


def test_create_issue_schema_structure() -> None:
    """CREATE_ISSUE_SCHEMA should have correct structure."""
    from tools.linear import CREATE_ISSUE_SCHEMA

    assert CREATE_ISSUE_SCHEMA["type"] == "object"
    assert "title" in CREATE_ISSUE_SCHEMA["properties"]
    assert "team_id" in CREATE_ISSUE_SCHEMA["properties"]
    assert "project_id" in CREATE_ISSUE_SCHEMA["properties"]
    assert CREATE_ISSUE_SCHEMA["required"] == ["title", "team_id", "project_id"]

    title_schema = CREATE_ISSUE_SCHEMA["properties"]["title"]
    assert title_schema["type"] == "string"
    assert title_schema["maxLength"] == 256


def test_update_issue_schema_structure() -> None:
    """UPDATE_ISSUE_SCHEMA should have correct structure."""
    from tools.linear import UPDATE_ISSUE_SCHEMA

    assert UPDATE_ISSUE_SCHEMA["required"] == ["issue_id"]
    assert "title" in UPDATE_ISSUE_SCHEMA["properties"]
    assert "state" in UPDATE_ISSUE_SCHEMA["properties"]
    assert "priority" in UPDATE_ISSUE_SCHEMA["properties"]
    # Re-parenting support.
    assert "parent_id" in UPDATE_ISSUE_SCHEMA["properties"]
    assert UPDATE_ISSUE_SCHEMA["properties"]["parent_id"]["type"] == "string"


def test_schemas_have_descriptions() -> None:
    """All tool schemas should have descriptions."""
    from tools.linear import (
        CREATE_ISSUE_SCHEMA,
        DELETE_ISSUE_SCHEMA,
        GET_ISSUE_RELATIONS_SCHEMA,
        GET_ISSUE_SCHEMA,
        GET_PROJECT_SCHEMA,
        GET_TEAM_SCHEMA,
        LIST_ISSUES_SCHEMA,
        LIST_PROJECTS_SCHEMA,
        LIST_SUB_ISSUES_SCHEMA,
        LIST_TEAMS_SCHEMA,
        UPDATE_ISSUE_SCHEMA,
        UPDATE_PROJECT_SCHEMA,
    )

    schemas = [
        CREATE_ISSUE_SCHEMA,
        UPDATE_ISSUE_SCHEMA,
        DELETE_ISSUE_SCHEMA,
        LIST_TEAMS_SCHEMA,
        GET_TEAM_SCHEMA,
        LIST_PROJECTS_SCHEMA,
        GET_PROJECT_SCHEMA,
        UPDATE_PROJECT_SCHEMA,
        LIST_ISSUES_SCHEMA,
        GET_ISSUE_SCHEMA,
        GET_ISSUE_RELATIONS_SCHEMA,
        LIST_SUB_ISSUES_SCHEMA,
    ]

    for schema in schemas:
        for prop_name, prop in schema["properties"].items():
            assert "description" in prop, f"Property {prop_name} missing description"


def test_get_issue_relations_schema_structure() -> None:
    """GET_ISSUE_RELATIONS_SCHEMA should require issue_id only."""
    from tools.linear import GET_ISSUE_RELATIONS_SCHEMA

    assert GET_ISSUE_RELATIONS_SCHEMA["type"] == "object"
    assert GET_ISSUE_RELATIONS_SCHEMA["required"] == ["issue_id"]
    assert "issue_id" in GET_ISSUE_RELATIONS_SCHEMA["properties"]


# -----------------------------------------------------------------------------
# _handle_get_issue_relations Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_get_issue_relations_returns_list(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_get_issue_relations should serialize relations to JSON dicts."""
    from libs.linear.schemas import IssueRelation, RelatedIssueRef

    mock_linear_client.get_issue_relations.return_value = [
        IssueRelation(
            id="rel-1",
            type="blocks",
            relatedIssue=RelatedIssueRef(id="issue-2", title="Other"),
            createdAt="2026-01-02T03:04:05",
        )
    ]

    result = await linear_tools._handle_get_issue_relations({"issue_id": "ENG-42"})

    mock_linear_client.get_issue_relations.assert_called_once_with("ENG-42")
    assert result == {
        "relations": [
            {
                "id": "rel-1",
                "type": "blocks",
                "related_issue": {"id": "issue-2", "title": "Other"},
                "created_at": "2026-01-02T03:04:05",
            }
        ]
    }


@pytest.mark.asyncio
async def test_handle_get_issue_relations_empty(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_get_issue_relations should return empty list when no relations exist."""
    mock_linear_client.get_issue_relations.return_value = []

    result = await linear_tools._handle_get_issue_relations({"issue_id": "ENG-42"})

    assert result == {"relations": []}


def test_get_policy_tools_includes_get_issue_relations(
    linear_tools: LinearTools,
) -> None:
    """get_policy_tools should include the new linear_get_issue_relations handler."""
    tools = linear_tools.get_policy_tools()
    assert "linear_get_issue_relations" in tools


# -----------------------------------------------------------------------------
# Sub-issue Support
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_update_issue_with_parent_id(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_update_issue should forward parent_id when re-parenting."""
    mock_issue = MagicMock()
    mock_issue.model_dump.return_value = {
        "id": "issue-child",
        "parent_id": "issue-new-parent",
    }
    mock_linear_client.update_issue.return_value = mock_issue

    result = await linear_tools._handle_update_issue(
        {
            "issue_id": "issue-child",
            "parent_id": "issue-new-parent",
        }
    )

    assert result["parent_id"] == "issue-new-parent"
    mock_linear_client.update_issue.assert_called_once()
    # The IssueUpdateInput passed to the client must carry parent_id.
    _, update_input = mock_linear_client.update_issue.call_args[0]
    assert update_input.parent_id == "issue-new-parent"


def test_list_sub_issues_schema_structure() -> None:
    """LIST_SUB_ISSUES_SCHEMA should require issue_id only."""
    from tools.linear import LIST_SUB_ISSUES_SCHEMA

    assert LIST_SUB_ISSUES_SCHEMA["type"] == "object"
    assert LIST_SUB_ISSUES_SCHEMA["required"] == ["issue_id"]
    assert "issue_id" in LIST_SUB_ISSUES_SCHEMA["properties"]


@pytest.mark.asyncio
async def test_handle_list_sub_issues_returns_list(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_list_sub_issues should serialize sub-issues to JSON dicts."""
    child_a = MagicMock()
    child_a.model_dump.return_value = {
        "id": "issue-child-1",
        "identifier": "ENG-101",
        "title": "Child A",
        "parent_id": "issue-parent",
    }
    child_b = MagicMock()
    child_b.model_dump.return_value = {
        "id": "issue-child-2",
        "identifier": "ENG-102",
        "title": "Child B",
        "parent_id": "issue-parent",
    }
    mock_linear_client.list_sub_issues.return_value = [child_a, child_b]

    result = await linear_tools._handle_list_sub_issues({"issue_id": "issue-parent"})

    mock_linear_client.list_sub_issues.assert_called_once_with("issue-parent")
    assert "sub_issues" in result
    assert len(result["sub_issues"]) == 2
    assert result["sub_issues"][0]["id"] == "issue-child-1"
    assert result["sub_issues"][1]["id"] == "issue-child-2"


@pytest.mark.asyncio
async def test_handle_list_sub_issues_empty(
    linear_tools: LinearTools, mock_linear_client: MagicMock
) -> None:
    """_handle_list_sub_issues returns empty list when no sub-issues exist."""
    mock_linear_client.list_sub_issues.return_value = []

    result = await linear_tools._handle_list_sub_issues({"issue_id": "issue-parent"})

    assert result == {"sub_issues": []}


def test_get_policy_tools_includes_list_sub_issues(
    linear_tools: LinearTools,
) -> None:
    """get_policy_tools should include the new linear_list_sub_issues handler."""
    tools = linear_tools.get_policy_tools()
    assert "linear_list_sub_issues" in tools
    assert callable(tools["linear_list_sub_issues"])
    assert callable(tools["linear_get_issue_relations"])
