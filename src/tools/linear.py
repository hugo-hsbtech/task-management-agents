"""Linear tools for provider-agnostic agent integration.

Defines ToolSpec declarations for Codex, Claude, and Gemini agents to manage
Linear issues, projects, and teams via the libs.linear client.

Example:
    from tools.linear import LinearTools
    from llm_providers.tools import ToolPolicy

    # Create tool policy for an agent
    linear_tools = LinearTools(api_key="lin_api_...")
    policy = ToolPolicy(
        allowed=("linear_create_issue", "linear_update_issue"),
        custom=linear_tools.get_tool_specs(),
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from libs.linear import LinearClient
from libs.linear.schemas import (
    IssueInput,
    IssueLabelInput,
    IssueUpdateInput,
    ProjectUpdateInput,
)
from llm_providers.tools import ToolSpec

# -----------------------------------------------------------------------------
# JSON Schema definitions for tool inputs
# -----------------------------------------------------------------------------

CREATE_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Issue title (required)",
            "maxLength": 256,
        },
        "description": {
            "type": "string",
            "description": "Issue description (optional)",
        },
        "team_id": {
            "type": "string",
            "description": "Team ID to create the issue in (required)",
        },
        "project_id": {
            "type": "string",
            "description": "Project ID to associate the issue with (required)",
        },
        "priority": {
            "type": "integer",
            "description": "Priority level: 0=none, 1=low, 2=medium, 3=high, 4=urgent",
            "minimum": 0,
            "maximum": 4,
            "default": 2,
        },
        "parent_id": {
            "type": "string",
            "description": "Parent issue ID for subtasks (optional)",
        },
    },
    "required": ["title", "team_id", "project_id"],
}

UPDATE_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issue_id": {
            "type": "string",
            "description": "Issue ID or identifier (e.g., 'ENG-123') (required)",
        },
        "title": {
            "type": "string",
            "description": "New issue title (optional)",
            "maxLength": 256,
        },
        "description": {
            "type": "string",
            "description": "New issue description (optional)",
        },
        "state": {
            "type": "string",
            "description": "New issue state (optional)",
        },
        "priority": {
            "type": "integer",
            "description": "New priority level: 0=none, 1=low, 2=medium, 3=high, 4=urgent",
            "minimum": 0,
            "maximum": 4,
        },
    },
    "required": ["issue_id"],
}

DELETE_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issue_id": {
            "type": "string",
            "description": "Issue ID or identifier to delete (e.g., 'ENG-123') (required)",
        },
    },
    "required": ["issue_id"],
}

ADD_LABEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issue_id": {
            "type": "string",
            "description": "Issue ID or identifier to add label to (required)",
        },
        "label_name": {
            "type": "string",
            "description": "Label name to add (creates if doesn't exist) (required)",
        },
    },
    "required": ["issue_id", "label_name"],
}

LIST_TEAMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}

GET_TEAM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "team_id": {
            "type": "string",
            "description": "Team ID or key to retrieve (required)",
        },
    },
    "required": ["team_id"],
}

LIST_PROJECTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "team_id": {
            "type": "string",
            "description": "Team ID to list projects for (required)",
        },
    },
    "required": ["team_id"],
}

GET_PROJECT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "project_id": {
            "type": "string",
            "description": "Project ID to retrieve (required)",
        },
    },
    "required": ["project_id"],
}

UPDATE_PROJECT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "project_id": {
            "type": "string",
            "description": "Project ID to update (required)",
        },
        "name": {
            "type": "string",
            "description": "New project name (optional)",
        },
        "description": {
            "type": "string",
            "description": "New project description (optional)",
        },
        "state": {
            "type": "string",
            "description": "New project state: planned, started, paused, completed, canceled (optional)",
        },
        "update_message": {
            "type": "string",
            "description": "Progress update message to post to project (optional)",
        },
    },
    "required": ["project_id"],
}

LIST_ISSUES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "project_id": {
            "type": "string",
            "description": "Project ID to list issues for (required)",
        },
    },
    "required": ["project_id"],
}

GET_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "issue_id": {
            "type": "string",
            "description": "Issue ID or identifier to retrieve (e.g., 'ENG-123') (required)",
        },
    },
    "required": ["issue_id"],
}


# -----------------------------------------------------------------------------
# Linear Tools Implementation
# -----------------------------------------------------------------------------


class LinearTools:
    """Provider-agnostic Linear tools for agent integration.

    Creates ToolSpec definitions that work with Codex, Claude, and Gemini
    providers via the llm_providers translation layer.

    Example:
        tools = LinearTools(api_key="lin_api_...")
        specs = tools.get_tool_specs()  # All available tools

        # Or with specific tools only
        specs = tools.get_tool_specs([
            "linear_create_issue",
            "linear_update_issue",
        ])
    """

    def __init__(self, api_key: str) -> None:
        """Initialize with Linear API key.

        Args:
            api_key: Linear API key (get from https://linear.app/settings/api)
        """
        self._client = LinearClient(api_key=api_key)

    # -------------------------------------------------------------------------
    # Tool Handlers
    # -------------------------------------------------------------------------

    async def _handle_create_issue(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Handler for linear_create_issue tool."""
        issue_input = IssueInput.model_validate(obj=input_data)
        try:
            issue = self._client.create_issue(issue_input)
        except RuntimeError as e:
            return {"error": str(e)}
        return issue.model_dump(mode="json")

    async def _handle_update_issue(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Handler for linear_update_issue tool."""
        update_input = IssueUpdateInput.model_validate(obj=input_data)
        try:
            issue = self._client.update_issue(input_data["issue_id"], update_input)
        except RuntimeError as e:
            return {"error": str(e)}
        return issue.model_dump(mode="json")

    async def _handle_delete_issue(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Handler for linear_delete_issue tool."""
        success = self._client.delete_issue(input_data["issue_id"])
        return {"success": success, "issue_id": input_data["issue_id"]}

    async def _handle_add_label(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Handler for linear_add_label tool."""
        label_input = IssueLabelInput.model_validate(obj=input_data)
        try:
            issue = self._client.add_label_to_issue(label_input)
        except RuntimeError as e:
            return {"error": str(e)}
        return issue.model_dump(mode="json")

    async def _handle_list_teams(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Handler for linear_list_teams tool."""
        try:
            teams = self._client.list_teams()
        except RuntimeError as e:
            return {"error": str(e)}
        return {"teams": [t.model_dump(mode="json") for t in teams]}

    async def _handle_get_team(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Handler for linear_get_team tool."""
        team = self._client.get_team(input_data["team_id"])
        if team is None:
            return {"error": f"Team '{input_data['team_id']}' not found"}

        return team.model_dump(mode="json")

    async def _handle_list_projects(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Handler for linear_list_projects tool."""
        try:
            projects = self._client.list_projects(input_data["team_id"])
        except RuntimeError as e:
            return {"error": str(e)}
        return {"projects": [p.model_dump(mode="json") for p in projects]}

    async def _handle_get_project(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Handler for linear_get_project tool."""
        project = self._client.get_project(input_data["project_id"])

        if project is None:
            return {"error": f"Project '{input_data['project_id']}' not found"}

        return project.model_dump(mode="json")

    async def _handle_update_project(
        self, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handler for linear_update_project tool."""
        update_input = ProjectUpdateInput.model_validate(obj=input_data)
        try:
            project = self._client.update_project(
                input_data["project_id"], update_input
            )
        except RuntimeError as e:
            return {"error": str(e)}
        return project.model_dump(mode="json")

    async def _handle_list_issues(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Handler for linear_list_issues tool."""
        try:
            issues = self._client.list_issues(input_data["project_id"])
        except RuntimeError as e:
            return {"error": str(e)}
        return {"issues": [i.model_dump(mode="json") for i in issues]}

    async def _handle_get_issue(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Handler for linear_get_issue tool."""
        issue = self._client.get_issue(input_data["issue_id"])
        if issue is None:
            return {"error": f"Issue '{input_data['issue_id']}' not found"}
        return issue.model_dump(mode="json")

    # -------------------------------------------------------------------------
    # Tool Specs
    # -------------------------------------------------------------------------

    def get_tool_specs(
        self, tool_names: list[str] | None = None
    ) -> tuple[ToolSpec, ...]:
        """Get ToolSpec definitions for Linear tools.

        Args:
            tool_names: Optional list of specific tool names to include.
                       If None, all tools are returned.

        Returns:
            Tuple of ToolSpec objects for use with ToolPolicy.custom
        """
        all_specs: dict[str, ToolSpec] = {
            "linear_create_issue": ToolSpec(
                name="linear_create_issue",
                description="Create a new Linear issue in a specific team and project",
                input_schema=CREATE_ISSUE_SCHEMA,
                handler=self._handle_create_issue,
            ),
            "linear_update_issue": ToolSpec(
                name="linear_update_issue",
                description="Update an existing Linear issue (title, description, state, priority)",
                input_schema=UPDATE_ISSUE_SCHEMA,
                handler=self._handle_update_issue,
            ),
            "linear_delete_issue": ToolSpec(
                name="linear_delete_issue",
                description="Delete a Linear issue by ID",
                input_schema=DELETE_ISSUE_SCHEMA,
                handler=self._handle_delete_issue,
            ),
            "linear_add_label": ToolSpec(
                name="linear_add_label",
                description="Add a label to a Linear issue (creates label if doesn't exist)",
                input_schema=ADD_LABEL_SCHEMA,
                handler=self._handle_add_label,
            ),
            "linear_list_teams": ToolSpec(
                name="linear_list_teams",
                description="List all Linear teams accessible to the API key",
                input_schema=LIST_TEAMS_SCHEMA,
                handler=self._handle_list_teams,
            ),
            "linear_get_team": ToolSpec(
                name="linear_get_team",
                description="Get a specific Linear team by ID or key",
                input_schema=GET_TEAM_SCHEMA,
                handler=self._handle_get_team,
            ),
            "linear_list_projects": ToolSpec(
                name="linear_list_projects",
                description="List all projects within a Linear team",
                input_schema=LIST_PROJECTS_SCHEMA,
                handler=self._handle_list_projects,
            ),
            "linear_get_project": ToolSpec(
                name="linear_get_project",
                description="Get a specific Linear project by ID",
                input_schema=GET_PROJECT_SCHEMA,
                handler=self._handle_get_project,
            ),
            "linear_update_project": ToolSpec(
                name="linear_update_project",
                description="Update a Linear project (name, description, state) and optionally post an update",
                input_schema=UPDATE_PROJECT_SCHEMA,
                handler=self._handle_update_project,
            ),
            "linear_list_issues": ToolSpec(
                name="linear_list_issues",
                description="List all issues within a Linear project",
                input_schema=LIST_ISSUES_SCHEMA,
                handler=self._handle_list_issues,
            ),
            "linear_get_issue": ToolSpec(
                name="linear_get_issue",
                description="Get a specific Linear issue by ID or identifier (e.g., 'ENG-123')",
                input_schema=GET_ISSUE_SCHEMA,
                handler=self._handle_get_issue,
            ),
        }

        if tool_names is None:
            return tuple(all_specs.values())

        return tuple(spec for name, spec in all_specs.items() if name in tool_names)

    def get_policy_tools(self) -> dict[str, Callable[..., Awaitable[Any]]]:
        """Get a mapping of tool names to handlers for direct use.

        Returns:
            Dict mapping tool name to handler function.
            Useful for providers that need explicit handler registration.
        """
        return {spec.name: spec.handler for spec in self.get_tool_specs()}
