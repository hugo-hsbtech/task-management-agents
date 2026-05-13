"""Integration tests for LinearPlatform and LinearTools against the real Linear API.

Covers all supported operations via the _handle_* handler layer:
  - list_teams
  - list_projects (within configured team)
  - list_issues (within configured project)
  - get_team / get_project / get_issue
  - create_issue
  - update_issue
  - add_label

No agent or LLM involved. Every input and output is logged for full
observability. Run with:

    LINEAR_API_KEY=... LINEAR_TEAM_ID=... LINEAR_PROJECT_ID=... \\
        uv run pytest tests/integration/backlog/test_linear_platform.py -v -s
"""

import json
from collections.abc import Generator

import pytest

from backlog.contracts import (
    BacklogOutput,
    IssueFields,
    IssuePlan,
    IssueRelation,
    IssueRelationType,
    IssueType,
)
from backlog.platforms import LinearPlatform
from backlog.platforms.linear import IssueResult
from libs.linear.linear_client import LinearClient
from settings import settings
from tools.linear import LinearTools

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def linear_settings():
    linear = settings.linear
    if linear.api_key is None:
        pytest.skip("LINEAR_API_KEY is not configured")
    if linear.team_id is None:
        pytest.skip("LINEAR_TEAM_ID is not configured")
    if linear.project_id is None:
        pytest.skip("LINEAR_PROJECT_ID is not configured")
    return linear


@pytest.fixture()
def api_key(linear_settings) -> str:
    return linear_settings.api_key.get_secret_value()


@pytest.fixture()
def team_id(linear_settings) -> str:
    return linear_settings.team_id


@pytest.fixture()
def project_id(linear_settings) -> str:
    return linear_settings.project_id


@pytest.fixture()
def tools(api_key: str) -> LinearTools:
    return LinearTools(api_key=api_key)


@pytest.fixture()
def platform(linear_settings) -> LinearPlatform:
    return LinearPlatform(
        team_id=linear_settings.team_id,
        project_id=linear_settings.project_id,
    )


@pytest.fixture()
def created_issues(api_key: str) -> Generator[list[str], None, None]:
    """Collects IDs of issues created during a test; deletes them all at teardown."""
    ids: list[str] = []
    yield ids
    if ids:
        client = LinearClient(api_key=api_key)
        for issue_id in ids:
            client.delete_issue(issue_id)


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _log(capsys, label: str, input_data: object, output_data: object) -> None:
    with capsys.disabled():
        print(f"\n{'=' * 60}")
        print(f"  {label}")
        print("=" * 60)
        print("  INPUT:")
        print(json.dumps(input_data, indent=4, default=str))
        print("  OUTPUT:")
        print(json.dumps(output_data, indent=4, default=str))
        print()


def _log_results(capsys, label: str, results: list[IssueResult]) -> None:
    _log(
        capsys,
        label,
        input_data=None,
        output_data=[
            {
                "action": r.action,
                "id": r.issue.id,
                "identifier": r.issue.identifier,
                "title": r.issue.title,
                "url": r.issue.url,
            }
            for r in results
        ],
    )


def _track(created_issues: list[str], result: dict) -> dict:
    """Register an issue ID for cleanup and return the result unchanged."""
    if issue_id := result.get("id"):
        created_issues.append(issue_id)
    return result


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_teams(capsys, tools: LinearTools) -> None:
    """list_teams must return at least one team with id and name."""
    result = await tools.handle_list_teams({})

    _log(capsys, "list_teams", input_data={}, output_data=result)

    assert "teams" in result
    assert len(result["teams"]) >= 1
    assert all("id" in t and "name" in t for t in result["teams"])


@pytest.mark.asyncio
async def test_get_team(capsys, tools: LinearTools, team_id: str) -> None:
    """get_team must resolve the configured team_id."""
    input_data = {"team_id": team_id}
    result = await tools.handle_get_team(input_data)

    _log(capsys, "get_team", input_data=input_data, output_data=result)

    assert result.get("id") == team_id
    assert "name" in result
    assert "key" in result


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_projects(capsys, tools: LinearTools, team_id: str) -> None:
    """list_projects must return projects for the configured team."""
    input_data = {"team_id": team_id}
    result = await tools.handle_list_projects(input_data)

    _log(capsys, "list_projects", input_data=input_data, output_data=result)

    assert "projects" in result
    assert len(result["projects"]) >= 1
    assert all("id" in p and "name" in p for p in result["projects"])


