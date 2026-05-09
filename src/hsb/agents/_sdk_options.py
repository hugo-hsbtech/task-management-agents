"""Phase 5 SDK options chokepoint.

Provides:
  - ``make_options()``       — factory for ``ClaudeAgentOptions`` (G2 enforcement)
  - ``assert_oauth2_only()`` — function-entry G1 guard (NOT module-import time)
  - ``assert_no_task_dispatch()`` — runtime G3 backstop for the receive loop
  - ``linear_write_guard``   — G5 stack-inspection decorator for LinearAgent writes

Why function-entry G1 (not module-import-time):
A developer/CI environment may legitimately have ``ANTHROPIC_API_KEY`` set for
unrelated reasons. A module-top assertion would crash pytest collection on
import, breaking the entire test suite. The function-entry guard fires at the
exact moment we are about to construct an SDK options object, paired with the
session-scoped autouse fixture in ``tests/conftest.py`` which unsets the env
var at session start as a defensive measure.
"""

import functools
import inspect
import logging
import os
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    PermissionMode,
    ResultMessage,
)
from claude_agent_sdk.types import (
    McpServerConfig,
    Message,
    SystemPromptFile,
    SystemPromptPreset,
    ToolsPreset,
)

logger = logging.getLogger(__name__)

_FORBIDDEN_TOOLS = {"Agent"}  # G2: WORC-02

_FORBIDDEN_API_KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def assert_oauth2_only() -> None:
    """G1 (AI-SPEC §6) — function-entry-time guard. Rejects metered API keys
    for either runtime. Operators must use OAuth tokens:
      - Claude:  CLAUDE_CODE_OAUTH_TOKEN  (from `claude setup-token`)
      - Codex:   ~/.codex/auth.json       (from `codex login --device-auth`)

    Called from :func:`make_options` before every ``ClaudeAgentOptions``
    construction. Function-time (NOT module-import-time) so test environments
    that legitimately have ``ANTHROPIC_API_KEY`` set for unrelated reasons do
    not break pytest collection. The defensive pairing is the session-scoped
    autouse fixture in ``tests/conftest.py`` that unsets the env var at
    session start.
    """
    forbidden = [v for v in _FORBIDDEN_API_KEY_VARS if v in os.environ]
    if forbidden:
        raise RuntimeError(
            f"G1 violation: {', '.join(forbidden)} set — forbidden. "
            "Use OAuth tokens only (CLAUDE_CODE_OAUTH_TOKEN for Claude, "
            "`codex login --device-auth` for Codex)."
        )


def make_options(
    permission_mode: PermissionMode,
    system_prompt: str | SystemPromptPreset | SystemPromptFile | None = None,
    allowed_tools: list[str] | None = None,
    tools: list[str] | ToolsPreset | None = None,
    max_turns: int | None = None,
    model: str | None = None,
    mcp_servers: dict[str, McpServerConfig] | str | Path | None = None,
    max_budget_usd: float | None = None,
    cwd: str | Path | None = None,
    resume: str | None = None,
) -> ClaudeAgentOptions:
    """Construct a ``ClaudeAgentOptions`` with G1 + G2 enforcement.

    G1: ``assert_oauth2_only()`` raises ``RuntimeError`` if
    ``ANTHROPIC_API_KEY`` is set in the environment.

    G2: raises ``ValueError`` if any tool name in ``_FORBIDDEN_TOOLS``
    (currently ``{"Agent"}``) is present in ``allowed_tools``. WORC-02
    forbids sub-subagent dispatch.
    """
    assert_oauth2_only()  # G1: enforced at every SDK construction site through this factory.
    forbidden = _FORBIDDEN_TOOLS & set(allowed_tools or [])
    if forbidden:
        raise ValueError(
            f"G2 violation: {forbidden} must not appear in allowed_tools. "
            "Sub-subagent dispatch is forbidden by WORC-02."
        )
    kwargs: dict[str, Any] = dict(
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        permission_mode=permission_mode,
        max_turns=max_turns,
        model=model,
    )
    if mcp_servers is not None:
        kwargs["mcp_servers"] = mcp_servers
    if max_budget_usd is not None:
        kwargs["max_budget_usd"] = max_budget_usd
    if cwd is not None:
        kwargs["cwd"] = cwd
    if resume is not None:
        kwargs["resume"] = resume
    if tools:
        kwargs["tools"] = tools
    return ClaudeAgentOptions(**kwargs)


