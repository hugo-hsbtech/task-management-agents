"""Unit tests for the provider-agnostic backlog agent."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

import backlog.agent as backlog_agent
from backlog.agent import (
    BacklogAgent,
    build_provider,
    run_backlog_agent,
    run_backlog_agent_async,
)
from backlog.contracts import BacklogInput
from backlog.platforms import LinearPlatform
from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.protocol import Message, ProviderOptions
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import ToolPolicy
from settings.provider import (
    ApiKeyAuth,
    OAuth2ADCAuth,
    OAuth2CliAuth,
    ProviderName,
    ProviderSettings,
)

EMPTY_TOOL_POLICY = ToolPolicy()

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class FakeProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []
        self.options: list[ProviderOptions] = []

    async def query(
        self,
        prompt: str,
        options: ProviderOptions,
    ) -> AsyncIterator[Message]:
        self.prompts.append(prompt)
        self.options.append(options)
        yield Message(text=self.responses.pop(0), is_final=True)


@pytest.fixture
def backlog_input() -> BacklogInput:
    return BacklogInput(
        plan_content="# Plan\nBuild login.",
        stacks=["python"],
        platform=LinearPlatform(team_id="team-1", project_id="project-1"),
        context={"repository": "repo"},
    )


def provider_settings(model: str = "gpt-4o") -> ProviderSettings:
    return ProviderSettings(
        name=ProviderName.openai,
        model=model,
        auth=ApiKeyAuth(key="sk-test"),
    )


def output_json(*, include_platform_fields: bool = False) -> str:
    fields: dict[str, Any] = {
        "title": "[EPIC] Login",
        "description": "Build login.",
        "priority": 2,
    }
    if include_platform_fields:
        fields["platform_fields"] = {"team_id": "custom-team"}
    return json.dumps(
        {
            "platform": {
                "team_id": "team-1",
                "project_id": "project-1",
            },
            "issues": [
                {
                    "issue_type": "epic",
                    "fields": fields,
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_agent_uses_provider_settings_model_and_validates_output(
    backlog_input: BacklogInput,
) -> None:
    provider = FakeProvider([output_json()])

    output = await run_backlog_agent_async(
        backlog_input,
        provider_settings=provider_settings(model="o4-mini"),
        provider=provider,  # type: ignore[arg-type]
        tool_policy=EMPTY_TOOL_POLICY,
    )

    assert output.platform.platform_name == "linear"
    assert output.issues[0].fields.platform_fields == {
        "team_id": "team-1",
        "project_id": "project-1",
    }
    assert provider.options[0].model == "o4-mini"
    assert provider.options[0].output_schema is not None


@pytest.mark.asyncio
async def test_backlog_agent_class_controls_state(
    backlog_input: BacklogInput,
) -> None:
    provider = FakeProvider([output_json()])
    agent = BacklogAgent(
        provider_settings=provider_settings(model="o4-mini"),
        provider=provider,  # type: ignore[arg-type]
        tool_policy=EMPTY_TOOL_POLICY,
        max_validation_retries=1,
        max_turns=7,
    )

    output = await agent.run(backlog_input)

    assert agent.provider is provider
    assert agent.tool_policy is EMPTY_TOOL_POLICY
    assert provider.options[0].max_turns == 7
    assert output.platform.team_id == "team-1"


@pytest.mark.asyncio
async def test_agent_retries_after_invalid_provider_output(
    backlog_input: BacklogInput,
) -> None:
    provider = FakeProvider(["not json", output_json()])

    output = await run_backlog_agent_async(
        backlog_input,
        provider_settings=provider_settings(),
        provider=provider,  # type: ignore[arg-type]
        tool_policy=EMPTY_TOOL_POLICY,
    )

    assert len(provider.prompts) == 2
    assert output.issues[0].fields.title == "[EPIC] Login"


@pytest.mark.asyncio
async def test_agent_retries_after_empty_final_message(
    backlog_input: BacklogInput,
) -> None:
    provider = FakeProvider(["", output_json()])

    output = await run_backlog_agent_async(
        backlog_input,
        provider_settings=provider_settings(),
        provider=provider,  # type: ignore[arg-type]
        tool_policy=EMPTY_TOOL_POLICY,
    )

    assert len(provider.prompts) == 2
    assert output.issues[0].fields.title == "[EPIC] Login"


@pytest.mark.asyncio
async def test_agent_raises_after_exhausted_validation_retries(
    backlog_input: BacklogInput,
) -> None:
    provider = FakeProvider(["not json", "still not json", "nope"])

    with pytest.raises(ValueError, match="failed validation after 3 attempts"):
        await run_backlog_agent_async(
            backlog_input,
            provider_settings=provider_settings(),
            provider=provider,  # type: ignore[arg-type]
            tool_policy=EMPTY_TOOL_POLICY,
        )

    assert len(provider.prompts) == 3


@pytest.mark.asyncio
async def test_agent_preserves_provider_platform_fields_over_defaults(
    backlog_input: BacklogInput,
) -> None:
    provider = FakeProvider([output_json(include_platform_fields=True)])

    output = await run_backlog_agent_async(
        backlog_input,
        provider_settings=provider_settings(),
        provider=provider,  # type: ignore[arg-type]
        tool_policy=EMPTY_TOOL_POLICY,
    )

    assert output.issues[0].fields.platform_fields == {
        "team_id": "custom-team",
        "project_id": "project-1",
    }


def test_run_backlog_agent_sync_wrapper_returns_output(
    backlog_input: BacklogInput,
) -> None:
    provider = FakeProvider([output_json()])

    output = run_backlog_agent(
        backlog_input,
        provider_settings=provider_settings(),
        provider=provider,  # type: ignore[arg-type]
        tool_policy=EMPTY_TOOL_POLICY,
    )

    assert output.issues[0].fields.title == "[EPIC] Login"


def test_build_provider_uses_provider_settings_without_direct_env_access(
    monkeypatch,
) -> None:
    class TestProvider:
        def __init__(self, auth: ApiKey) -> None:
            self.auth = auth

    calls: list[tuple[str, ApiKey]] = []

    def fake_build(name: str, *, auth: ApiKey) -> TestProvider:
        calls.append((name, auth))
        return TestProvider(auth)

    monkeypatch.setattr(ProviderRegistry, "build", fake_build)
    configured = provider_settings()

    provider = build_provider(configured)

    assert isinstance(provider, TestProvider)
    assert calls[0][0] == "openai"
    assert provider.auth.resolve().payload["api_key"] == "sk-test"


def test_build_provider_uses_settings_provider_when_not_explicit(
    monkeypatch,
) -> None:
    class TestProvider:
        def __init__(self, auth: ApiKey) -> None:
            self.auth = auth

    def fake_build(name: str, *, auth: ApiKey) -> TestProvider:
        assert name == "openai"
        return TestProvider(auth)

    monkeypatch.setattr(ProviderRegistry, "build", fake_build)
    monkeypatch.setattr(
        backlog_agent,
        "settings",
        type("FakeSettings", (), {"provider": provider_settings()})(),
    )

    provider = build_provider()

    assert isinstance(provider, TestProvider)


def test_build_provider_accepts_oauth2_cli_auth(monkeypatch) -> None:
    captured: list[OAuth2CliToken] = []

    def fake_build(name: str, *, auth: OAuth2CliToken) -> object:
        captured.append(auth)
        return object()

    monkeypatch.setattr(ProviderRegistry, "build", fake_build)
    configured = ProviderSettings(
        name=ProviderName.claude,
        model="claude-haiku-4-5",
        auth=OAuth2CliAuth(env_var="TOKEN"),
    )

    build_provider(configured)

    assert isinstance(captured[0], OAuth2CliToken)


def test_build_provider_rejects_unwired_oauth2_adc_auth() -> None:
    configured = ProviderSettings(
        name=ProviderName.gemini,
        model="gemini-2.5-pro",
        auth=OAuth2ADCAuth(),
        gemini={"project_id": "project-1"},
    )

    with pytest.raises(ValueError, match="oauth2_adc auth is not wired"):
        build_provider(configured)


def test_auth_from_settings_rejects_unknown_auth_type() -> None:
    """_auth_from_settings must surface unsupported auth subclasses as TypeError."""
    from backlog.agent import _auth_from_settings

    class _ForeignAuth:
        """Auth type not handled by the registry."""

    configured = ProviderSettings(
        name=ProviderName.openai,
        model="gpt-4o",
        auth=ApiKeyAuth(key="sk-test"),
    )
    object.__setattr__(configured, "auth", _ForeignAuth())

    with pytest.raises(TypeError, match="Unsupported auth settings type"):
        _auth_from_settings(configured)


def test_build_tool_policy_uses_platform_api_key(monkeypatch) -> None:
    """build_tool_policy must pull the platform's api_key property and forward it."""
    from backlog.platforms import LinearPlatform

    monkeypatch.setattr(
        LinearPlatform, "api_key", property(lambda self: "lin-from-settings")
    )

    captured: list[str] = []

    def fake_tool_policy(self: LinearPlatform, *, api_key: str) -> ToolPolicy:
        captured.append(api_key)
        return ToolPolicy()

    monkeypatch.setattr(LinearPlatform, "tool_policy", fake_tool_policy)

    input_contract = BacklogInput(
        plan_content="# Plan",
        stacks=["python"],
        platform=LinearPlatform(team_id="team-1", project_id="project-1"),
    )

    policy = BacklogAgent.build_tool_policy(input_contract)

    assert isinstance(policy, ToolPolicy)
    assert captured == ["lin-from-settings"]


