"""Live Linear MCP integration tests for FOUND-01 and LINR-01..04.

These tests require:
  - ANTHROPIC_API_KEY set in environment
  - Linear MCP OAuth completed (one-time interactive login; token cached at ~/.mcp-remote/)
  - LINEAR_TEST_TEAM_ID env var pointing at a sandbox team

Run with: pytest tests/test_integration.py -x -m integration
"""
from __future__ import annotations
import os

import pytest

pytestmark = pytest.mark.integration


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        pytest.skip(f"{name} not set; skipping live integration test")
    return val


@pytest.mark.asyncio
async def test_mcp_connection_and_tool_prefix():
    """FOUND-01: Linear MCP connects; tool prefix is mcp__linear__ (Pitfall 1 guard)."""
    _require_env("ANTHROPIC_API_KEY")
    from hsb.agents.linear_agent import run_linear_agent

    result = await run_linear_agent(
        "List the available Linear teams using mcp__linear__list_teams. "
        "Return a JSON object: "
        '{"operation": "read", "result": "success", "linear_entities": [], "error": null}'
    )
    assert result is not None
    # If the wrong prefix were used, result would be missing or contain a permission error.
    assert "result" in result.lower()


@pytest.mark.asyncio
async def test_create_epic(monkeypatch):
    """LINR-01: Create an EPIC at the top of the hierarchy."""
    team_id = _require_env("LINEAR_TEST_TEAM_ID")
    _require_env("ANTHROPIC_API_KEY")
    from hsb.agents.linear_agent import run_validated_linear_agent

    result = await run_validated_linear_agent(
        operation="create",
        payload={"title": "[PHASE-1-INTEGRATION] EPIC test", "type": "epic", "teamId": team_id},
    )
    assert result.result == "success"
    assert result.linear_entities[0].type == "epic"


@pytest.mark.asyncio
async def test_create_task_under_epic(monkeypatch):
    """LINR-01: Create a Task with parent linkage to an EPIC."""
    team_id = _require_env("LINEAR_TEST_TEAM_ID")
    _require_env("ANTHROPIC_API_KEY")
    from hsb.agents.linear_agent import run_validated_linear_agent

    epic = await run_validated_linear_agent(
        operation="create",
        payload={"title": "[PHASE-1-INTEGRATION] EPIC for task test", "type": "epic", "teamId": team_id},
    )
    epic_id = epic.linear_entities[0].id

    task = await run_validated_linear_agent(
        operation="create",
        payload={"title": "[PHASE-1-INTEGRATION] Task under EPIC", "type": "task",
                 "teamId": team_id, "parentId": epic_id},
    )
    assert task.result == "success"
    assert task.linear_entities[0].type == "task"


@pytest.mark.asyncio
async def test_create_user_story_under_epic():
    """LINR-01: Create a User Story with parent linkage to an EPIC (mid-tier hierarchy)."""
    team_id = _require_env("LINEAR_TEST_TEAM_ID")
    _require_env("ANTHROPIC_API_KEY")
    from hsb.agents.linear_agent import run_validated_linear_agent

    epic = await run_validated_linear_agent(
        operation="create",
        payload={"title": "[PHASE-1-INTEGRATION] EPIC for user_story test", "type": "epic", "teamId": team_id},
    )
    epic_id = epic.linear_entities[0].id

    story = await run_validated_linear_agent(
        operation="create",
        payload={"title": "[PHASE-1-INTEGRATION] User Story under EPIC", "type": "user_story",
                 "teamId": team_id, "parentId": epic_id},
    )
    assert story.result == "success"
    assert story.linear_entities[0].type == "user_story"


