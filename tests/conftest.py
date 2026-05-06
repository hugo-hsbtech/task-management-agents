import pytest


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