@pytest.mark.asyncio
async def test_create_issues_delegates_to_platform_execute(monkeypatch) -> None:
    """BacklogAgent.create_issues must call output.platform.execute(output)."""
    from backlog.contracts import BacklogOutput, IssueFields, IssuePlan
    from backlog.platforms import LinearPlatform

    platform = LinearPlatform(team_id="team-1", project_id="project-1")
    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                issue_type="task",
                fields=IssueFields(
                    title="[T] Anything",
                    description="Any.",
                    platform_fields={"team_id": "team-1", "project_id": "project-1"},
                ),
            )
        ],
    )

    captured: list[BacklogOutput] = []

    async def fake_execute(self: LinearPlatform, out: BacklogOutput) -> list[Any]:
        captured.append(out)
        return ["fake-result"]

    monkeypatch.setattr(LinearPlatform, "execute", fake_execute)

    results = await BacklogAgent.create_issues(output)

    assert captured == [output]
    assert results == ["fake-result"]


def test_run_and_create_sync_returns_output_and_results(
    monkeypatch, backlog_input: BacklogInput
) -> None:
    """run_and_create_sync must drive both run() and create_issues() under asyncio.run()."""
    from backlog.platforms import LinearPlatform

    provider = FakeProvider([output_json()])
    agent = BacklogAgent(
        provider_settings=provider_settings(),
        provider=provider,  # type: ignore[arg-type]
        tool_policy=EMPTY_TOOL_POLICY,
    )

    async def fake_execute(self: LinearPlatform, output: Any) -> list[str]:
        return ["created-1"]

    monkeypatch.setattr(LinearPlatform, "execute", fake_execute)

    output, results = agent.run_and_create_sync(backlog_input)

    assert output.issues[0].fields.title == "[EPIC] Login"
    assert results == ["created-1"]


