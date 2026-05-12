"""Integration tests for the Linear Agent using Codex backend.

Requires:
  - Codex CLI authenticated (`codex login --device-auth`)
  - ~/.codex/config.toml with MCP servers configured
  - LINEAR_TEST_PROJECT_NAME env var (optional)

Provider and model are driven by env vars:
  LINEAR_PROVIDER_NAME=openai           (required for Codex)
  LINEAR_PROVIDER_MODEL=gpt-4o
  LINEAR_PROVIDER_AUTH__KIND=oauth2_cli  (default for Codex)

Run with:
    HSB_RUN_INTEGRATION=1 uv run pytest tests/integration/linear/test_linear_codex.py -v

Note: Codex backend doesn't support hooks (capabilities.supports_hooks=False).
"""

from __future__ import annotations

import os

import pytest

from linear.agent import run_validated_linear_agent
from linear.contracts import (
    LinearInput,
    LinearItemInput,
    LinearItemType,
    LinearOperation,
    Project,
)
from linear.prompts import SYSTEM_PROMPT
from llm_providers import McpServerSpec, ProviderRegistry
from llm_providers.prompt import TextSystemPrompt
from llm_providers.protocol import ProviderOptions
from llm_providers.tools import ToolPolicy
from settings import settings

pytestmark = [pytest.mark.integration]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_ITEMS = [
    LinearItemInput(
        type=LinearItemType.epic,
        title="[Integration Test] Linear Agent Connectivity (Codex)",
        description="Verify the Linear Agent can persist items via MCP using Codex backend.",
    ),
    LinearItemInput(
        type=LinearItemType.task,
        title="Create a test task via Codex agent",
        description="Confirm the agent creates issues visible in the test project.",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_project() -> Project:
    name = os.environ.get("LINEAR_TEST_PROJECT_NAME", "Linear Integration Tests")
    return Project(name=name)


@pytest.fixture(scope="module")
def codex_provider():
    """Build OpenAI provider with Codex backend (OAuth2 from ~/.codex/auth.json)."""
    if settings.linear.provider.name.value != "openai":
        pytest.skip(
            f"LINEAR_PROVIDER_NAME={settings.linear.provider.name} — "
            f"this test is Codex (openai) only"
        )

    # Codex uses oauth2_cli_token by default
    auth_kind = settings.linear.provider.auth.kind
    if auth_kind != "oauth2_cli":
        pytest.skip(f"Codex requires oauth2_cli auth, got {auth_kind}")

    return ProviderRegistry.build_from_auth_method(
        "openai",  # Codex is the openai provider with oauth2
        auth_method="oauth2_cli",
    )


@pytest.fixture(scope="module")
def codex_options() -> ProviderOptions:
    """ProviderOptions for Codex backend.

    Note: Codex doesn't support hooks (supports_hooks=False).
    MCP servers must be configured in ~/.codex/config.toml
    """
    # For Codex, MCP servers are configured in ~/.codex/config.toml
    # We pass them for verification, but Codex reads from its own config
    return ProviderOptions(
        system_prompt=TextSystemPrompt(SYSTEM_PROMPT),
        model=settings.linear.provider.model,
        max_turns=10,
        tool_policy=ToolPolicy(allowed={"mcp__linear__*"}),
        mcp_servers=(
            McpServerSpec(name="linear", transport="http", url=settings.linear.mcp_url),
        ),
        # No hooks - Codex backend doesn't support them
    )


@pytest.fixture
def create_input(test_project: Project) -> LinearInput:
    return LinearInput(
        operation=LinearOperation.create,
        project=test_project,
        items=SAMPLE_ITEMS,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task_returns_success(
    create_input: LinearInput,
    codex_provider,
    codex_options: ProviderOptions,
):
    """Agent creates at least one Linear issue using Codex and returns success."""
    output = await run_validated_linear_agent(
        create_input, codex_provider, codex_options
    )

    assert output.result == "success", f"Agent failed: {output.error}"
    assert len(output.linear_entities) > 0, "Expected at least one created entity"


@pytest.mark.asyncio
async def test_create_task_entities_have_valid_ids(
    create_input: LinearInput,
    codex_provider,
    codex_options: ProviderOptions,
):
    r"""All returned LinearEntity ids match the LIN-\d+ pattern."""
    output = await run_validated_linear_agent(
        create_input, codex_provider, codex_options
    )

    assert output.result == "success", f"Agent failed: {output.error}"
    for entity in output.linear_entities:
        assert entity.id.startswith("LIN-"), f"Invalid entity id: {entity.id}"
        assert entity.url.startswith("https://linear.app/"), (
            f"Invalid entity url: {entity.url}"
        )


@pytest.mark.asyncio
async def test_create_task_output_matches_operation(
    create_input: LinearInput,
    codex_provider,
    codex_options: ProviderOptions,
):
    """Output operation field echoes back the requested operation."""
    output = await run_validated_linear_agent(
        create_input, codex_provider, codex_options
    )

    assert output.operation == LinearOperation.create
