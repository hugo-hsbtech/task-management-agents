"""Low-level Linear API client wrapping linear-api package.

Uses internal mapping to convert between linear_api types and our own schemas.
Consumers should import from libs.linear.schemas, not from linear_api.
"""

import logging
from typing import Any

from linear_api import LinearClient as BaseLinearClient
from linear_api import LinearIssueInput, LinearIssueUpdateInput

from libs.linear.schemas import (
    Issue,
    IssueInput,
    IssueLabelInput,
    IssueUpdateInput,
    Label,
    Project,
    ProjectUpdateInput,
    Team,
    _map_priority_to_api,
)

logger = logging.getLogger(__name__)


class LinearClient:
    """Wrapper around linear-api package with typed responses.

    This is a low-level client. For high-level operations, use LinearService.
    """

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise RuntimeError(
                "Linear API key required. Get API key from: https://linear.app/settings/api"
            )
        self._client = BaseLinearClient(api_key=api_key)

    # -----------------------------------------------------------------------
    # Teams
    # -----------------------------------------------------------------------

    def list_teams(self) -> list[Team]:
        """List all teams accessible to the API key."""
        linear_teams = self._client.teams.get_all()
        return [Team.from_linear(team) for team in linear_teams.values()]

    def get_team(self, team_id: str) -> Team | None:
        """Get a specific team by ID."""
        try:
            linear_team = self._client.teams.get(team_id=team_id)
            if linear_team:
                return Team.from_linear(linear_team)
            return None
        except Exception:
            logger.warning(
                "teams.get(%r) failed; falling back to list-and-match",
                team_id,
                exc_info=True,
            )
            try:
                teams = self._client.teams.get_all()
                for team in teams.values():
                    if team.id == team_id or team.key == team_id:
                        return Team.from_linear(team)
                return None
            except Exception:
                logger.exception("teams.get_all() fallback failed for %r", team_id)
                return None

    # -----------------------------------------------------------------------
    # Projects
    # -----------------------------------------------------------------------

    def list_projects(self, team_id: str) -> list[Project]:
        """List all projects within a team."""
        if not team_id:
            return []

        linear_projects = self._client.projects.get_all(team_id=team_id)
        return [Project.from_linear(proj) for proj in linear_projects.values()]

    def get_project(self, project_id: str) -> Project | None:
        """Get a specific project by ID."""
        try:
            linear_project = self._client.projects.get(project_id)
            if linear_project:
                return Project.from_linear(linear_project)
            return None
        except Exception:
            logger.exception("projects.get(%r) failed", project_id)
            return None

    def update_project(
        self, project_id: str, input_data: ProjectUpdateInput
    ) -> Project:
        """Update a project (name, description, state) and optionally post an update."""
        try:
            if input_data.name or input_data.description or input_data.state:
                linear_project = self._client.projects.update(
                    project_id=project_id,
                    name=input_data.name,
                    description=input_data.description,
                    state=input_data.state,
                )
            else:
                linear_project = self._client.projects.get(project_id)
        except Exception as e:
            raise RuntimeError(f"Failed to update project {project_id!r}: {e}") from e

        if linear_project is None:
            raise RuntimeError(f"Project {project_id!r} not found.")

        if input_data.update_message:
            self._post_project_update(project_id, input_data.update_message)

        return Project.from_linear(linear_project)

    def _post_project_update(self, project_id: str, message: str) -> None:
        """Post an update/message to a project (progress report)."""
        try:
            # Use raw GraphQL to post project update
            query = """
            mutation($input: ProjectUpdateCreateInput!) {
                projectUpdateCreate(input: $input) {
                    success
                    projectUpdate {
                        id
                        body
                    }
                }
            }
            """
            variables = {
                "input": {
                    "projectId": project_id,
                    "body": message,
                }
            }
            self._execute_raw(query, variables)
        except Exception:
            # Best effort — don't fail the whole update if posting fails,
            # but surface the cause so callers can see it in traces.
            logger.exception(
                "projectUpdateCreate mutation failed for project %r", project_id
            )

    def _execute_raw(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a raw GraphQL query (internal use only)."""
        from collections.abc import Callable
        from typing import cast

        vars_dict = variables or {}

        # Try to access the underlying client's execute method
        if hasattr(self._client, "_execute"):
            result: dict[str, Any] = self._client._execute(query, vars_dict)
            return result

        # Fallback: try to use any public execute method
        execute_method = getattr(self._client, "execute", None)
        if execute_method:
            typed_execute = cast(Callable[..., dict[str, Any]], execute_method)
            return typed_execute(query, vars_dict)

        raise RuntimeError(
            "Raw GraphQL execution not supported by this linear-api version"
        )

    # -----------------------------------------------------------------------
    # Issues
    # -----------------------------------------------------------------------

    def list_issues(self, project_id: str) -> list[Issue]:
        """List all issues within a specific project."""
        linear_issues = self._client.projects.get_issues(project_id=project_id)
        return [Issue.from_linear(issue) for issue in linear_issues]

    def get_issue(self, issue_id: str) -> Issue | None:
        """Get a specific issue by ID or identifier (e.g., 'ENG-123')."""
        try:
            linear_issue = self._client.issues.get(issue_id)
            if linear_issue:
                return Issue.from_linear(linear_issue)
            return None
        except Exception:
            logger.exception("issues.get(%r) failed", issue_id)
            return None

    def create_issue(self, input_data: IssueInput) -> Issue:
        """Create a new Linear issue."""
        # LinearIssueInput expects human-readable teamName / projectName, not
        # IDs — the linear-api package resolves names → IDs internally. Our
        # IssueInput schema carries IDs, so we resolve them here.
        team = self.get_team(input_data.team_id)
        if team is None:
            raise RuntimeError(f"Team {input_data.team_id!r} not found.")

        project = self.get_project(input_data.project_id)
        if project is None:
            raise RuntimeError(f"Project {input_data.project_id!r} not found.")

        issue_input = LinearIssueInput(
            title=input_data.title,
            description=input_data.description,
            teamName=team.name,
            projectName=project.name,
            priority=_map_priority_to_api(input_data.priority),
            parentId=input_data.parent_id,
        )

        linear_issue = self._client.issues.create(issue=issue_input)
        return Issue.from_linear(linear_issue)

    def update_issue(self, issue_id: str, input_data: IssueUpdateInput) -> Issue:
        """Update an existing Linear issue."""
        # linear-api exposes the workflow state field as `stateName` and
        # resolves it to a state ID internally via the issue's team.
        update = LinearIssueUpdateInput(
            title=input_data.title,
            description=input_data.description,
            stateName=input_data.state,
            priority=_map_priority_to_api(input_data.priority),
        )

        try:
            linear_issue = self._client.issues.update(issue_id, update)
            return Issue.from_linear(linear_issue)
        except Exception as e:
            raise RuntimeError(f"Failed to update issue {issue_id!r}: {e}") from e

    def delete_issue(self, issue_id: str) -> bool:
        """Delete a Linear issue. Returns True if successful."""
        try:
            self._client.issues.delete(issue_id)
            return True
        except Exception:
            logger.exception("issues.delete(%r) failed", issue_id)
            return False

    def add_label_to_issue(self, input_data: IssueLabelInput) -> Issue:
        """Add a label to an issue. Creates the label if it doesn't exist."""
        try:
            # linear-api uses label name which creates if not exists
            linear_issue = self._client.issues.add_label(
                issue_id=input_data.issue_id,
                label=input_data.label_name,
            )
            return Issue.from_linear(linear_issue)
        except Exception as e:
            raise RuntimeError(f"Failed to add label to issue: {e}") from e

    def list_issue_labels(self, issue_id: str) -> list[Label]:
        """List all labels on a specific issue."""
        try:
            linear_issue = self._client.issues.get(issue_id)
            if linear_issue and hasattr(linear_issue, "labels"):
                return [Label.from_linear(label) for label in linear_issue.labels]
            return []
        except Exception:
            logger.exception("issues.get(%r) failed while listing labels", issue_id)
            return []
