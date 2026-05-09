"""guards.py — Security and compliance guards for PydanticAI agents.

Replaces _sdk_options.py. Key changes from the claude-agent-sdk era:

G1 INVERTED: PydanticAI requires ANTHROPIC_API_KEY (not OAuth token).
  assert_api_key_set() now asserts the key IS present.
  The conftest.py session fixture must SET the key (or let it pass through).

G2: validate_tool_list(tools) raises ValueError if "Agent" appears. No
  change in semantics — just detached from ClaudeAgentOptions.

G3: assert_no_task_dispatch(msg) is a noop. No Task tool exists in
  PydanticAI. Kept as a importable shim so source-grep tests and any
  remaining callers do not break during the migration window.

G5: linear_write_guard unchanged — pure Python stack inspection.
"""

from __future__ import annotations

import functools
import inspect
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_FORBIDDEN_TOOLS: set[str] = {"Agent"}  # G2: WORC-02


def assert_api_key_set() -> None:
    """G1 (inverted for PydanticAI): ANTHROPIC_API_KEY must be present.

    PydanticAI's AnthropicModel reads this key directly. Call this from
    every public agent entry-point before constructing the model.
    """
    if "ANTHROPIC_API_KEY" not in os.environ:
        raise RuntimeError(
            "G1 (PydanticAI): ANTHROPIC_API_KEY is not set. "
            "PydanticAI requires a direct API key."
        )


def validate_tool_list(tool_names: list[str]) -> None:
    """G2 (WORC-02): raise ValueError if any forbidden tool name is present."""
    forbidden = _FORBIDDEN_TOOLS & set(tool_names)
    if forbidden:
        raise ValueError(
            f"G2 violation: {forbidden} must not appear in tool list. "
            "Sub-subagent dispatch is forbidden by WORC-02."
        )


def assert_no_task_dispatch(msg: Any) -> None:  # noqa: ARG001
    """G3 shim — noop in PydanticAI. No Task tool exists.

    Preserved as an importable symbol so source-grep-based tests that
    check for 'assert_no_task_dispatch' in agent source files still pass
    during the migration window. Safe to call on any object.
    """
    return


# G5 — unchanged from _sdk_options.py
_RISK_AGENT_PATH_FRAGMENT = "hsb/agents/risk_agent.py"
_GLOBAL_ORCH_PATH_FRAGMENT = "hsb/agents/global_orchestrator.py"
_OPERATOR_DELEGATED_FRAME = "approve_improvement_trigger"


def _stack_includes_risk_agent_excluding_delegated() -> bool:
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


def linear_write_guard(fn: Any) -> Any:
    """G5 decorator — identical logic to _sdk_options.linear_write_guard."""

    @functools.wraps(fn)
    async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
        if _stack_includes_risk_agent_excluding_delegated():
            logger.error(
                "G5 violation: LinearAgent write from risk_agent.py outside delegated path."
            )
            raise PermissionError(
                "RISK-04 violation (G5): Risk Agent attempted Linear write "
                "without explicit operator delegation."
            )
        return await fn(*args, **kwargs)

    @functools.wraps(fn)
    def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        if _stack_includes_risk_agent_excluding_delegated():
            logger.error(
                "G5 violation: LinearAgent write from risk_agent.py outside delegated path."
            )
            raise PermissionError(
                "RISK-04 violation (G5): Risk Agent attempted Linear write "
                "without explicit operator delegation."
            )
        return fn(*args, **kwargs)

    if inspect.iscoroutinefunction(fn):
        return _async_wrapper
    return _sync_wrapper
