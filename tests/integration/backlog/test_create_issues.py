"""Integration tests for BacklogAgent.create_issues.

Verifies the Linear write path in isolation — no LLM call is made.
A pre-built BacklogOutput is fed directly to create_issues so the test
is fast, deterministic on the LLM side, and only exercises the executor.

Run with:
    LINEAR_API_KEY=... LINEAR_TEAM_ID=... LINEAR_PROJECT_ID=... \\
        .venv/bin/python -m pytest tests/integration/backlog/test_create_issues.py -v
"""

import json

import pytest

from backlog.agent import BacklogAgent
from backlog.contracts import (
    BacklogOutput,
    IssueAction,
    IssueFields,
    IssuePlan,
    IssueType,
)
from backlog.platforms import LinearPlatform
from settings import settings

pytestmark = [pytest.mark.integration]


@pytest.fixture()
def linear_settings():
    linear = settings.linear
    if linear.api_key is None:
        pytest.skip("LINEAR_API_KEY is not configured in settings.linear")
    if linear.team_id is None:
        pytest.skip("LINEAR_TEAM_ID is not configured in settings.linear")
    if linear.project_id is None:
        pytest.skip("LINEAR_PROJECT_ID is not configured in settings.linear")
    return linear


@pytest.fixture()
def backlog_output(linear_settings) -> BacklogOutput:
    platform = LinearPlatform(
        team_id=linear_settings.team_id, project_id=linear_settings.project_id
    )
    defaults = platform.issue_defaults()
    return BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                action=IssueAction.create,
                issue_type=IssueType.epic,
                fields=IssueFields(
                    title="[EPIC] create_issues integration test",
                    description="Verifies that BacklogAgent.create_issues writes to Linear.",
                    priority=2,
                    platform_fields=dict(defaults),
                ),
            ),
            IssuePlan(
                action=IssueAction.create,
                issue_type=IssueType.task,
                fields=IssueFields(
                    title="[TASK] create_issues integration test — subtask",
                    description="Child task created by the create_issues integration test.",
                    priority=3,
                    platform_fields=dict(defaults),
                ),
            ),
        ],
    )


def test_create_issues_writes_to_linear_and_returns_results(
    capsys, backlog_output: BacklogOutput
) -> None:
    agent = BacklogAgent()

    results = agent.create_issues_sync(backlog_output)

    with capsys.disabled():
        print("\nLinear write results:")
        print(json.dumps([r.model_dump(mode="json") for r in results], indent=2))

    assert len(results) == len(backlog_output.issues)
    assert {r.action for r in results} <= {"create", "reuse", "update"}


def test_create_issues_is_idempotent_on_same_titles(
    capsys, backlog_output: BacklogOutput
) -> None:
    """Running create_issues twice with the same titles reuses existing issues."""
    agent = BacklogAgent()

    first = agent.create_issues_sync(backlog_output)
    second = agent.create_issues_sync(backlog_output)

    with capsys.disabled():
        print("\nFirst run results:")
        print(json.dumps([r.model_dump(mode="json") for r in first], indent=2))
        print("\nSecond run results (expect reuse):")
        print(json.dumps([r.model_dump(mode="json") for r in second], indent=2))

    assert all(r.action == "reuse" for r in second), (
        "Second run should reuse all issues created in the first run"
    )


def test_create_issues_raises_when_api_key_missing(
    monkeypatch, backlog_output: BacklogOutput
) -> None:
    monkeypatch.setattr(
        "backlog.agent.settings",
        type(
            "FakeSettings",
            (),
            {
                "linear": type("FakeLinear", (), {"api_key": None})(),
                "provider": settings.provider,
            },
        )(),
    )
    agent = BacklogAgent()

    with pytest.raises(ValueError, match="Platform API key required"):
        agent.create_issues_sync(backlog_output)


def test_create_issues_delegates_to_platform_execute(
    backlog_output: BacklogOutput,
) -> None:
    """create_issues delegates to platform.execute() — no platform type-check in agent."""
    executed: list[str] = []

    class FakePlatform:
        platform_name = "fake"

        def issue_defaults(self) -> dict:
            return backlog_output.platform.issue_defaults()

        async def execute(self, output: BacklogOutput, *, api_key: str) -> list:
            executed.append(api_key)
            return [{"action": "fake", "issue": {}}] * len(output.issues)

    bad_output = backlog_output.model_copy(update={"platform": FakePlatform()})
    linear = settings.linear
    agent = BacklogAgent()

    results = agent.create_issues_sync(bad_output)

    assert len(executed) == 1
    assert executed[0] == linear.api_key.get_secret_value()
    assert all(r["action"] == "fake" for r in results)
