"""Low-level Linear API client wrapping linear-api package.

Uses internal mapping to convert between linear_api types and our own schemas.
Consumers should import from libs.linear.schemas, not from linear_api.
"""

import logging
from typing import TYPE_CHECKING, Any, Literal

from linear_api import LinearClient as BaseLinearClient
from linear_api import LinearIssueInput, LinearIssueUpdateInput
from linear_api.domain import LinearAttachmentInput

from libs.linear.schemas import (
    Comment,
    CommentInput,
    CommentUser,
    Issue,
    IssueInput,
    IssueLabelInput,
    IssueRelation,
    IssueUpdateInput,
    Label,
    Project,
    ProjectCommentInput,
    ProjectUpdateInput,
    Team,
    _map_priority_to_api,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class LinearClient:
    """Wrapper around linear-api package with typed responses."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError(
                "Linear API key required. Get API key from: https://linear.app/settings/api"
            )
        self._client = BaseLinearClient(api_key=api_key)

    # -----------------------------------------------------------------------
    # Teams
    # -----------------------------------------------------------------------

    def list_teams(self) -> list[Team]:
        """List all teams accessible to the API key."""
        try:
            linear_teams = self._client.teams.get_all()
        except Exception as e:
            raise RuntimeError(f"Failed to list teams: {e}") from e
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
            raise ValueError("Team ID is required to list projects")

        try:
            linear_projects = self._client.projects.get_all(team_id=team_id)
        except Exception as e:
            raise RuntimeError(
                f"Failed to list projects for team {team_id!r}: {e}"
            ) from e
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
        # `is not None` (not truthy) so empty-string clears (description="")
        # still hit the update endpoint instead of falling through to get().
        has_field_update = (
            input_data.name is not None
            or input_data.description is not None
            or input_data.state is not None
        )
        try:
            if has_field_update:
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

    def create_project(
        self, team_id: str, name: str, description: str | None = None
    ) -> Project:
        """Create a new Linear project."""
        team = self.get_team(team_id)
        if team is None:
            raise ValueError(f"Team not found: {team_id}")

        try:
            linear_project = self._client.projects.create(
                name=name, team_name=team.name, description=description
            )
            return Project.from_linear(linear_project)
        except Exception as e:
            raise RuntimeError(f"Failed to create project: {e}") from e

    def delete_project(self, project_id: str) -> bool:
        """Delete a Linear project. Returns True if successful."""
        result = self._client.projects.delete(project_id)
        return bool(result)

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
        from typing import cast

        vars_dict = variables or {}

        # SDK public method (linear-api >= 0.3)
        if hasattr(self._client, "execute_graphql"):
            result: dict[str, Any] = self._client.execute_graphql(query, vars_dict)
            return result

        # Fallback: try public execute method first (more stable)
        execute_method = getattr(self._client, "execute", None)
        if execute_method:
            typed_execute = cast("Callable[..., dict[str, Any]]", execute_method)
            return typed_execute(query, vars_dict)

        # Older SDK private method (fallback for older versions)
        if hasattr(self._client, "_execute"):
            result = self._client._execute(query, vars_dict)
            return result

        raise RuntimeError(
            "Raw GraphQL execution not supported by this linear-api version"
        )

    # -----------------------------------------------------------------------
    # Issues
    # -----------------------------------------------------------------------

    def list_issues(self, project_id: str) -> list[Issue]:
        """List all issues within a specific project.

        Bypasses ``linear_api.projects.get_issues``: its GraphQL projection
        omits ``team``, ``project``, ``parent``, ``identifier``, and ``url``
        — so the returned issues lose every foreign-key reference — and it
        silently caps results at 50 with no pagination. We run our own query
        instead and follow ``pageInfo`` to completion.
        """
        query = """
        query($projectId: String!, $cursor: String) {
          project(id: $projectId) {
            issues(first: 50, after: $cursor) {
              nodes {
                id
                identifier
                title
                description
                url
                priority
                state { id name color type }
                team { id }
                project { id }
                parent { id }
                createdAt
                updatedAt
              }
              pageInfo { hasNextPage endCursor }
            }
          }
        }
        """

        issues: list[Issue] = []
        cursor: str | None = None
        while True:
            try:
                response = self._execute_raw(
                    query, {"projectId": project_id, "cursor": cursor}
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to list issues for project {project_id!r}: {e}"
                ) from e

            # _execute_raw may return either unwrapped data ({"project": ...})
            # or the full envelope ({"data": {"project": ...}}); accept both.
            payload: Any = response
            if isinstance(response, dict) and isinstance(response.get("data"), dict):
                payload = response["data"]
            if not isinstance(payload, dict):
                break

            project = payload.get("project")
            if not isinstance(project, dict):
                break

            issues_conn = project.get("issues") or {}
            for node in issues_conn.get("nodes") or []:
                issues.append(Issue.from_linear(node))

            page_info = issues_conn.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            next_cursor = page_info.get("endCursor")
            if not next_cursor:
                break
            cursor = next_cursor

        return issues

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

        try:
            linear_issue = self._client.issues.create(issue=issue_input)
            return Issue.from_linear(linear_issue)
        except Exception as e:
            raise RuntimeError(f"Failed to create issue: {e}") from e

    def update_issue(self, issue_id: str, input_data: IssueUpdateInput) -> Issue:
        """Update an existing Linear issue."""
        # linear-api exposes the workflow state field as `stateName` and
        # resolves it to a state ID internally via the issue's team.
        # parent_id re-parents the issue when provided (turning it into a sub-issue).
        update = LinearIssueUpdateInput(
            title=input_data.title,
            description=input_data.description,
            stateName=input_data.state,
            priority=_map_priority_to_api(input_data.priority),
            parentId=input_data.parent_id,
        )

        try:
            linear_issue = self._client.issues.update(issue_id, update)
            return Issue.from_linear(linear_issue)
        except Exception as e:
            raise RuntimeError(f"Failed to update issue {issue_id!r}: {e}") from e

    def delete_issue(self, issue_id: str) -> bool:
        """Delete a Linear issue. Returns True if successful."""
        try:
            result = self._client.issues.delete(issue_id)
            return bool(result)
        except Exception:
            logger.exception("issues.delete(%r) failed", issue_id)
            return False

    def add_label_to_issue(self, input_data: IssueLabelInput) -> Issue:
        """Add a label to an issue. Creates the label if it doesn't exist."""
        try:
            linear_issue = self._client.issues.add_label(
                input_data.issue_id,
                label=input_data.label_name,
            )
            return Issue.from_linear(linear_issue)
        except Exception as e:
            raise RuntimeError(f"Failed to add label to issue: {e}") from e

    def list_issue_labels(self, issue_id: str) -> list[Label]:
        """List all labels on an issue."""
        try:
            linear_labels = self._client.issues.get_labels(issue_id)
            return [Label.from_linear(label) for label in linear_labels]
        except Exception:
            logger.exception("issues.get(%r) failed while listing labels", issue_id)
            return []

    def create_issue_relation(
        self,
        *,
        issue_id: str,
        related_issue_id: str,
        relation_type: Literal["blocks", "duplicate", "related"],
    ) -> dict[str, str]:
        """Create a relation between two issues via GraphQL."""
        mutation = """
        mutation CreateRelation($input: IssueRelationCreateInput!) {
          issueRelationCreate(input: $input) {
            success
            issueRelation { id type }
          }
        }
        """
        result = self._execute_raw(
            mutation,
            {
                "input": {
                    "issueId": issue_id,
                    "relatedIssueId": related_issue_id,
                    "type": relation_type,
                }
            },
        )
        rel = (result.get("issueRelationCreate") or {}).get("issueRelation") or {}
        return {
            "id": rel.get("id", ""),
            "type": rel.get("type", relation_type),
            "issue_id": issue_id,
            "related_issue_id": related_issue_id,
        }

    def get_issue_relations(self, issue_id: str) -> list[IssueRelation]:
        """Get all relations for an issue (blocks / duplicate / related).

        Returns an empty list when the issue has no relations. SDK errors
        propagate to the caller — they're meaningful (auth, not-found,
        rate-limit) and should not be hidden behind a falsy empty list.
        """
        linear_relations = self._client.issues.get_relations(issue_id=issue_id)
        return [IssueRelation.from_linear(r) for r in linear_relations]

    def list_sub_issues(self, issue_id: str) -> list[Issue]:
        """List all sub-issues (children) of a parent issue.

        Wraps linear_api.IssueManager.get_children, which returns a dict of
        {child_id: LinearIssue}. SDK errors propagate to the caller — an empty
        list here would silently hide auth/not-found/rate-limit failures.
        """
        linear_children = self._client.issues.get_children(issue_id)
        return [Issue.from_linear(child) for child in linear_children.values()]

    def add_comment_to_issue(self, comment: CommentInput) -> Comment:
        """Add a comment to an issue. Returns the created Comment.

        Linear's GraphQL schema uses the same `commentCreate` mutation for
        both issue and project comments — the difference is whether `issueId`
        or `projectId` is supplied in the input. There is no
        `issueCommentCreate` mutation.
        """
        try:
            query = """
            mutation CommentCreate($input: CommentCreateInput!) {
                commentCreate(input: $input) {
                    success
                    comment {
                        id
                        body
                        user {
                            id
                            name
                        }
                        createdAt
                    }
                }
            }
            """

            variables = {
                "input": {
                    "issueId": comment.issue_id,
                    "body": comment.body,
                }
            }

            result = self._execute_raw(query, variables)
            mutation_result = result.get("commentCreate") or {}
            if not mutation_result.get("success"):
                raise RuntimeError("commentCreate mutation returned success=false")
            comment_data = mutation_result.get("comment") or {}
            if not comment_data.get("id"):
                raise RuntimeError("commentCreate returned no comment data")
            user_data = comment_data.get("user") or {}
            return Comment(
                id=comment_data["id"],
                body=comment_data["body"],
                user=CommentUser(
                    id=user_data.get("id"),
                    name=user_data.get("name"),
                )
                if user_data
                else None,
                createdAt=comment_data.get("createdAt"),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to add comment to issue: {e}") from e

    def list_issue_comments(self, issue_id: str) -> list[Comment]:
        """List all comments on an issue."""
        try:
            linear_comments = self._client.issues.get_comments(issue_id)
            return [Comment.from_linear(comment) for comment in linear_comments]
        except Exception:
            return []

    def list_issue_attachments(self, issue_id: str) -> list[dict[str, Any]]:
        """List all attachments on an issue."""
        try:
            linear_attachments = self._client.issues.get_attachments(issue_id)
            return [
                {
                    "id": attachment.id,
                    "title": getattr(attachment, "title", None),
                    "url": getattr(attachment, "url", None),
                    "file_name": getattr(attachment, "file_name", None),
                    "file_size": getattr(attachment, "file_size", None),
                    "content_type": getattr(attachment, "content_type", None),
                    "created_at": getattr(attachment, "created_at", None),
                }
                for attachment in linear_attachments
            ]
        except Exception:
            return []

    def create_attachment(self, issue_id: str, title: str, url: str) -> dict[str, Any]:
        """Create an attachment on an issue.

        linear_api.IssueManager.create_attachment takes a LinearAttachmentInput
        (not kwargs) and returns the raw `attachmentCreate` GraphQL payload as
        a dict — `{"attachmentCreate": {"success": bool, "attachment": {...}}}`.
        We flatten that to `{"success": bool, "attachment": {...}}`.
        """
        try:
            attachment_input = LinearAttachmentInput(
                issueId=issue_id,
                title=title,
                url=url,
            )
            response = self._client.issues.create_attachment(
                attachment=attachment_input
            )
            payload = response.get("attachmentCreate") or {}
            return {
                "success": bool(payload.get("success", False)),
                "attachment": payload.get("attachment") or {},
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create attachment: {e}") from e

    def get_team_members(self, team_id: str) -> list[dict[str, Any]]:
        """Get all members of a team."""
        try:
            linear_members = self._client.teams.get_members(team_id)
            return [
                {
                    "id": member.id,
                    "name": member.name,
                    "email": getattr(member, "email", None),
                    "avatar_url": getattr(member, "avatar_url", None),
                }
                for member in linear_members
            ]
        except Exception:
            return []

    def get_team_labels(self, team_id: str) -> list[dict[str, Any]]:
        """Get all labels in a team."""
        try:
            linear_labels = self._client.teams.get_labels(team_id)
            return [
                {
                    "id": label.id,
                    "name": label.name,
                    "color": getattr(label, "color", None),
                    "description": getattr(label, "description", None),
                }
                for label in linear_labels
            ]
        except Exception:
            return []

    def get_team_issues(self, team_id: str) -> list[Issue]:
        """Get all issues in a team."""
        try:
            linear_issues = self._client.teams.get_issues(team_id)
            return [Issue.from_linear(issue) for issue in linear_issues.values()]
        except Exception:
            return []

    def get_team_projects(self, team_id: str) -> list[Project]:
        """Get all projects in a team."""
        try:
            linear_projects = self._client.teams.get_projects(team_id)
            return [
                Project.from_linear(project) for project in linear_projects.values()
            ]
        except Exception:
            return []

    def get_project_members(self, project_id: str) -> list[dict[str, Any]]:
        """Get all members of a project."""
        try:
            linear_members = self._client.projects.get_members(project_id)
            return [
                {
                    "id": member.id,
                    "name": member.name,
                    "email": getattr(member, "email", None),
                    "avatar_url": getattr(member, "avatar_url", None),
                }
                for member in linear_members
            ]
        except Exception:
            return []

    def get_project_labels(self, project_id: str) -> list[dict[str, Any]]:
        """Get all labels in a project."""
        try:
            linear_labels = self._client.projects.get_labels(project_id)
            return [
                {
                    "id": label.id,
                    "name": label.name,
                    "color": getattr(label, "color", None),
                    "description": getattr(label, "description", None),
                }
                for label in linear_labels
            ]
        except Exception:
            return []

    def get_project_comments(self, project_id: str) -> list[Comment]:
        """Get all comments on a project via direct GraphQL.

        Bypasses linear_api.projects.get_comments, which silently returns an
        empty list for projects that have comments (pagination/cache bug). We
        page through `project.comments` ourselves and return Comment objects
        populated with user info — something the library's flow loses, because
        its Comment model omits the `user` field.
        """
        query = """
        query($projectId: String!, $cursor: String) {
          project(id: $projectId) {
            comments(after: $cursor) {
              nodes {
                id
                body
                createdAt
                user { id name displayName email }
              }
              pageInfo { hasNextPage endCursor }
            }
          }
        }
        """

        comments: list[Comment] = []
        cursor: str | None = None

        while True:
            try:
                response = self._execute_raw(
                    query, {"projectId": project_id, "cursor": cursor}
                )
            except Exception:
                break

            # _execute_raw may return either unwrapped data ({"project": ...})
            # or the full envelope ({"data": {"project": ...}}); accept both.
            payload: Any = response
            if isinstance(response, dict) and isinstance(response.get("data"), dict):
                payload = response["data"]
            if not isinstance(payload, dict):
                break

            project = payload.get("project")
            if not isinstance(project, dict):
                break

            comments_conn = project.get("comments") or {}
            for node in comments_conn.get("nodes") or []:
                user_data = node.get("user") or {}
                comments.append(
                    Comment(
                        id=node["id"],
                        body=node["body"],
                        user=CommentUser(
                            id=user_data.get("id"),
                            name=user_data.get("name"),
                        )
                        if user_data
                        else None,
                        createdAt=node.get("createdAt"),
                    )
                )

            page_info = comments_conn.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            next_cursor = page_info.get("endCursor")
            if not next_cursor:
                break
            cursor = next_cursor

        return comments

    def add_comment_to_project(self, comment: ProjectCommentInput) -> Comment:
        """Add a comment to a project. Returns the created Comment."""
        try:
            query = """
            mutation CommentCreate($input: CommentCreateInput!) {
                commentCreate(input: $input) {
                    success
                    comment {
                        id
                        body
                        user {
                            id
                            name
                            displayName
                            email
                        }
                        createdAt
                    }
                }
            }
            """

            variables = {
                "input": {
                    "projectId": comment.project_id,
                    "body": comment.body,
                }
            }

            result = self._execute_raw(query, variables)
            mutation_result = result.get("commentCreate") or {}
            if not mutation_result.get("success"):
                raise RuntimeError("commentCreate mutation returned success=false")
            comment_data = mutation_result.get("comment") or {}
            if not comment_data.get("id"):
                raise RuntimeError("commentCreate returned no comment data")
            user_data = comment_data.get("user") or {}
            return Comment(
                id=comment_data["id"],
                body=comment_data["body"],
                user=CommentUser(
                    id=user_data.get("id"),
                    name=user_data.get("name"),
                    displayName=user_data.get("displayName"),
                    email=user_data.get("email"),
                )
                if user_data
                else None,
                createdAt=comment_data.get("createdAt"),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to add comment to project: {e}") from e
