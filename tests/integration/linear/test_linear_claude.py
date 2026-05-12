"""Integration tests for the Linear Agent against a real Linear workspace.

Requires:
  - Linear MCP authenticated via mcp-remote (~/.mcp-remote/ OAuth token)
  - ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN in environment
  - LINEAR_TEST_PROJECT_NAME env var — the Linear project name to target (optional)

Provider and model are driven by env vars:
  LINEAR_PROVIDER_NAME=claude          (default)
  LINEAR_PROVIDER_MODEL=claude-opus-4-5
  LINEAR_PROVIDER_AUTH=oauth2          (default: api_key)

Run with:
    HSB_RUN_INTEGRATION=1 pytest tests/integration/linear/ -v
"""

import os
import re

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
from linear.providers.claude import LINEAR_HOOKS
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
        title="[Integration Test] Linear Agent Connectivity",
        description="Verify the Linear Agent can persist items via MCP.",
    ),
    LinearItemInput(
        type=LinearItemType.task,
        title="Create a test task via agent",
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
def claude_provider():
    if not settings.linear.provider.is_claude():
        pytest.skip(
            f"LINEAR_PROVIDER_NAME={settings.linear.provider.name} — this test is Claude-only"
        )

    return ProviderRegistry.build_from_auth_method(
        settings.linear.provider.name,
        auth_method=settings.linear.provider.auth.kind,
    )


@pytest.fixture(scope="module")
def claude_options() -> ProviderOptions:
    # ClaudeProvider auto-converts HTTP MCP to STDIO via mcp-remote
    return ProviderOptions(
        system_prompt=TextSystemPrompt(SYSTEM_PROMPT),
        model=settings.linear.provider.model,
        max_turns=10,
        tool_policy=ToolPolicy(allowed={"mcp__linear__*"}),
        mcp_servers=(
            McpServerSpec(name="linear", transport="http", url=settings.linear.mcp_url),
        ),
        extras={"claude": {"hooks": LINEAR_HOOKS}},
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
    claude_provider,
    claude_options: ProviderOptions,
):
    """Agent creates at least one Linear issue and returns success."""
    output = await run_validated_linear_agent(
        create_input, claude_provider, claude_options
    )

    assert output.result == "success", f"Agent failed: {output.error}"
    assert len(output.linear_entities) > 0, "Expected at least one created entity"


@pytest.mark.asyncio
async def test_create_task_entities_have_valid_ids(
    create_input: LinearInput,
    claude_provider,
    claude_options: ProviderOptions,
):
    """All returned LinearEntity ids match the LIN-\\d+ pattern."""
    output = await run_validated_linear_agent(
        create_input, claude_provider, claude_options
    )

    assert output.result == "success", f"Agent failed: {output.error}"
    for entity in output.linear_entities:
        assert re.match(r"^LIN-\d+$", entity.id), f"Invalid entity id: {entity.id}"
        assert entity.url.startswith("https://linear.app/"), (
            f"Invalid entity url: {entity.url}"
        )


@pytest.mark.asyncio
async def test_create_task_output_matches_operation(
    create_input: LinearInput,
    claude_provider,
    claude_options: ProviderOptions,
):
    """Output operation field echoes back the requested operation."""
    output = await run_validated_linear_agent(
        create_input, claude_provider, claude_options
    )

    assert output.operation == LinearOperation.create