def test_create_issues_sync_wraps_create_issues_in_asyncio_run(monkeypatch) -> None:
    """create_issues_sync must run create_issues() to completion via asyncio.run()."""
    from backlog.contracts import BacklogOutput, IssueFields, IssuePlan
    from backlog.platforms import LinearPlatform

    platform = LinearPlatform(team_id="team-1", project_id="project-1")
    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                issue_type="task",
                fields=IssueFields(
                    title="[T] Anything",
                    description="Any.",
                    platform_fields={"team_id": "team-1", "project_id": "project-1"},
                ),
            )
        ],
    )

    async def fake_execute(self: LinearPlatform, out: Any) -> list[str]:
        return ["sync-result"]

    monkeypatch.setattr(LinearPlatform, "execute", fake_execute)

    agent = BacklogAgent(
        provider_settings=provider_settings(),
        provider=FakeProvider([]),  # type: ignore[arg-type]
        tool_policy=EMPTY_TOOL_POLICY,
    )

    assert agent.create_issues_sync(output) == ["sync-result"]


def test_build_provider_maps_codex_name_to_openai_registry(monkeypatch) -> None:
    """build_provider(codex settings) must call ProviderRegistry.build("openai", ...)."""
    from pathlib import Path

    from settings.provider import CodexModel, OAuth2CliAuth, ProviderName, ProviderSettings

    class TestProvider:
        def __init__(self, auth: OAuth2CliToken) -> None:
            self.auth = auth

    calls: list[tuple[str, object]] = []

    def fake_build(name: str, *, auth: object) -> TestProvider:
        calls.append((name, auth))
        return TestProvider(auth)  # type: ignore[arg-type]

    monkeypatch.setattr(ProviderRegistry, "build", fake_build)

    codex_settings = ProviderSettings(
        name=ProviderName.codex,
        model=CodexModel.codex_mini_latest,
        auth=OAuth2CliAuth(token_path=Path("/tmp/auth.json")),
    )

    build_provider(codex_settings)

    assert calls[0][0] == "openai", (
        "build_provider must pass 'openai' to ProviderRegistry for codex settings"
    )
    assert isinstance(calls[0][1], OAuth2CliToken)
