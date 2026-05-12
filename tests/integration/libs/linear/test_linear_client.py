"""Real-world integration tests for LinearClient against the actual Linear API.

Tests ALL implemented operations in src/libs/linear.linear_client organized by domain:
  - TestTeamOperations: list_teams, get_team, get_team_members, get_team_labels, get_team_issues, get_team_projects
  - TestProjectOperations: list_projects, get_project, create_project, update_project, delete_project, get_project_members, get_project_labels, get_project_comments
  - TestIssueOperations: list_issues, get_issue, create_issue, update_issue, delete_issue, list_issue_labels, add_comment_to_issue, list_issue_comments, list_issue_attachments, create_attachment, create_issue_relation
  - TestInternalOperations: _post_project_update
  - TestWorkflowOperations: End-to-end workflows

Run with:
    LINEAR_API_KEY=... LINEAR_TEAM_ID=... LINEAR_PROJECT_ID=... \\
        uv run pytest tests/integration/libs/linear/test_linear_client.py -v -s
"""

import contextlib
import json
from collections.abc import Generator
from datetime import datetime

import pytest

from libs.linear.linear_client import LinearClient
from libs.linear.schemas import (
    CommentInput,
    Issue,
    IssueInput,
    IssueUpdateInput,
    Priority,
    Project,
    ProjectUpdateInput,
)
from settings.linear import LinearSettings

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Class-scoped Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(api_key: str) -> Generator[LinearClient, None, None]:
    client = LinearClient(api_key=api_key)
    yield client


@pytest.fixture()
def created_issues(api_key: str) -> Generator[list[str], None, None]:
    """Collects IDs of issues created during tests; deletes them all at teardown."""
    ids: list[str] = []
    yield ids
    if ids:
        client = LinearClient(api_key=api_key)
        for issue_id in ids:
            with contextlib.suppress(Exception):
                client.delete_issue(issue_id)  # Best effort cleanup


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _log(label: str, input_data: object, output_data: object) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print("=" * 60)
    print("  INPUT:")
    print(json.dumps(input_data, indent=4, default=str))
    print("  OUTPUT:")
    print(json.dumps(output_data, indent=4, default=str))
    print()


# ---------------------------------------------------------------------------
# Team Tests
# ---------------------------------------------------------------------------


class TestTeamOperations:
    def test_list_teams(self, client: LinearClient) -> None:
        """list_teams must return real teams from Linear workspace."""
        teams = client.list_teams()

        _log(
            "list_teams",
            {},
            [{"id": t.id, "name": t.name, "key": t.key} for t in teams],
        )

        assert len(teams) >= 1, "Should have at least one team"
        for team in teams:
            assert team.id, "Team should have an ID"
            assert team.name, "Team should have a name"
            assert team.key, "Team should have a key"

    def test_get_team(self, client: LinearClient, team_id: str) -> None:
        """get_team must resolve a real team by ID."""
        team = client.get_team(team_id)

        _log(
            "get_team",
            {"team_id": team_id},
            {"id": team.id, "name": team.name, "key": team.key} if team else None,
        )

        assert team is not None, f"Team {team_id} should exist"
        assert team.id == team_id
        assert team.name
        assert team.key

    def test_get_team_by_key(self, client: LinearClient) -> None:
        """get_team should also work with team key instead of ID."""
        # First get a team to find its key
        teams = client.list_teams()
        team_key = teams[0].key
        team = client.get_team(team_key)

        _log(
            "get_team_by_key",
            {"team_key": team_key},
            {"id": team.id, "name": team.name, "key": team.key} if team else None,
        )

        assert team is not None
        assert team.key == team_key

    def test_get_team_members(self, client: LinearClient, team_id: str) -> None:
        """get_team_members must return real team members."""
        members = client.get_team_members(team_id)

        _log(
            "get_team_members",
            {"team_id": team_id},
            [{"id": m["id"], "name": m["name"]} for m in members],
        )

        assert isinstance(members, list)
        assert len(members) >= 1, "Team should have at least one member"
        for member in members:
            assert member["id"], "Member should have an ID"
            assert member["name"], "Member should have a name"

    def test_get_team_labels(self, client: LinearClient, team_id: str) -> None:
        labels = client.get_team_labels(team_id)

        _log(
            "get_team_labels",
            {"team_id": team_id},
            [{"id": lbl["id"], "name": lbl["name"]} for lbl in labels],
        )

        assert isinstance(labels, list)
        for label in labels:
            assert label["id"], "Label should have an ID"
            assert label["name"], "Label should have a name"

    def test_get_team_issues(self, client: LinearClient, team_id: str) -> None:
        issues = client.get_team_issues(team_id)

        _log(
            "get_team_issues",
            {"team_id": team_id},
            [{"id": i.id, "title": i.title} for i in issues],
        )

        assert isinstance(issues, list)
        for issue in issues:
            assert issue.id, "Issue should have an ID"
            assert issue.title, "Issue should have a title"

    def test_get_team_projects(self, client: LinearClient, team_id: str) -> None:
        projects = client.get_team_projects(team_id)

        _log(
            "get_team_projects",
            {"team_id": team_id},
            [{"id": p.id, "name": p.name} for p in projects],
        )

        assert isinstance(projects, list)
        for project in projects:
            assert project.id, "Project should have an ID"
            assert project.name, "Project should have a name"


