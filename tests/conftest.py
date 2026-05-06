"""Shared pytest fixtures.

Phase 5 G1 defensive pairing: a session-scoped autouse fixture clears
``ANTHROPIC_API_KEY`` at test session start so that the function-entry G1
guard in ``_sdk_options.assert_oauth2_only()`` never trips on a leaked env
var during automated runs. Pairs with — does not replace — the runtime
G1 guard in ``_sdk_options.py``.
"""
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _gsd_clear_api_key():
    """G1 defensive: unset ``ANTHROPIC_API_KEY`` at test session start."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    yield
    # Do NOT restore on teardown — test sessions are short-lived processes
    # and we never want a child test process inheriting this env var.


@pytest.fixture
def valid_linear_output() -> dict:
    """Canonical valid LinearOutput payload for contract tests."""
    return {
        "operation": "create",
        "result": "success",
        "linear_entities": [
            {
                "id": "LIN-123",
                "type": "task",
                "url": "https://linear.app/hsb/issue/LIN-123",
            }
        ],
        "error": None,
    }


@pytest.fixture
def failed_linear_output() -> dict:
    """Canonical failed LinearOutput payload for contract tests."""
    return {
        "operation": "create",
        "result": "failed",
        "linear_entities": [],
        "error": "tool_failure: mcp__linear__create_issue returned 500",
    }