def assert_no_task_dispatch(msg: Message) -> None:
    """G3 (AI-SPEC §6) — runtime backstop for G2.

    Called from every agent's SDK receive loop on every message. Inspects
    ``AssistantMessage`` content blocks for any ``tool_use_block`` with
    ``name == "Task"`` (the SDK name for sub-agent dispatch). G2 is the
    configuration-time defense (``allowed_tools``); G3 catches an SDK
    regression that bypasses ``allowed_tools`` enforcement at runtime.

    Detection:
      - For ``AssistantMessage``: walk ``msg.content``; if any block exposes
        ``name == "Task"`` (i.e., a ``ToolUseBlock`` named ``"Task"``), raise.
      - For ``ResultMessage``: best-effort scan of ``msg.usage`` /
        ``msg.tool_calls`` if the SDK exposes them.
      - Other message types: no-op.

    Intervention: raise ``RuntimeError``; the agent's receive loop must
    propagate (do NOT swallow) so the SDK session aborts.
    """

    if isinstance(msg, AssistantMessage):
        for block in getattr(msg, "content", []) or []:
            block_name = getattr(block, "name", None)
            if block_name == "Task":
                logger.error(
                    "G3 violation: Task-tool dispatch detected at runtime. "
                    "WORC-02 forbids sub-subagent dispatch. Aborting session."
                )
                raise RuntimeError(
                    "G3 violation: 'Task' tool dispatched at runtime "
                    "(WORC-02 / sub-subagent dispatch forbidden)."
                )
        return

    if isinstance(msg, ResultMessage):
        candidates = getattr(msg, "usage", {}).get("tool_uses", None) or []
        for entry in candidates or []:
            entry_name = (
                entry.get("name")
                if isinstance(entry, dict)
                else getattr(entry, "name", None)
            )
            if entry_name == "Task":
                logger.error(
                    "G3 violation: Task-tool dispatch found in ResultMessage tool log."
                )
                raise RuntimeError(
                    "G3 violation: 'Task' tool dispatched at runtime "
                    "(WORC-02 / sub-subagent dispatch forbidden)."
                )


# G5 (AI-SPEC §6) — LinearAgent write-call decorator with stack inspection.
# RISK-04: any Linear write originating from src/hsb/agents/risk_agent.py
# is denied EXCEPT the explicit operator-delegated path through
# src/hsb/agents/global_orchestrator.py::approve_improvement_trigger().

_RISK_AGENT_PATH_FRAGMENT = "hsb/agents/risk_agent.py"
_GLOBAL_ORCH_PATH_FRAGMENT = "hsb/agents/global_orchestrator.py"
_OPERATOR_DELEGATED_FRAME = "approve_improvement_trigger"


def _stack_includes_risk_agent_excluding_delegated() -> bool:
    """Return ``True`` iff the current call stack contains a frame inside
    ``risk_agent.py`` AND no frame for the explicit operator-delegated
    ``global_orchestrator.approve_improvement_trigger()`` entry point."""
    found_risk_frame = False
    found_delegated_frame = False
    for frame_info in inspect.stack():
        filename = frame_info.filename or ""
        funcname = frame_info.function or ""
        if _RISK_AGENT_PATH_FRAGMENT in filename:
            found_risk_frame = True
        if (
            _GLOBAL_ORCH_PATH_FRAGMENT in filename
            and funcname == _OPERATOR_DELEGATED_FRAME
        ):
            found_delegated_frame = True
    return found_risk_frame and not found_delegated_frame


def linear_write_guard(fn):
    """G5 decorator. Apply to every ``LinearAgent`` write method
    (``create_issue``, ``update_issue``, ``create_comment``,
    ``create_subtasks``, etc.). Stack-inspects on every call; denies if
    invocation originated from ``risk_agent.py`` outside the
    operator-delegated path.

    See AI-SPEC §6 G5: 'Inspect Python call stack: if any frame originates
    from ``src/hsb/agents/risk_agent.py``, except the explicit
    operator-delegated path through
    ``src/hsb/agents/global_orchestrator.py::approve_improvement_trigger()``,
    deny.'
    """

    @functools.wraps(fn)
    async def _async_wrapper(*args, **kwargs):
        if _stack_includes_risk_agent_excluding_delegated():
            logger.error(
                "G5 violation: LinearAgent write attempted from risk_agent.py "
                "outside the operator-delegated approve_improvement_trigger() path. "
                "RISK-04 enforcement: denying."
            )
            raise PermissionError(
                "RISK-04 violation (G5): Risk Agent attempted Linear write "
                "without explicit operator delegation."
            )
        return await fn(*args, **kwargs)

    @functools.wraps(fn)
    def _sync_wrapper(*args, **kwargs):
        if _stack_includes_risk_agent_excluding_delegated():
            logger.error(
                "G5 violation: LinearAgent write attempted from risk_agent.py "
                "outside the operator-delegated approve_improvement_trigger() path."
            )
            raise PermissionError(
                "RISK-04 violation (G5): Risk Agent attempted Linear write "
                "without explicit operator delegation."
            )
        return fn(*args, **kwargs)

    if inspect.iscoroutinefunction(fn):
        return _async_wrapper

    return _sync_wrapper
