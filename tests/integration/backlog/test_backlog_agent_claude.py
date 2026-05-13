"""Live Claude integration tests for the provider-agnostic backlog agent.

Run with:
    HSB_RUN_INTEGRATION=1 CLAUDE_CODE_OAUTH_TOKEN=... \
        .venv/bin/python -m pytest tests/integration/backlog/test_backlog_agent_claude.py -q
"""

import asyncio
import json
from pathlib import Path

import pytest

from backlog.agent import BacklogAgent
from backlog.contracts import BacklogInput, IssueType
from backlog.platforms import LinearPlatform
from settings import settings
from settings.provider import ClaudeModel, OAuth2CliAuth, ProviderName, ProviderSettings

pytestmark = [pytest.mark.integration]


REAL_WORLD_PLAN = (Path(__file__).parent / "planning-poker-prd.md").read_text(
    encoding="utf-8"
)


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
            platform.validate_target(
                api_key=linear_settings.api_key.get_secret_value(),
            )
        )
    except ValueError as exc:
        pytest.skip(str(exc))

    input_contract = BacklogInput(
        plan_content=REAL_WORLD_PLAN,
        stacks=["nextjs", "react", "typescript", "golang", "postgres", "redis"],
        platform=platform,
        context={
            "repository": "https://github.com/hugo-hsbtech/hsb-test-fixture",
            "environment": "integration-test",
        },
    )

    provider_settings = ProviderSettings(
        name=ProviderName.claude,
        model=ClaudeModel.opus_4_7,
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
        print(
            json.dumps(
                [r.model_dump(mode="json") for r in results],
                indent=2,
            )
        )

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
    assert {result.action for result in results} <= {"create", "reuse", "update"}
    assert any(result.action in {"create", "reuse"} for result in results)
