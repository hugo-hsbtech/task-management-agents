"""Live Claude integration tests for the provider-agnostic backlog agent.

Run with:
    HSB_RUN_INTEGRATION=1 CLAUDE_CODE_OAUTH_TOKEN=... \
        .venv/bin/python -m pytest tests/integration/backlog/test_claude_agent.py -q
"""

import asyncio
import json

import pytest

from backlog.agent import BacklogAgent
from backlog.contracts import BacklogInput, IssueType
from backlog.executor import validate_linear_platform_target
from backlog.platforms import LinearPlatform
from settings import settings
from settings.provider import OAuth2CliAuth, ProviderName, ProviderSettings

pytestmark = [pytest.mark.integration]


REAL_WORLD_PLAN = """# Plan: Team Knowledge Base Search

Build a searchable internal knowledge base for engineering teams.

## Goal
Let engineers search approved implementation notes, QA findings, and release
decisions from one place before starting new work.

## Users
- Backend engineer looking for previous API decisions.
- QA engineer checking known regression patterns.
- Engineering manager reviewing delivery risk.

## Acceptance Criteria
- Users can search by keyword and filter by source type.
- Results show title, source, summary, and a link back to the original record.
- Empty searches return a helpful empty state.
- Search requests complete in under 500 ms for 10,000 indexed records.

## Initial Tasks
- Define the indexed document schema.
- Build the search API endpoint.
- Add result ranking by source recency and keyword match.
- Add tests for empty, partial, and exact-match searches.

## Tech stacks
- Python 3.12
- FastAPI
- PostgreSQL
"""


def test_claude_generates_realistic_backlog_for_product_plan(capsys) -> None:
    runtime_settings = settings.runtime
    if runtime_settings.claude_code_oauth_token is None:
        pytest.skip("CLAUDE_CODE_OAUTH_TOKEN is not configured in settings.runtime")
    linear_settings = settings.linear
    if linear_settings.api_key is None:
        pytest.skip("LINEAR_API_KEY is not configured in settings.linear")
    if linear_settings.team_id is None:
        pytest.skip("LINEAR_TEAM_ID is not configured in settings.linear")
    if linear_settings.project_id is None:
        pytest.skip("LINEAR_PROJECT_ID is not configured in settings.linear")

    platform = LinearPlatform(
        team_id=linear_settings.team_id,
        project_id=linear_settings.project_id,
    )
    try:
        asyncio.run(
            validate_linear_platform_target(
                platform,
                api_key=linear_settings.api_key.get_secret_value(),
            )
        )
    except ValueError as exc:
        pytest.skip(str(exc))

    input_contract = BacklogInput(
        plan_content=REAL_WORLD_PLAN,
        stacks=["python", "fastapi", "postgres"],
        platform=platform,
        context={
            "repository": "https://github.com/hugo-hsbtech/hsb-test-fixture",
            "environment": "integration-test",
        },
    )

    provider_settings = ProviderSettings(
        name=ProviderName.claude,
        model="claude-haiku-4-5",
        auth=OAuth2CliAuth(env_var="CLAUDE_CODE_OAUTH_TOKEN"),
    )
    agent = BacklogAgent(
        provider_settings=provider_settings,
    )
    output, results = agent.run_and_create_sync(input_contract)

    with capsys.disabled():
        print("\nBacklogOutput:")
        print(json.dumps(output.model_dump(mode="json"), indent=2))
        print("\nLinear write results:")
        print(json.dumps(results, indent=2))

    assert output.is_linear()
    assert output.issues
    assert {issue.issue_type for issue in output.issues} & {
        IssueType.epic,
        IssueType.user_story,
        IssueType.task,
    }

    for issue in output.issues:
        assert issue.fields.title.strip()
        assert issue.fields.description.strip()
        assert issue.fields.platform_fields["team_id"] == linear_settings.team_id
        assert issue.fields.platform_fields["project_id"] == linear_settings.project_id

    assert len(results) == len(output.issues)
    assert {result["action"] for result in results} <= {"create", "reuse", "update"}
    assert any(result["action"] in {"create", "reuse"} for result in results)
