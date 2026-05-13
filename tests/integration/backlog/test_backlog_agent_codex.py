"""Live Codex integration test for the provider-agnostic backlog agent.

Requires:
  - `codex login --device-auth` completed (creates ~/.codex/auth.json)
  - ~/.codex/config.toml with `forced_login_method = "chatgpt"`
  - LINEAR_API_KEY, LINEAR_TEAM_ID, LINEAR_PROJECT_ID set

Run with:
    HSB_RUN_INTEGRATION=1 \\
        uv run pytest tests/integration/backlog/test_backlog_agent_codex.py -q
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from backlog.agent import BacklogAgent
from backlog.contracts import BacklogInput, IssueType
from backlog.platforms import LinearPlatform
from settings import settings
from settings.provider import (
    CodexModel,
    OAuth2CliAuth,
    ProviderName,
    ProviderSettings,
)

pytestmark = [pytest.mark.integration]

REAL_WORLD_PLAN = (Path(__file__).parent / "planning-poker-prd.md").read_text(
    encoding="utf-8"
)


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


def _codex_provider_settings() -> ProviderSettings:
    return ProviderSettings(
        name=ProviderName.codex,
        model=CodexModel.gpt_5_5,
        auth=OAuth2CliAuth(token_path=_codex_home() / "auth.json"),
    )


def test_codex_generates_realistic_backlog_for_product_plan(capsys) -> None:
    auth_path = _codex_home() / "auth.json"
    if not auth_path.exists():
        pytest.skip(
            f"Codex not authenticated: {auth_path} missing. Run: codex login --device-auth"
        )

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

    agent = BacklogAgent(provider_settings=_codex_provider_settings())
    output, results = agent.run_and_create_sync(input_contract)

    with capsys.disabled():
        print("\nBacklogOutput (Codex):")
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
