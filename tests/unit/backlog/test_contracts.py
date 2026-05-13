"""Unit tests for backlog contracts and platform protocol."""

import json

import pytest
from pydantic import ValidationError

from backlog.contracts import (
    BacklogInput,
    BacklogOutput,
    IssueFields,
    IssuePlan,
)
from backlog.platforms import (
    LINEAR_BACKLOG_TOOL_NAMES,
    BacklogPlatform,
    LinearPlatform,
)
from backlog.prompts import BACKLOG_USER_PROMPT_TEMPLATE
from utils.prompt import build_prompt, prompt_template_fields, to_json


def test_backlog_input_requires_platform_dependency() -> None:
    with pytest.raises(ValidationError):
        BacklogInput.model_validate({"plan_content": "# Plan"})


def test_backlog_input_accepts_plan_stack_and_linear_platform_dependency() -> None:
    input_contract = BacklogInput(
        plan_content="# Plan",
        stacks=["python", "fastapi"],
        platform=LinearPlatform(team_id="team-1", project_id="project-1"),
        context={"repository": "https://github.com/example/repo"},
    )

    assert isinstance(input_contract.platform, BacklogPlatform)
    assert input_contract.platform.platform_name == "linear"
    assert input_contract.platform.team_id == "team-1"


def test_linear_platform_provides_issue_defaults() -> None:
    platform = LinearPlatform(team_id="team-1", project_id="project-1")

    assert platform.issue_defaults == {
        "team_id": "team-1",
        "project_id": "project-1",
    }


def test_linear_platform_provides_supported_tool_policy() -> None:
    policy = LinearPlatform(team_id="team-1", project_id="project-1").tool_policy(
        api_key="lin-test"
    )

    assert policy.allowed == LINEAR_BACKLOG_TOOL_NAMES
    assert {spec.name for spec in policy.custom} == set(LINEAR_BACKLOG_TOOL_NAMES)
    assert all(spec.handler is not None for spec in policy.custom)


def test_linear_platform_requires_team_and_project_ids() -> None:
    with pytest.raises(ValidationError):
        LinearPlatform.model_validate({"team_id": "team-1"})


def test_backlog_output_requires_at_least_one_issue() -> None:
    with pytest.raises(ValidationError):
        BacklogOutput.model_validate(
            {
                "platform": {"team_id": "team-1", "project_id": "project-1"},
                "issues": [],
            }
        )


def test_backlog_output_accepts_linear_issue_fields() -> None:
    output = BacklogOutput(
        platform=LinearPlatform(team_id="team-1", project_id="project-1"),
        issues=[
            IssuePlan(
                issue_type="epic",
                fields=IssueFields(
                    title="[EPIC] Authentication",
                    description="Build the authentication flow.",
                    priority=3,
                    labels=["backlog"],
                    platform_fields={
                        "team_id": "team-1",
                        "project_id": "project-1",
                    },
                ),
            )
        ],
    )

    assert output.issues[0].fields.title == "[EPIC] Authentication"
    assert output.issues[0].fields.priority == 3


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        IssueFields.model_validate(
            {
                "title": "[Task] Login endpoint",
                "description": "Implement the endpoint.",
                "unexpected": "boom",
            }
        )


def test_linear_issue_priority_must_match_linear_bounds() -> None:
    with pytest.raises(ValidationError):
        IssueFields.model_validate(
            {
                "title": "[Task] Login endpoint",
                "description": "Implement the endpoint.",
                "priority": 5,
            }
        )


def test_backlog_user_prompt_is_parseable_and_matches_contract_shape() -> None:
    input_contract = BacklogInput(
        plan_content="# Plan",
        stacks=["python"],
        platform=LinearPlatform(team_id="team-1", project_id="project-1"),
    )

    prompt = build_prompt(
        BACKLOG_USER_PROMPT_TEMPLATE,
        output_schema=to_json(BacklogOutput.model_json_schema()),
        platform=to_json(input_contract.platform.model_dump(mode="json")),
        platform_defaults=to_json(input_contract.platform.issue_defaults),
        plan_content=to_json(input_contract.plan_content),
        stacks=to_json(input_contract.stacks),
        platform_name=to_json(input_contract.platform.platform_name),
        context=to_json(input_contract.context),
    )
    payload = json.loads(prompt)

    assert prompt_template_fields(BACKLOG_USER_PROMPT_TEMPLATE) == {
        "context",
        "output_schema",
        "plan_content",
        "platform",
        "platform_defaults",
        "platform_name",
        "stacks",
    }
    assert payload["output_contract"]["type"] == "BacklogOutput"
    assert payload["output_contract"]["required_shape"]["platform"] == {
        "team_id": "team-1",
        "project_id": "project-1",
    }
    assert payload["input"]["platform_defaults"] == {
        "team_id": "team-1",
        "project_id": "project-1",
    }
