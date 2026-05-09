"""INTL-04 + G2 enforcement: WIO tools never include Linear write tools.

Updated for PydanticAI: instead of checking ``allowed_tools=[]`` blocks,
we check the ``tools=[...]`` lists passed to ``Agent(...)`` and the
``@_wio_agent.tool_plain`` decorators.
"""
import re
from pathlib import Path

WIO_PATH = Path("src/hsb/agents/work_item_orchestrator.py")


def test_wio_tools_excludes_agent():
    """G2 (WORC-02): no tool function named 'agent' or 'task' is registered."""
    src = WIO_PATH.read_text()
    # PydanticAI tools are registered via @_wio_agent.tool_plain decorators
    # No tool should be named "agent" or use the Agent dispatch pattern
    tool_funcs = re.findall(r"@_wio_agent\.tool_plain\s+async def (\w+)", src)
    for fn in tool_funcs:
        assert fn.lower() not in ("agent", "task"), (
            f"G2 violation: tool function named '{fn}' must not exist"
        )


def test_wio_skill_files_includes_phase5_skills():
    src = WIO_PATH.read_text()
    assert "knowledge-context-enrichment/SKILL.md" in src, (
        "D-04 violated: skill 10 (knowledge-context-enrichment) not "
        "injected into WIO system prompt"
    )
    assert "knowledge-storage/SKILL.md" in src, (
        "D-04 violated: skill 11 (knowledge-storage) not injected into "
        "WIO system prompt"
    )


def test_wio_uses_pydantic_ai_agent():
    """PydanticAI Agent is the new runtime — must be imported and used."""
    src = WIO_PATH.read_text()
    assert "from pydantic_ai import Agent" in src, (
        "WIO must import Agent from pydantic_ai"
    )
    assert "AnthropicModel" in src, (
        "WIO must use AnthropicModel for the LLM backend"
    )


def test_wio_calls_intelligence_step_helpers():
    src = WIO_PATH.read_text()
    assert "build_enrichment_prompt" in src, (
        "INTL-01 violated: WIO does not call build_enrichment_prompt for Step 1"
    )
    assert "build_storage_prompt" in src, (
        "INTL-02 violated: WIO does not call build_storage_prompt for Step 5"
    )


def test_wio_imports_g3_backstop():
    """G3 shim: WIO must import ``assert_no_task_dispatch`` from ``guards``."""
    src = WIO_PATH.read_text()
    assert "from hsb.agents.guards import" in src and (
        "assert_no_task_dispatch" in src
    ), (
        "G3 violated: WIO does not import assert_no_task_dispatch from guards."
    )


def test_wio_uses_message_history_for_multiturn():
    """Multi-turn lifecycle uses message_history= chaining (replaces ClaudeSDKClient)."""
    src = WIO_PATH.read_text()
    assert "message_history=" in src, (
        "WIO must use message_history= for multi-turn (replaces ClaudeSDKClient)"
    )