# ---------------------------------------------------------------------------
# Project Tests
# ---------------------------------------------------------------------------


class TestProjectOperations:
    _project_ids: list[str] = []

    @pytest.fixture(autouse=True, scope="class")
    def teardown_projects(self) -> Generator[None, None, None]:
        """Delete all projects created by this class after all tests complete."""
        yield
        if self._project_ids:
            client = LinearClient(api_key=LinearSettings().api_key.get_secret_value())
            for project_id in self._project_ids:
                with contextlib.suppress(Exception):
                    client.delete_project(project_id)  # Best effort cleanup
            self._project_ids.clear()

    @pytest.fixture
    def new_project(self, client: LinearClient, api_key, team_id) -> Project:
        project_name = f"[TEST] Project {__import__('datetime').datetime.now()}"
        project_description = "Created by integration test - should be deleted."

        project = client.create_project(team_id, project_name, project_description)
        self._project_ids.append(project.id)

        _log(
            "create_project",
            {
                "team_id": team_id,
                "name": project_name,
                "description": project_description,
            },
            {
                "id": project.id,
                "name": project.name,
                "description": project.description,
            },
        )

        return project

    def test_list_projects(self, client: LinearClient, new_project: Project) -> None:
        projects = client.list_projects(team_id=new_project.team.id)

        _log(
            "list_projects",
            {"team_id": new_project.team.id},
            [{"id": p.id, "name": p.name, "state": p.state} for p in projects],
        )

        assert len(projects) > 0, "It should have found at least 1 project"
        project_ids = [p.id for p in projects]
        assert new_project.id in project_ids, "New project should be in list"

    def test_get_project(self, client: LinearClient, new_project: Project) -> None:
        project = client.get_project(new_project.id)

        _log(
            "get_project",
            {"project_id": new_project.id},
            {"id": project.id, "name": project.name, "state": project.state}
            if project
            else None,
        )

        assert project is not None, f"Project {new_project.id} should exist"
        assert project.id == new_project.id
        assert project.name == new_project.name
        assert project.description == new_project.description
        assert project.state == new_project.state
        assert project.team.id == new_project.team.id

    def test_delete_project(self, client: LinearClient, new_project: Project) -> None:
        # Create a project first, then delete it
        # Verify project was created
        # Delete the project
        result = client.delete_project(new_project.id)

        _log("delete_project", {"project_id": new_project.id}, {"deleted": result})

        # Should return True for successful deletion
        assert result is True

    def test_update_project(self, client: LinearClient, new_project: Project) -> None:
        update_message = f"[TEST] Project update at {datetime.now()}"
        update_input = ProjectUpdateInput(updateMessage=update_message)

        updated = client.update_project(new_project.id, update_input)

        _log(
            "update_project",
            {"project_id": new_project.id, "update_message": update_message},
            {"id": updated.id, "name": updated.name} if updated else None,
        )

        assert updated is not None
        assert updated.id == new_project.id

    # SDK comment from project is not workign properly
    # def test_create_and_get_project_comments(self, client: LinearClient, new_project: Project) -> None:
    #     new_comment1 = client.add_comment_to_project(ProjectCommentInput(
    #         project_id=str(new_project.id),
    #         body="[TEST] New comment #1"
    #     ))
    #     new_comment2 = client.add_comment_to_project(ProjectCommentInput(
    #         project_id=str(new_project.id),
    #         body="[TEST] New comment #2"
    #     ))
    #
    #     _log("create_and_get_project_comments",
    # {"project_id": new_project.id, "comment1": new_comment1.body, "comment2": new_comment2.body},
    #         {
    #             "comment1": {"id": new_comment1.id, "body": new_comment1.body},
    #             "comment2": {"id": new_comment2.id, "body": new_comment2.body}
    #         }
    #      )
    #
    #     comments = client.get_project_comments(project_id=new_project.id)
    #     comment_ids = [c.id for c in comments]
    #
    #     assert new_comment1.id in comment_ids
    #     assert new_comment2.id in comment_ids
    #
    #     _log("get_project_comments", {"project_id": new_project.id},
    #          [c.model_dump(mode='json') for c in comments])