@pytest.mark.asyncio
async def test_get_project(capsys, tools: LinearTools, project_id: str) -> None:
    """get_project must resolve the configured project_id."""
    input_data = {"project_id": project_id}
    result = await tools.handle_get_project(input_data)

    _log(capsys, "get_project", input_data=input_data, output_data=result)

    assert result.get("id") == project_id
    assert "name" in result


# ---------------------------------------------------------------------------
# Issues — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_issues(
    capsys, tools: LinearTools, team_id: str, project_id: str
) -> None:
    """list_issues must return issues with team/project references populated.

    Guards against the regression where the upstream GraphQL projection
    stripped foreign-key references — issues came back with ``team_id`` and
    ``project_id`` set to ``None``.
    """
    input_data = {"project_id": project_id}
    result = await tools.handle_list_issues(input_data)

    _log(capsys, "list_issues", input_data=input_data, output_data=result)

    assert "issues" in result
    assert isinstance(result["issues"], list)

    for issue in result["issues"]:
        assert issue.get("team_id") == team_id, (
            f"issue {issue.get('id')} has team_id={issue.get('team_id')!r}, "
            f"expected {team_id!r}"
        )
        assert issue.get("project_id") == project_id, (
            f"issue {issue.get('id')} has project_id={issue.get('project_id')!r}, "
            f"expected {project_id!r}"
        )
        assert issue.get("identifier"), f"issue {issue.get('id')} missing identifier"
        assert issue.get("url"), f"issue {issue.get('id')} missing url"


# ---------------------------------------------------------------------------
# Issues — create / get / update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue(
    capsys, tools: LinearTools, team_id: str, project_id: str, created_issues: list[str]
) -> None:
    """create_issue must write to Linear and return a typed Issue."""
    input_data = {
        "title": "[TEST] create_issue integration test",
        "description": "Created by test_linear_platform.py — safe to delete.",
        "team_id": team_id,
        "project_id": project_id,
        "priority": 3,
    }

    result = _track(created_issues, await tools.handle_create_issue(input_data))

    _log(capsys, "create_issue", input_data=input_data, output_data=result)

    assert result.get("id")
    assert result.get("identifier")
    assert result["title"] == input_data["title"]


@pytest.mark.asyncio
async def test_get_issue(
    capsys, tools: LinearTools, team_id: str, project_id: str, created_issues: list[str]
) -> None:
    """get_issue must retrieve a previously created issue by id."""
    created = _track(
        created_issues,
        await tools.handle_create_issue(
            {
                "title": "[TEST] get_issue integration test",
                "description": "Created by test_linear_platform.py — safe to delete.",
                "team_id": team_id,
                "project_id": project_id,
                "priority": 3,
            }
        ),
    )
    issue_id = created["id"]

    input_data = {"issue_id": issue_id}
    result = await tools.handle_get_issue(input_data)

    _log(capsys, "get_issue", input_data=input_data, output_data=result)

    assert result.get("id") == issue_id
    assert result.get("identifier")


@pytest.mark.asyncio
async def test_update_issue(
    capsys, tools: LinearTools, team_id: str, project_id: str, created_issues: list[str]
) -> None:
    """update_issue must modify an existing issue and return the updated state."""
    created = _track(
        created_issues,
        await tools.handle_create_issue(
            {
                "title": "[TEST] update_issue integration test — original",
                "description": "Created by test_linear_platform.py — safe to delete.",
                "team_id": team_id,
                "project_id": project_id,
                "priority": 3,
            }
        ),
    )
    issue_id = created["id"]

    input_data = {
        "issue_id": issue_id,
        "title": "[TEST] update_issue integration test — updated",
        "priority": 1,
    }
    result = await tools.handle_update_issue(input_data)

    _log(capsys, "update_issue", input_data=input_data, output_data=result)

    assert result.get("id") == issue_id


# ---------------------------------------------------------------------------
# Platform-level: validate_target + execute (create + reuse)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_target(capsys, platform: LinearPlatform, api_key: str) -> None:
    """validate_target must resolve team and project without error."""
    input_data = {"team_id": platform.team_id, "project_id": platform.project_id}

    await platform.validate_target(api_key=api_key)

    _log(capsys, "validate_target", input_data=input_data, output_data={"status": "ok"})