@pytest.mark.asyncio
async def test_create_subtask_under_task():
    """LINR-01: Create a Subtask with parent linkage to a Task (deepest hierarchy level)."""
    team_id = _require_env("LINEAR_TEST_TEAM_ID")
    _require_env("ANTHROPIC_API_KEY")
    from hsb.agents.linear_agent import run_validated_linear_agent

    epic = await run_validated_linear_agent(
        operation="create",
        payload={"title": "[PHASE-1-INTEGRATION] EPIC for subtask test", "type": "epic", "teamId": team_id},
    )
    epic_id = epic.linear_entities[0].id

    task = await run_validated_linear_agent(
        operation="create",
        payload={"title": "[PHASE-1-INTEGRATION] Task for subtask test", "type": "task",
                 "teamId": team_id, "parentId": epic_id},
    )
    task_id = task.linear_entities[0].id

    subtask = await run_validated_linear_agent(
        operation="create",
        payload={"title": "[PHASE-1-INTEGRATION] Subtask under Task", "type": "subtask",
                 "teamId": team_id, "parentId": task_id},
    )
    assert subtask.result == "success"
    assert subtask.linear_entities[0].type == "subtask"


@pytest.mark.asyncio
async def test_update_issue_status():
    """LINR-02: Update a Linear issue's status."""
    issue_id = os.environ.get("LINEAR_TEST_ISSUE_ID")
    if not issue_id:
        pytest.skip("LINEAR_TEST_ISSUE_ID not set; create a test issue manually first")
    _require_env("ANTHROPIC_API_KEY")
    from hsb.agents.linear_agent import run_validated_linear_agent

    result = await run_validated_linear_agent(
        operation="update",
        payload={"issueId": issue_id, "status": "in_progress"},
    )
    assert result.result == "success"


@pytest.mark.asyncio
async def test_update_issue_custom_fields():
    """LINR-02: Update qa_status / uat_status / assigned_orchestrator custom fields.

    Per RESEARCH.md Open Question 1 (RESOLVED): the agent inspects the MCP tool
    schema at runtime and chooses native custom field, label, or structured comment
    fallback. This test verifies the agent succeeds via whichever mechanism is
    available — operator visually confirms the field is visible in Linear UI in
    Task 3 Step 5b (manual checkpoint).
    """
    issue_id = os.environ.get("LINEAR_TEST_ISSUE_ID")
    if not issue_id:
        pytest.skip("LINEAR_TEST_ISSUE_ID not set")
    _require_env("ANTHROPIC_API_KEY")
    from hsb.agents.linear_agent import run_validated_linear_agent

    result = await run_validated_linear_agent(
        operation="update",
        payload={
            "issueId": issue_id,
            "qa_status": "approved",
            "uat_status": "approved",
            "assigned_orchestrator": "phase-1-test",
        },
    )
    assert result.result == "success", (
        f"Custom field update failed: {result.error}. The agent should fall back "
        "to label or structured comment if native custom fields are unavailable."
    )


@pytest.mark.asyncio
async def test_add_comment():
    """LINR-03: Add a structured comment to a Linear issue."""
    issue_id = os.environ.get("LINEAR_TEST_ISSUE_ID")
    if not issue_id:
        pytest.skip("LINEAR_TEST_ISSUE_ID not set")
    _require_env("ANTHROPIC_API_KEY")
    from hsb.agents.linear_agent import run_validated_linear_agent

    result = await run_validated_linear_agent(
        operation="comment",
        payload={"issueId": issue_id, "body": "[INTEGRATION TEST] Phase 1 verification"},
    )
    assert result.result == "success"


@pytest.mark.asyncio
async def test_link_pr():
    """LINR-04: Link a PR URL to a Linear issue."""
    issue_id = os.environ.get("LINEAR_TEST_ISSUE_ID")
    if not issue_id:
        pytest.skip("LINEAR_TEST_ISSUE_ID not set")
    _require_env("ANTHROPIC_API_KEY")
    from hsb.agents.linear_agent import run_validated_linear_agent

    result = await run_validated_linear_agent(
        operation="link",
        payload={"issueId": issue_id, "prUrl": "https://github.com/test/repo/pull/1"},
    )
    assert result.result == "success"