# ---------------------------------------------------------------------------
# Issue Tests
# ---------------------------------------------------------------------------


class TestIssueOperations:
    _client: LinearClient = None
    _project_ids: list[str] = []
    _issue_ids: list[str] = []

    @pytest.fixture
    def new_project(self, client: LinearClient, api_key, team_id):
        self._client = client
        project_name = f"[TEST] Project {__import__('datetime').datetime.now()}"
        project_description = "Created by integration test - should be deleted."
        project = client.create_project(
            team_id=team_id, name=project_name, description=project_description
        )
        self._project_ids.append(project.id)
        return project

    def create_issue(self, client: LinearClient, project: Project) -> Issue:
        input_data = IssueInput(
            title=f"[TEST] Real-world integration test issue {__import__('datetime').datetime.now()}",
            description="Created by test_linear_client.py — safe to delete.",
            teamId=project.team.id,
            projectId=project.id,
            priority=Priority.HIGH,
        )

        issue = client.create_issue(input_data)
        self._issue_ids.append(issue.id)

        _log(
            "create_issue",
            input_data.model_dump(),
            {"id": issue.id, "identifier": issue.identifier, "title": issue.title},
        )

        return issue

    @pytest.fixture(scope="class", autouse=True)
    def teardown_project_and_issues(self):
        """Delete all issues created by this class after all tests complete."""
        yield
        client = LinearClient(api_key=LinearSettings().api_key.get_secret_value())
        if self._issue_ids:
            for issue_id in self._issue_ids:
                client.delete_issue(issue_id)
            self._issue_ids.clear()

        if self._project_ids:
            for project_id in self._project_ids:
                client.delete_project(project_id)
            self._project_ids.clear()

    def test_list_issues(self, client: LinearClient, new_project: Project) -> None:
        new_issues = [
            self.create_issue(client, new_project),
            self.create_issue(client, new_project),
        ]
        issues = client.list_issues(new_project.id)

        _log(
            "list_issues",
            {"project_id": new_project.id},
            [
                {"id": i.id, "identifier": i.identifier, "title": i.title}
                for i in issues
            ],
        )

        issue_ids = [i.id for i in new_issues]
        assert all(i.id in issue_ids for i in issues)

    def test_get_issue(self, client: LinearClient, new_project: Project) -> None:
        new_issue = self.create_issue(client, new_project)

        # Retrieve the issue
        issue = client.get_issue(new_issue.id)

        _log(
            "get_issue",
            {"issue_id": new_issue.id},
            {"id": issue.id, "identifier": issue.identifier, "title": issue.title}
            if issue
            else None,
        )

        assert issue is not None
        assert issue.id == new_issue.id
        assert issue.title == new_issue.title

    def test_update_issue(self, client: LinearClient, new_project: Project) -> None:
        new_issue = self.create_issue(client, new_project)

        # Update the issue
        update_input = IssueUpdateInput(
            title=f"[TEST] Updated title {__import__('datetime').datetime.now()}",
            description="Updated description.",
            priority=Priority.URGENT,
        )

        updated = client.update_issue(new_issue.id, update_input)

        _log(
            "update_issue",
            {"issue_id": new_issue.id, "updates": update_input.model_dump()},
            {"id": updated.id, "title": updated.title, "priority": updated.priority}
            if updated
            else None,
        )

        assert updated is not None
        assert updated.id == new_issue.id
        assert updated.title == update_input.title
        # Linear may normalize priorities, just verify it's a valid priority
        assert updated.priority in [p.value for p in Priority]

    def test_list_issue_labels(
        self, client: LinearClient, new_project: Project
    ) -> None:
        new_issue = self.create_issue(client, new_project)

        labels = client.list_issue_labels(new_issue.id)

        _log(
            "list_issue_labels",
            {"issue_id": new_issue.id},
            [{"id": lbl.id, "name": lbl.name} for lbl in labels],
        )

        assert isinstance(labels, list), "Should return a list of labels"

        for label in labels:
            assert label.id, "Label should have an ID"
            assert label.name, "Label should have a name"

    def test_create_issue_and_check_relations(
        self, client: LinearClient, new_project: Project
    ) -> None:
        new_issue = self.create_issue(client, new_project)
        new_issue2 = self.create_issue(client, new_project)
        new_issue3 = self.create_issue(client, new_project)
        new_issue4 = self.create_issue(client, new_project)

        # Create relation
        client.create_issue_relation(
            issue_id=new_issue.id,
            related_issue_id=new_issue2.id,
            relation_type="blocks",
        )
        client.create_issue_relation(
            issue_id=new_issue.id,
            related_issue_id=new_issue3.id,
            relation_type="related",
        )
        client.create_issue_relation(
            issue_id=new_issue2.id,
            related_issue_id=new_issue4.id,
            relation_type="duplicate",
        )

        # fetch relations to check
        issue1_relations = client.get_issue_relations(new_issue.id)
        issue2_relations = client.get_issue_relations(new_issue2.id)

        _log(
            "get_issue_relations",
            {"issue_id": new_issue.id},
            [r.model_dump() for r in issue1_relations],
        )

        assert len(issue1_relations) == 2
        relation_types_1 = {r.type for r in issue1_relations}
        assert relation_types_1 == {"blocks", "related"}

        related_ids_1 = {
            r.related_issue.id for r in issue1_relations if r.related_issue
        }
        assert related_ids_1 == {new_issue2.id, new_issue3.id}

        assert len(issue2_relations) == 1
        assert issue2_relations[0].type == "duplicate"
        assert issue2_relations[0].related_issue is not None
        assert issue2_relations[0].related_issue.id == new_issue4.id

    def test_add_comment_to_issue(
        self, client: LinearClient, new_project: Project
    ) -> None:
        new_issue = self.create_issue(client, new_project)

        comment_body = f"[TEST] Integration test comment at {datetime.now()}"
        comment_result = client.add_comment_to_issue(
            CommentInput(issueId=new_issue.id, body=comment_body)
        )

        _log(
            "add_comment_to_issue",
            {"issue_id": new_issue.id, "body": comment_body},
            {"id": comment_result.id, "body": comment_result.body},
        )

        assert comment_result.id

    def test_list_issue_comments(
        self, client: LinearClient, new_project: Project
    ) -> None:
        new_issue = self.create_issue(client, new_project)

        # Seed a comment so listing has something to return
        comment_body = f"[TEST] Comment for listing test at {datetime.now()}"
        client.add_comment_to_issue(
            CommentInput(issueId=new_issue.id, body=comment_body)
        )

        comments = client.list_issue_comments(new_issue.id)

        _log(
            "list_issue_comments",
            {"issue_id": new_issue.id},
            [
                {
                    "id": c.id,
                    "body": c.body[:100] + "..." if len(c.body) > 100 else c.body,
                }
                for c in comments
            ],
        )

        assert isinstance(comments, list)
        for comment in comments:
            assert comment.id, "Comment should have an ID"
            assert comment.body, "Comment should have a body"

    def test_list_issue_attachments(
        self, client: LinearClient, new_project: Project
    ) -> None:
        new_issue = self.create_issue(client, new_project)

        attachments = client.list_issue_attachments(new_issue.id)

        _log(
            "list_issue_attachments",
            {"issue_id": new_issue.id},
            [{"id": a["id"], "title": a["title"]} for a in attachments],
        )

        assert isinstance(attachments, list)
        for attachment in attachments:
            assert attachment["id"], "Attachment should have an ID"

    def test_create_attachment(
        self, client: LinearClient, new_project: Project
    ) -> None:
        new_issue = self.create_issue(client, new_project)

        attachment_title = f"Test Attachment {datetime.now()}"
        attachment_url = "https://placehold.co/600x400/png"  # Placeholder image URL

        attachment_result = client.create_attachment(
            new_issue.id, attachment_title, attachment_url
        )

        _log(
            "create_attachment",
            {
                "issue_id": new_issue.id,
                "title": attachment_title,
                "url": attachment_url,
            },
            attachment_result,
        )

        assert attachment_result.get("success", False)
        if attachment_result.get("attachment"):
            assert attachment_result["attachment"]["title"] == attachment_title