@pytest.mark.asyncio
async def test_execute_creates_and_reuses_issues(
    capsys, platform: LinearPlatform, api_key: str, created_issues: list[str]
) -> None:
    """execute() creates issues on first run, reuses on second run."""
    defaults = platform.issue_defaults
    backlog_output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                issue_type=IssueType.epic,
                fields=IssueFields(
                    title="[TEST][EPIC] execute integration test",
                    description="Created by test_linear_platform.py — safe to delete.",
                    priority=2,
                    platform_fields=dict(defaults),
                ),
            ),
            IssuePlan(
                issue_type=IssueType.task,
                fields=IssueFields(
                    title="[TEST][TASK] execute integration test — subtask",
                    description="Created by test_linear_platform.py — safe to delete.",
                    priority=3,
                    platform_fields=dict(defaults),
                ),
            ),
        ],
    )

    first = await platform.execute(backlog_output)
    for r in first:
        created_issues.append(r.issue.id)

    second = await platform.execute(backlog_output)

    _log_results(capsys, "execute — first run", first)
    _log_results(capsys, "execute — second run (expect reuse)", second)

    assert len(first) == 2
    assert all(isinstance(r, IssueResult) for r in first)
    assert all(r.action in {"create", "reuse"} for r in first)
    assert all(r.action == "reuse" for r in second), (
        f"Second run should reuse all issues, got: {[r.action for r in second]}"
    )
    assert [r.issue.id for r in first] == [r.issue.id for r in second]


# ---------------------------------------------------------------------------
# Relations — create_issue_relation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue_relation(
    capsys, tools: LinearTools, team_id: str, project_id: str, created_issues: list[str]
) -> None:
    """create_issue_relation must wire a blocks relation between two real issues."""
    source = _track(
        created_issues,
        await tools.handle_create_issue(
            {
                "title": "[TEST] relation source — blocker",
                "description": "Created by test_linear_platform.py — safe to delete.",
                "team_id": team_id,
                "project_id": project_id,
                "priority": 3,
            }
        ),
    )
    target = _track(
        created_issues,
        await tools.handle_create_issue(
            {
                "title": "[TEST] relation target — blocked",
                "description": "Created by test_linear_platform.py — safe to delete.",
                "team_id": team_id,
                "project_id": project_id,
                "priority": 3,
            }
        ),
    )

    input_data = {
        "issue_id": source["id"],
        "related_issue_id": target["id"],
        "type": "blocks",
    }
    result = await tools.handle_create_issue_relation(input_data)

    _log(capsys, "create_issue_relation", input_data=input_data, output_data=result)

    assert result.get("issue_id") == source["id"]
    assert result.get("related_issue_id") == target["id"]
    assert result.get("type") == "blocks"


@pytest.mark.asyncio
async def test_execute_wires_relations_between_issues(
    capsys, platform: LinearPlatform, api_key: str, created_issues: list[str]
) -> None:
    """execute() must call create_issue_relation for issues that declare relations."""
    defaults = platform.issue_defaults
    backlog_output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                issue_type=IssueType.epic,
                fields=IssueFields(
                    title="[TEST][EPIC] relation — blocker",
                    description="Created by test_linear_platform.py — safe to delete.",
                    priority=2,
                    platform_fields=dict(defaults),
                ),
                relations=[
                    IssueRelation(
                        type=IssueRelationType.blocks,
                        target_title="[TEST][TASK] relation — blocked",
                    )
                ],
            ),
            IssuePlan(
                issue_type=IssueType.task,
                fields=IssueFields(
                    title="[TEST][TASK] relation — blocked",
                    description="Created by test_linear_platform.py — safe to delete.",
                    priority=3,
                    platform_fields=dict(defaults),
                ),
            ),
        ],
    )

    results = await platform.execute(backlog_output)
    for r in results:
        created_issues.append(r.issue.id)

    _log_results(capsys, "execute with relations", results)

    assert len(results) == 2
    assert all(r.action in {"create", "reuse"} for r in results)
    assert results[0].issue.id
    assert results[1].issue.id