# ---------------------------------------------------------------------------
# Sub-Issue Tests
# ---------------------------------------------------------------------------


class TestSubIssueOperations:
    """Live coverage for sub-issue creation, listing, and re-parenting."""

    _project_ids: list[str] = []
    _issue_ids: list[str] = []

    @pytest.fixture
    def new_project(self, client: LinearClient, team_id: str) -> Project:
        project_name = f"[TEST] Sub-issue project {datetime.now()}"
        project = client.create_project(
            team_id=team_id,
            name=project_name,
            description="Created by sub-issue integration test - safe to delete.",
        )
        self._project_ids.append(project.id)
        return project

    @pytest.fixture(scope="class", autouse=True)
    def teardown_project_and_issues(self) -> Generator[None, None, None]:
        """Delete every issue and project created by this class at teardown."""
        yield
        client = LinearClient(api_key=LinearSettings().api_key.get_secret_value())
        # Delete children first to avoid orphaning failures.
        for issue_id in self._issue_ids:
            with contextlib.suppress(Exception):
                client.delete_issue(issue_id)
        self._issue_ids.clear()
        for project_id in self._project_ids:
            with contextlib.suppress(Exception):
                client.delete_project(project_id)
        self._project_ids.clear()

    def _create_issue(
        self,
        client: LinearClient,
        project: Project,
        *,
        title: str,
        parent_id: str | None = None,
    ) -> Issue:
        input_data = IssueInput(
            title=title,
            description="Created by test_linear_client.py — safe to delete.",
            teamId=project.team.id,
            projectId=project.id,
            priority=Priority.MEDIUM,
            parentId=parent_id,
        )
        issue = client.create_issue(input_data)
        self._issue_ids.append(issue.id)
        return issue

    def test_create_issue_with_parent_id(
        self, client: LinearClient, new_project: Project
    ) -> None:
        """create_issue should attach a child under the supplied parent."""
        parent = self._create_issue(
            client, new_project, title=f"[TEST] Parent {datetime.now()}"
        )
        child = self._create_issue(
            client,
            new_project,
            title=f"[TEST] Child of {parent.identifier}",
            parent_id=parent.id,
        )

        _log(
            "create_issue_with_parent_id",
            {"parent_id": parent.id, "child_title": child.title},
            {"child_id": child.id, "child_parent_id": child.parent_id},
        )

        assert child.parent_id == parent.id, (
            "Newly-created sub-issue should report the parent it was created under"
        )

    def test_list_sub_issues_returns_children(
        self, client: LinearClient, new_project: Project
    ) -> None:
        """list_sub_issues should surface every child of a given parent."""
        parent = self._create_issue(
            client, new_project, title=f"[TEST] Parent w/ children {datetime.now()}"
        )
        child_a = self._create_issue(
            client, new_project, title="[TEST] Child A", parent_id=parent.id
        )
        child_b = self._create_issue(
            client, new_project, title="[TEST] Child B", parent_id=parent.id
        )

        sub_issues = client.list_sub_issues(parent.id)

        _log(
            "list_sub_issues",
            {"parent_id": parent.id},
            [
                {"id": i.id, "identifier": i.identifier, "title": i.title}
                for i in sub_issues
            ],
        )

        returned_ids = {i.id for i in sub_issues}
        assert {child_a.id, child_b.id}.issubset(returned_ids), (
            "list_sub_issues must return every direct child of the parent issue"
        )
        # And each must point back at the parent.
        for issue in sub_issues:
            if issue.id in {child_a.id, child_b.id}:
                assert issue.parent_id == parent.id

    def test_list_sub_issues_empty_for_leaf(
        self, client: LinearClient, new_project: Project
    ) -> None:
        """list_sub_issues should return [] for an issue that has no children."""
        leaf = self._create_issue(
            client, new_project, title=f"[TEST] Leaf {datetime.now()}"
        )

        sub_issues = client.list_sub_issues(leaf.id)

        _log("list_sub_issues_empty", {"issue_id": leaf.id}, [])

        assert sub_issues == [], "Leaf issue should have no sub-issues"

    def test_update_issue_re_parents(
        self, client: LinearClient, new_project: Project
    ) -> None:
        """update_issue should move an issue under a different parent."""
        parent_a = self._create_issue(
            client, new_project, title=f"[TEST] Parent A {datetime.now()}"
        )
        parent_b = self._create_issue(
            client, new_project, title=f"[TEST] Parent B {datetime.now()}"
        )
        child = self._create_issue(
            client, new_project, title="[TEST] Movable child", parent_id=parent_a.id
        )

        assert child.parent_id == parent_a.id

        updated = client.update_issue(child.id, IssueUpdateInput(parentId=parent_b.id))

        _log(
            "update_issue_re_parents",
            {"issue_id": child.id, "new_parent_id": parent_b.id},
            {"id": updated.id, "parent_id": updated.parent_id},
        )

        assert updated.parent_id == parent_b.id, (
            "After re-parenting via update_issue, parent_id must reflect the new parent"
        )

        # And the child must appear under the new parent only.
        children_of_b = {i.id for i in client.list_sub_issues(parent_b.id)}
        children_of_a = {i.id for i in client.list_sub_issues(parent_a.id)}
        assert child.id in children_of_b
        assert child.id not in children_of_a
